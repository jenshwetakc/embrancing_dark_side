"axedev tool: https://chromewebstore.google.com/detail/axe-devtools-web-accessib/lhdoppojpmngadmnindnejefpokejbdd"


import os
import re
import json
import base64
import random
import shutil
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
from collections.abc import Mapping

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

OUT_ROOT              = "/output"

STEPS                 = 1
MOBILE                = False
HEADLESS              = False
PAGE_WAIT_SEC         = 20
HIGHLIGHT_ALL_VIOLATIONS = True
CLEAN_TITLE_MAXLEN = 12

CHROMEDRIVER_PATH = "/chromedriver"  # chromedriver_path
AXE_SCRIPT_PATH   = "/axe.min.js"    # axedevtool


# Tuning thresholds
IOU_THRESHOLD        = 0.50
AREA_DELTA_THRESHOLD = 0.25

def mkdir_clean(path: str) -> str:
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    return path

def mkdir_p(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def wait_ready(driver, timeout: int = 20):  # default fallback if PAGE_WAIT_SEC not injected
    """Wait for document ready + a loose network idle heuristic."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script("""
            const entries = performance.getEntriesByType('resource') || [];
            const now = performance.now();
            return entries.every(e => (now - e.startTime) > 1200);
        """) is True)
    except TimeoutException:
        print("[WARN] wait_ready timed out; proceeding anyway")

def save_json(path: str, data: Any):
    mkdir_p(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _sanitize_filename(s: str) -> str:
    """
    Produce a safe, flat filename (no directories). Removes slashes, question marks, etc.
    Keeps only A-Z a-z 0-9 . _ -
    """
    s = s.replace("://", "_")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

def get_application_name(driver):
    app_url = driver.current_url
    parsed_url = urlparse(app_url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain.replace("www.", "", 1)
    app_name = domain.split('.')[0]
    print(app_name)
    return app_name

def clean_title_from_driver(driver, max_len: int = 48) -> str:  # default fallback
    """
    Your requested logic, with a couple of fallbacks if title is empty.
    """
    page_title = (driver.title or "").strip()
    if not page_title:
        # fallback: last path segment or 'home'
        path_tail = (urlparse(driver.current_url).path or "/").rstrip("/").split("/")[-1] or "home"
        page_title = path_tail

    page_name = page_title[:max_len]  # e.g., 48 chars
    # keep unicode letters/digits/underscore/hyphen/space, then remove spaces
    clean_title = re.sub(r'[^\w\s-]', '', page_name).strip().replace(' ', '')
    # if it ends up empty, force a fallback
    return clean_title or "page"

def short_url_hash(u: str, n: int = 6) -> str:
    return hashlib.sha1(u.encode("utf-8")).hexdigest()[:n]

def page_key(driver, step: int) -> str:
    """
    Short, readable, and collision-safe page key:
    s{step}__{app}__{cleanTitle}__{h6}
    Example: s1__sigmaos__Introducing__a1b2c3
    """
    app  = get_application_name(driver)
    tit  = clean_title_from_driver(driver, 48)
    h6   = short_url_hash(driver.current_url, 6)

    base = f"{app}__{tit}__{h6}"
    base = _sanitize_filename(base)  # keeps only A-Z a-z 0-9 . _ -
    return f"s{step}__{base}"

def _step_index_from_key(key: str) -> int:
    try:
        if key.startswith("s"):
            return int(key.split("__", 1)[0][1:]) - 1
    except Exception:
        pass
    return 0


# SELENIUM
def setup_driver(prefers_color_scheme: str) -> webdriver.Chrome:
    """Launch Chrome and emulate prefers-color-scheme = 'light' or 'dark'."""
    if not os.path.exists(CHROMEDRIVER_PATH):
        raise RuntimeError("CHROMEDRIVER_PATH is not set or invalid.")
    if not os.path.exists(AXE_SCRIPT_PATH):
        raise RuntimeError("AXE_SCRIPT_PATH is not set or invalid.")

    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--ignore-certificate-errors")
    if MOBILE:
        opts.add_experimental_option("mobileEmulation", {"deviceName": "iPhone 12 Pro"})
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {
        "features": [{"name": "prefers-color-scheme", "value": prefers_color_scheme}]
    })
    driver.set_script_timeout(90)
    return driver

def inject_axe(driver):
    with open(AXE_SCRIPT_PATH, "r", encoding="utf-8") as f:
        axe_js = f.read()
    driver.execute_script(axe_js)
    ok = driver.execute_script("return !!window.axe;")
    if not ok:
        raise RuntimeError("Axe was injected but window.axe not found")

def run_axe_full(driver) -> dict:
    inject_axe(driver)
    result = driver.execute_async_script("""
      const cb = arguments[arguments.length - 1];
      if (!window.axe) return cb({error:'axe not injected'});
      axe.run(document, { iframes: true })
        .then(r => cb({ok:true, r}))
        .catch(e => cb({error: (e && e.message) || String(e)}));
    """)
    if result.get("error"):
        raise RuntimeError("axe.run failed: " + result["error"])
    return result["r"]

def collect_internal_links(driver) -> List[str]:
    base = urlparse(driver.current_url).netloc
    seen, links = set(), []
    for a in driver.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href")
        if not href:
            continue
        p = urlparse(href)
        if p.scheme in ("http", "https") and p.netloc == base and href not in seen:
            if p.path or p.query:
                links.append(href); seen.add(href)
    return links

def capture_fullpage_png(driver, out_path: str) -> bool:
    """Use CDP to capture beyond viewport (falls back to viewport)."""
    try:
        driver.execute_cdp_cmd("Page.enable", {})  # improves reliability on some versions
        driver.execute_script("window.scrollTo(0,0)")
        shot = driver.execute_cdp_cmd("Page.captureScreenshot", {"captureBeyondViewport": True})
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        return True
    except Exception as e:
        print(f"[WARN] fullpage capture failed, falling back ({e})")
        driver.save_screenshot(out_path)
        return False


# Axe helpers / data extraction

def extract_cc_details(axe_results: dict) -> List[Dict[str, Any]]:
    out = []
    for v in axe_results.get("violations", []):
        if v.get("id") != "color-contrast":
            continue
        for n in v.get("nodes", []):
            data_entry = None
            for bucket in ("any", "all", "none"):
                for chk in n.get(bucket, []) or []:
                    if chk.get("id") == "color-contrast" and isinstance(chk.get("data"), dict):
                        data_entry = chk["data"]; break
                if data_entry: break
            out.append({
                "targets": n.get("target", []),
                "xpaths": n.get("xpath", []),
                "fgColor": data_entry.get("fgColor") if data_entry else None,
                "bgColor": data_entry.get("bgColor") if data_entry else None,
                "contrastRatio": data_entry.get("contrastRatio") if data_entry else None,
                "fontSize": data_entry.get("fontSize") if data_entry else None,
                "fontWeight": data_entry.get("fontWeight") if data_entry else None,
                "failureSummary": n.get("failureSummary"),
            })
    return out

def enrich_with_geometry(driver, axe_results: dict) -> dict:
    """
    Attach '__bbox' = {x,y,w,h,area} to each node using the first resolvable CSS selector or XPath.
    """
    js = r"""
    (function(violations){
      function byXPath(xp) {
        try {
          const res = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
          return res.snapshotLength ? res.snapshotItem(0) : null;
        } catch(e){ return null; }
      }
      function firstEl(node){
        for (const sel of (node.target||[])) {
          try { const el = document.querySelector(sel); if (el) return el; } catch(e){}
        }
        for (const xp of (node.xpath||[])) {
          const el = byXPath(xp); if (el) return el;
        }
        return null;
      }
      violations.forEach(v => {
        (v.nodes||[]).forEach(n => {
          const el = firstEl(n);
          if (el && el.getBoundingClientRect) {
            const r = el.getBoundingClientRect();
            const x = Math.max(0, Math.floor(window.scrollX + r.left));
            const y = Math.max(0, Math.floor(window.scrollY + r.top));
            const w = Math.max(0, Math.floor(r.width));
            const h = Math.max(0, Math.floor(r.height));
            n.__bbox = {x, y, w, h, area: (w*h)};
          } else {
            n.__bbox = null;
          }
        });
      });
      return violations;
    })
    """
    try:
        new_violations = driver.execute_script(f"return ({js})(arguments[0]);", axe_results.get("violations", []))
        out = dict(axe_results)
        out["violations"] = new_violations
        return out
    except Exception as e:
        print(f"[WARN] geometry enrichment failed: {e}")
        return axe_results


#  Deep freeze / thaw helpers
def _freeze(obj):
    """Recursively convert lists/tuples/dicts into fully hashable structures."""
    if isinstance(obj, Mapping):
        # sort for determinism
        return tuple((k, _freeze(v)) for k, v in sorted(obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    return obj  # str/int/float/bool/None already hashable

def _thaw(obj):
    """Best-effort reverse of _freeze to JSON-friendly shapes."""
    if isinstance(obj, tuple):
        # dict-like? (k, v) pairs
        if all(isinstance(x, tuple) and len(x) == 2 for x in obj):
            return {k: _thaw(v) for k, v in obj}
        # otherwise list-like
        return [_thaw(v) for v in obj]
    return obj

def _jsonify_key(k):
    """Convert frozen key back to JSON-friendly list/dict/str."""
    return _thaw(k)

def _sort_issue_pairs(issue_set: Set[Tuple[str, Any]]):
    """
    Sort (rule_id, key) pairs stably, by rule_id then a JSON string of the thawed key.
    This avoids tuple-vs-str comparisons.
    """
    def _k(pair):
        rid, k = pair
        return (rid or "", json.dumps(_thaw(k), sort_keys=True, ensure_ascii=False))
    return sorted(issue_set, key=_k)


# Node keys / helpers

def _node_key_from_node(node: dict):
    """Return a frozen, hashable node key."""
    targets = sorted(node.get("target", []) or [])
    if targets:
        return _freeze(("css", targets))
    xps = sorted(node.get("xpath", []) or [])
    if xps:
        return _freeze(("xpath", xps))
    html_snip = (node.get("html") or "")[:200]
    fs = (node.get("failureSummary") or "")[:200]
    return _freeze(("fp", (html_snip, len(fs))))


# Consistency matching

def _iou(a, b) -> float:
    if not a or not b: return 0.0
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"]+a["w"], a["y"]+a["h"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"]+b["w"], b["y"]+b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0: return 0.0
    area_a = (ax2-ax1)*(ay2-ay1)
    area_b = (bx2-bx1)*(by2-by1)
    return inter / float(area_a + area_b - inter)

def _rel_area_change(a, b) -> float:
    if not a or not b or not a.get("area") or not b.get("area"):
        return 1.0
    return abs(a["area"] - b["area"]) / max(a["area"], b["area"])

def compute_consistency(light_results: dict, dark_results: dict) -> Dict[str, Any]:
    """
    CONSISTENT := same region (IoU >= IOU_THRESHOLD OR small area delta) AND same rule_id.
    INCONSISTENT := everything else (including same region but different rule_id, moved, only-in-one-mode).
    Returns per-side sets of (rule_id, node_key) issue so we can filter per violation.
    """
    def _flatten(res):
        items = []
        for v in res.get("violations", []):
            rid = v.get("id")
            for n in v.get("nodes", []):
                items.append((rid, _node_key_from_node(n), n.get("__bbox")))  # key already frozen
        return items

    L = _flatten(light_results)
    D = _flatten(dark_results)

    def same_region(b1, b2) -> bool:
        if not b1 or not b2:
            return False
        iou = _iou(b1, b2)
        if iou >= IOU_THRESHOLD:
            return True
        return _rel_area_change(b1, b2) <= AREA_DELTA_THRESHOLD

    candidates = []  # (iou, (rid_l, kl), (rid_d, kd))
    rule_mismatch_light_issue = set()
    rule_mismatch_dark_issue  = set()

    for rid_d, kd, bd in D:
        best_same_id = (0.0, None)
        best_same_region = (0.0, None)
        for rid_l, kl, bl in L:
            if not same_region(bd, bl):
                continue
            iou = _iou(bd, bl)
            if rid_l == rid_d and iou > best_same_id[0]:
                best_same_id = (iou, (rid_l, kl))
            if iou > best_same_region[0]:
                best_same_region = (iou, (rid_l, kl))
        if best_same_id[1] is not None:
            candidates.append((best_same_id[0], best_same_id[1], (rid_d, kd)))
        elif best_same_region[1] is not None:
            rid_l2, kl2 = best_same_region[1]
            rule_mismatch_light_issue.add((rid_l2, kl2))
            rule_mismatch_dark_issue.add((rid_d, kd))

    candidates.sort(key=lambda t: t[0], reverse=True)
    used_light_issue = set()
    consistent_light_issue = set()
    consistent_dark_issue  = set()

    for _, (rid_l, kl), (rid_d, kd) in candidates:
        if (rid_l, kl) in used_light_issue: continue
        used_light_issue.add((rid_l, kl))
        consistent_light_issue.add((rid_l, kl))
        consistent_dark_issue.add((rid_d, kd))

    # Keys are already frozen and hashable
    all_light_issue = {(rid, k) for rid, k, _ in L}
    all_dark_issue  = {(rid, k) for rid, k, _ in D}

    inconsistent_light_issue = all_light_issue - consistent_light_issue
    inconsistent_dark_issue  = all_dark_issue  - consistent_dark_issue

    def _jsonify_pair(pair):
        rid, key = pair
        return [rid, _jsonify_key(key)]

    return {
        "consistent_light_issue":    [ _jsonify_pair(p) for p in _sort_issue_pairs(consistent_light_issue) ],
        "consistent_dark_issue":     [ _jsonify_pair(p) for p in _sort_issue_pairs(consistent_dark_issue) ],
        "inconsistent_light_issue":  [ _jsonify_pair(p) for p in _sort_issue_pairs(inconsistent_light_issue) ],
        "inconsistent_dark_issue":   [ _jsonify_pair(p) for p in _sort_issue_pairs(inconsistent_dark_issue) ],
        "rule_mismatch_light_issue": [ _jsonify_pair(p) for p in _sort_issue_pairs(rule_mismatch_light_issue) ],
        "rule_mismatch_dark_issue":  [ _jsonify_pair(p) for p in _sort_issue_pairs(rule_mismatch_dark_issue) ],
        "counts": {
            "consistent":           len(consistent_dark_issue),
            "inconsistent_light":   len(inconsistent_light_issue),
            "inconsistent_dark":    len(inconsistent_dark_issue),
            "rule_mismatch_issue":  min(len(rule_mismatch_light_issue), len(rule_mismatch_dark_issue)),
        }
    }


#  Style hints (screenshots)

def _issue_to_set(issue_json_list):
    out = set()
    for rid, key_json in issue_json_list or []:
        out.add((rid, _freeze(key_json)))
    return out

def build_style_hints_consistent_only(axe_results: dict, cons: dict, side: str) -> dict:
    assert side in ("light", "dark")
    keyname = "consistent_light_issue" if side == "light" else "consistent_dark_issue"
    cons_issue = _issue_to_set(cons.get(keyname, []))
    ordered = _sort_issue_pairs(cons_issue)
    return {
        "allowed_issue":   [ [rid, _jsonify_key(k)] for (rid, k) in ordered ],
        "consistent_issue":[ [rid, _jsonify_key(k)] for (rid, k) in ordered ],
    }

def build_style_hints_inconsistent_only(axe_results: dict, cons: dict, side: str) -> dict:
    assert side in ("light", "dark")
    keyname = "inconsistent_light_issue" if side == "light" else "inconsistent_dark_issue"
    inc_issue = _issue_to_set(cons.get(keyname, []))
    ordered = _sort_issue_pairs(inc_issue)
    return {
        "allowed_issue":   [ [rid, _jsonify_key(k)] for (rid, k) in ordered ],
        "consistent_issue":[],
    }


#  Highlight overlays

def highlight_all_violations(driver, axe_results: dict, style_hints: Optional[dict] = None) -> int:
    if not HIGHLIGHT_ALL_VIOLATIONS:
        return 0

    style_hints = style_hints or {}

    def _issue_to_py(s):
        out = set()
        for rid, key_json in s or []:
            out.add((rid, _freeze(key_json)))  # freeze, not tupleize
        return out

    ALLOWED    = _issue_to_py(style_hints.get("allowed_issue"))
    CONSISTENT = _issue_to_py(style_hints.get("consistent_issue"))

    has_allowed_filter = ("allowed_issue" in style_hints)

    STYLE_CONSISTENT = "3px solid #2563eb"
    impact_to_style = {
        "critical": "3px solid #e11d48",
        "serious":  "3px solid #f97316",
        "moderate": "3px solid #eab308",
        "minor":    "3px solid #9ca3af",
        None:       "3px solid #9ca3af",
        "unknown":  "3px solid #9ca3af",
    }

    def _node_key_from_node_local(node: dict):
        targets = sorted(node.get("target", []) or [])
        if targets: return _freeze(("css", targets))
        xps = sorted(node.get("xpath", []) or [])
        if xps: return _freeze(("xpath", xps))
        html_snip = (node.get("html") or "")[:200]
        fs = (node.get("failureSummary") or "")[:200]
        return _freeze(("fp", (html_snip, len(fs))))

    payload = []
    for v in axe_results.get("violations", []):
        rule_id = v.get("id") or "unknown"
        impact  = v.get("impact") or "unknown"
        default_style = impact_to_style.get(impact, impact_to_style["unknown"])
        for n in v.get("nodes", []):
            k = _node_key_from_node_local(n)   # frozen
            pair = (rule_id, k)

            if has_allowed_filter and (pair not in ALLOWED):
                continue

            style = STYLE_CONSISTENT if (pair in CONSISTENT) else default_style
            label = f"{rule_id}" + (" · consistent" if (pair in CONSISTENT) else f" ({impact})")
            payload.append({
                "rule": rule_id,
                "impact": impact,
                "style": style,
                "label": label,
                "targets": n.get("target", []) or [],
                "xpaths":  n.get("xpath", []) or [],
                "summary": (n.get("failureSummary") or "")[:500],
            })

    # JS overlay
    js = r"""
    (function(items){
      let container = document.querySelector('#axe-overlay-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'axe-overlay-container';
        container.style.position = 'absolute';
        container.style.left = '0';
        container.style.top = '0';
        container.style.width = '0';
        container.style.height = '0';
        container.style.zIndex = '2147483647';
        container.style.pointerEvents = 'none';
        document.documentElement.appendChild(container);

        const style = document.createElement('style');
        style.id = 'axe-overlay-style';
        style.textContent = `
          .axe-ov { position: absolute; box-sizing: border-box; pointer-events: none; }
          .axe-ov-label {
            pointer-events: auto; position: absolute; left: 0; top: 0; transform: translateY(-100%);
            max-width: 380px; padding: 2px 6px; font-family: ui-sans-serif, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
            font-size: 11px; line-height: 1.2; color: #111; background: rgba(255,255,255,0.92);
            border: 1px solid rgba(0,0,0,0.2); border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          }
        `;
        document.documentElement.appendChild(style);
      }

      function byXPath(xp) {
        try {
          const res = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
          const arr = []; for (let i=0;i<res.snapshotLength;i++) arr.push(res.snapshotItem(i));
          return arr;
        } catch(e) { return []; }
      }

      const map = new WeakMap();
      let outlinedCount = 0;

      function upsert(el, labelText, borderStyle, summary){
        const r = el.getBoundingClientRect();
        const overlayId = el.getAttribute('data-axe-ov-id') || (Math.random().toString(36).slice(2));
        el.setAttribute('data-axe-ov-id', overlayId);

        const cur = map.get(el);
        if (cur) {
          cur.label.textContent = labelText;
          cur.label.title = summary || '';
          cur.node.style.border = borderStyle;
          cur.node.style.left   = (window.scrollX + r.left) + 'px';
          cur.node.style.top    = (window.scrollY + r.top)  + 'px';
          cur.node.style.width  = Math.max(0, r.width) + 'px';
          cur.node.style.height = Math.max(0, r.height) + 'px';
          return false;
        }

        const ov = document.createElement('div');
        ov.className = 'axe-ov';
        ov.setAttribute('data-axe-overlay','true');
        ov.setAttribute('data-axe-for', overlayId);
        ov.style.left   = (window.scrollX + r.left) + 'px';
        ov.style.top    = (window.scrollY + r.top)  + 'px';
        ov.style.width  = Math.max(0, r.width) + 'px';
        ov.style.height = Math.max(0, r.height) + 'px';
        ov.style.border = borderStyle;
        ov.style.pointerEvents = 'none';

        const label = document.createElement('div');
        label.className = 'axe-ov-label';
        label.textContent = labelText;
        label.title = summary || '';
        label.style.boxShadow = '0 1px 2px rgba(0,0,0,0.25)';

        ov.appendChild(label);
        container.appendChild(ov);

        map.set(el, {node: ov, label});
        return true;
      }

      items.forEach(it => {
        const els = [];
        (it.targets || []).forEach(sel => {
          try { document.querySelectorAll(sel).forEach(el => els.push(el)); } catch(e){}
        });
        if (els.length === 0) (it.xpaths || []).forEach(xp => els.push(...byXPath(xp)));
        els.forEach(el => {
          if (!el || !(el instanceof Element)) return;
          const isNew = upsert(el, it.label, it.style, it.summary);
          if (isNew) outlinedCount++;
        });
      });

      if (!window.__axeOvReflowHook__) {
        window.__axeOvReflowHook__ = () => {
          const all = document.querySelectorAll('[data-axe-ov-id]');
          all.forEach(el => {
            const id = el.getAttribute('data-axe-ov-id');
            const ov = document.querySelector(`.axe-ov[data-axe-for="${id}"]`);
            if (!ov) return;
            const r = el.getBoundingClientRect();
            ov.style.left   = (window.scrollX + r.left) + 'px';
            ov.style.top    = (window.scrollY + r.top)  + 'px';
            ov.style.width  = Math.max(0, r.width) + 'px';
            ov.style.height = Math.max(0, r.height) + 'px';
          });
        };
        window.addEventListener('scroll', window.__axeOvReflowHook__, {passive:true});
        window.addEventListener('resize', window.__axeOvReflowHook__);
      }

      return outlinedCount;
    })
    """
    try:
        return int(driver.execute_script(f"return ({js})(arguments[0]);", payload) or 0)
    except Exception as e:
        print(f"[WARN] highlight_all_violations failed: {e}")
        return 0


#  Flattening (optional export)

def flatten_violations(axe_results: dict, *, mode: str, page_key: str, url: str) -> List[dict]:
    flat = []
    for v in axe_results.get("violations", []):
        rule_id     = v.get("id")
        impact      = v.get("impact")
        description = v.get("description")
        help_url    = v.get("helpUrl")
        tags        = v.get("tags", [])
        for node in v.get("nodes", []):
            flat.append({
                "mode": mode, "page_key": page_key, "url": url,
                "rule_id": rule_id, "impact": impact,
                "description": description, "help_url": help_url, "tags": tags,
                "targets": node.get("target", []), "xpaths": node.get("xpath", []),
                "html": node.get("html"),
                "failure_summary": node.get("failureSummary"),
                "bbox": node.get("__bbox"),
            })
    return flat

def flatten_violations_categorized_issue(axe_results: dict, *, mode: str, page_key: str, url: str,
                                         consistent_issue: Set[Tuple[str, Any]]) -> List[dict]:
    flat = []
    for v in axe_results.get("violations", []):
        rule_id     = v.get("id")
        impact      = v.get("impact")
        description = v.get("description")
        help_url    = v.get("helpUrl")
        tags        = v.get("tags", [])
        for node in v.get("nodes", []):
            k = _node_key_from_node(node)  # already frozen
            cat = "consistent" if (rule_id, k) in consistent_issue else "inconsistent"
            flat.append({
                "mode": mode, "page_key": page_key, "url": url,
                "rule_id": rule_id, "impact": impact,
                "description": description, "help_url": help_url, "tags": tags,
                "targets": node.get("target", []), "xpaths": node.get("xpath", []),
                "html": node.get("html"),
                "failure_summary": node.get("failureSummary"),
                "bbox": node.get("__bbox"),
                "category": cat
            })
    return flat


#  SCANNING
@dataclass
class ScanOutput:
    visited_urls: List[str]
    by_key_full: Dict[str, dict]
    all_flat_violations: List[dict]
    consistency_by_key: Dict[str, dict]

def scan_mode(mode: str, start_url: str, out_json_dir: str, out_shots_dir: str,
              follow_urls: List[str] = None,
              counterpart_by_key: Dict[str, dict] = None) -> ScanOutput:
    # random.seed(RANDOM_SEED)
    driver = setup_driver(prefers_color_scheme=mode)
    consistency_by_key: Dict[str, dict] = {}
    try:
        driver.get(start_url); wait_ready(driver)

        visited, by_key_full, all_flat = [], {}, []

        for step in range(1, STEPS + 1):
            if step > 1:
                if follow_urls and step-1 < len(follow_urls):
                    driver.get(follow_urls[step-1]); wait_ready(driver)
                else:
                    links = collect_internal_links(driver)
                    if not links: break
                    links = sorted(set(links))
                    driver.get(links[min(step-2, len(links)-1)]); wait_ready(driver)

            key = page_key(driver, step)
            visited.append(driver.current_url)

            # Run axe + enrich with bbox
            results = run_axe_full(driver)
            results = enrich_with_geometry(driver, results)

            # If counterpart provided (dark pass), compute consistency vs light
            if counterpart_by_key is not None:
                light_page = counterpart_by_key.get(key, {"violations": []})
                cons = compute_consistency(light_page, results)
                consistency_by_key[key] = cons
                save_json(os.path.join(out_json_dir, f"{key}__consistency.json"), cons)

            # Save per-page artifacts (raw JSON)
            save_json(os.path.join(out_json_dir, f"{key}__axe_{mode}.json"), results)
            save_json(os.path.join(out_json_dir, f"{key}__contrast_details_{mode}.json"), extract_cc_details(results))

            # Accumulate flat violations
            all_flat.extend(flatten_violations(results, mode=mode, page_key=key, url=driver.current_url))

            # Baseline highlight (impact colors) + screenshot
            try:
                outlined = highlight_all_violations(driver, results, style_hints=None)
            except Exception as e:
                print(f"[{mode}] highlight failed: {e}")
                outlined = 0
            capture_fullpage_png(driver, os.path.join(out_shots_dir, f"{key}__screenshot_{mode}.png"))

            by_key_full[key] = results
            print(f"[{mode.upper()}] {key} URL={driver.current_url} violations={len(results.get('violations', []))} outlined={outlined}")

        # Per-mode flat export (legacy raw) -> Json/
        save_json(os.path.join(out_json_dir, f"{mode.capitalize()}_all_violations.json"), all_flat)
        return ScanOutput(visited, by_key_full, all_flat, consistency_by_key)
    finally:
        driver.quit()


#  Recolor screenshots (consistent/inconsistent)

def recolor_light_screenshots(light: ScanOutput, dark: ScanOutput, shots_dir: str):
    driver = setup_driver(prefers_color_scheme="light")
    try:
        for key, light_results in light.by_key_full.items():
            cons = dark.consistency_by_key.get(key)
            if not cons:
                continue
            idx = _step_index_from_key(key)
            url = light.visited_urls[idx] if idx < len(light.visited_urls) else None
            if not url:
                continue

            # 1) consistent-only
            driver.get(url); wait_ready(driver)
            hints = build_style_hints_consistent_only(light_results, cons, side="light")
            try:
                highlight_all_violations(driver, light_results, style_hints=hints)
            except Exception as e:
                print(f"[LIGHT recolor consistent-only] highlight failed: {e}")
            capture_fullpage_png(driver, os.path.join(shots_dir, f"{key}__screenshot_light_consistent_only.png"))

            # 2) inconsistent-only
            driver.get(url); wait_ready(driver)
            hints = build_style_hints_inconsistent_only(light_results, cons, side="light")
            try:
                highlight_all_violations(driver, light_results, style_hints=hints)
            except Exception as e:
                print(f"[LIGHT recolor inconsistent-only] highlight failed: {e}")
            capture_fullpage_png(driver, os.path.join(shots_dir, f"{key}__screenshot_light_inconsistent_only.png"))
    finally:
        driver.quit()

def recolor_dark_screenshots(light: ScanOutput, dark: ScanOutput, shots_dir: str):
    driver = setup_driver(prefers_color_scheme="dark")
    try:
        for key, dark_results in dark.by_key_full.items():
            cons = dark.consistency_by_key.get(key)
            if not cons:
                continue
            idx = _step_index_from_key(key)
            url = dark.visited_urls[idx] if idx < len(dark.visited_urls) else None
            if not url:
                continue

            # 1) consistent-only
            driver.get(url); wait_ready(driver)
            hints = build_style_hints_consistent_only(dark_results, cons, side="dark")
            try:
                highlight_all_violations(driver, dark_results, style_hints=hints)
            except Exception as e:
                print(f"[DARK recolor consistent-only] highlight failed: {e}")
            capture_fullpage_png(driver, os.path.join(shots_dir, f"{key}__screenshot_dark_consistent_only.png"))

            # 2) inconsistent-only
            driver.get(url); wait_ready(driver)
            hints = build_style_hints_inconsistent_only(dark_results, cons, side="dark")
            try:
                highlight_all_violations(driver, dark_results, style_hints=hints)
            except Exception as e:
                print(f"[DARK recolor inconsistent-only] highlight failed: {e}")
            capture_fullpage_png(driver, os.path.join(shots_dir, f"{key}__screenshot_dark_inconsistent_only.png"))
    finally:
        driver.quit()


#  Run-level categorized JSON export (flat, per pair)

def export_run_level_categorized(light: ScanOutput, dark: ScanOutput, dest_dir: str):
    records: List[dict] = []
    keys = sorted(set(light.by_key_full.keys()) | set(dark.by_key_full.keys()))
    for key in keys:
        L = light.by_key_full.get(key, {"violations": []})
        D = dark.by_key_full.get(key,  {"violations": []})
        cons = dark.consistency_by_key.get(key)
        idx = _step_index_from_key(key)
        url_light = light.visited_urls[idx] if idx < len(light.visited_urls) else ""
        url_dark  = dark.visited_urls[idx]  if idx < len(dark.visited_urls)  else ""

        if cons:
            cons_light_issue = _issue_to_set(cons.get("consistent_light_issue", []))
            cons_dark_issue  = _issue_to_set(cons.get("consistent_dark_issue", []))
        else:
            cons_light_issue = set()
            cons_dark_issue  = set()

        records += flatten_violations_categorized_issue(L, mode="light", page_key=key, url=url_light, consistent_issue=cons_light_issue)
        records += flatten_violations_categorized_issue(D, mode="dark",  page_key=key, url=url_dark,  consistent_issue=cons_dark_issue)

    save_json(os.path.join(dest_dir, "All_violations_categorized.json"), records)


#  Grouped JSON export (by mode → category → rule)

def export_run_level_grouped(light: ScanOutput, dark: ScanOutput, dest_dir: str):
    def _collect_for_side(results_by_key: Dict[str, dict],
                          visited_urls: List[str],
                          cons_by_key: Dict[str, dict],
                          side: str):
        assert side in ("light", "dark")
        bucket = {"consistent": {"count": 0, "by_rule": {}},
                  "inconsistent": {"count": 0, "by_rule": {}}}

        for key, axe_results in results_by_key.items():
            cons = cons_by_key.get(key)
            idx = _step_index_from_key(key)
            url = visited_urls[idx] if idx < len(visited_urls) else ""
            if cons:
                if side == "light":
                    cons_issue = _issue_to_set(cons.get("consistent_light_issue", []))
                else:
                    cons_issue = _issue_to_set(cons.get("consistent_dark_issue", []))
            else:
                cons_issue = set()

            for v in axe_results.get("violations", []):
                rid = v.get("id")
                for n in v.get("nodes", []):
                    k = _node_key_from_node(n)  # already frozen
                    cat = "consistent" if (rid, k) in cons_issue else "inconsistent"
                    rec = {
                        "page_key": key, "url": url, "rule_id": rid,
                        "impact": v.get("impact"), "description": v.get("description"),
                        "help_url": v.get("helpUrl"), "targets": n.get("target", []),
                        "xpaths": n.get("xpath", []), "html": n.get("html"),
                        "failure_summary": n.get("failureSummary"), "bbox": n.get("__bbox"),
                        "mode": side, "category": cat
                    }
                    bucket[cat]["count"] += 1
                    bucket[cat]["by_rule"].setdefault(rid, []).append(rec)
        return bucket

    light_grouped = _collect_for_side(light.by_key_full, light.visited_urls, dark.consistency_by_key, "light")
    dark_grouped  = _collect_for_side(dark.by_key_full,  dark.visited_urls,  dark.consistency_by_key, "dark")

    summary = {
        "light": {"consistent": light_grouped["consistent"]["count"],
                  "inconsistent": light_grouped["inconsistent"]["count"]},
        "dark":  {"consistent": dark_grouped["consistent"]["count"],
                  "inconsistent": dark_grouped["inconsistent"]["count"]},
        "total": {"consistent": light_grouped["consistent"]["count"] + dark_grouped["consistent"]["count"],
                  "inconsistent": light_grouped["inconsistent"]["count"] + dark_grouped["inconsistent"]["count"]}
    }

    out = {"summary": summary, "light": light_grouped, "dark": dark_grouped}
    save_json(os.path.join(dest_dir, "All_violations_grouped.json"), out)


#  Application-level summary & flag

def _issue_json_to_tuple_set(issue_json_list):
    out = set()
    for rid, key_json in issue_json_list or []:
        out.add((rid, _freeze(key_json)))
    return out

def _merge_consistency_sets(cons: dict):
    return {
        "cons_l": _issue_json_to_tuple_set(cons.get("consistent_light_issue", [])),
        "cons_d": _issue_json_to_tuple_set(cons.get("consistent_dark_issue", [])),
        "inc_l":  _issue_json_to_tuple_set(cons.get("inconsistent_light_issue", [])),
        "inc_d":  _issue_json_to_tuple_set(cons.get("inconsistent_dark_issue", [])),
        "mis_l":  _issue_json_to_tuple_set(cons.get("rule_mismatch_light_issue", [])),
        "mis_d":  _issue_json_to_tuple_set(cons.get("rule_mismatch_dark_issue", [])),
    }

def _sum_counts_pagewise(cons_by_key: Dict[str, dict]) -> dict:
    totals = {
        "consistent_issue": 0,
        "inconsistent_light_issue": 0,
        "inconsistent_dark_issue": 0,
        "rule_mismatch_issue": 0,
        "pages_with_inconsistency": 0
    }
    for key, cons in cons_by_key.items():
        c = cons.get("counts", {}) or {}
        inc_sum = int(c.get("inconsistent_light", 0)) + int(c.get("inconsistent_dark", 0)) + int(c.get("rule_mismatch_issue", 0))
        if inc_sum > 0:
            totals["pages_with_inconsistency"] += 1
        totals["consistent_issue"]          += int(c.get("consistent", 0))
        totals["inconsistent_light_issue"]  += int(c.get("inconsistent_light", 0))
        totals["inconsistent_dark_issue"]   += int(c.get("inconsistent_dark", 0))
        totals["rule_mismatch_issue"]       += int(c.get("rule_mismatch_issue", 0))
    return totals

def _unique_sets_appwide(cons_by_key: Dict[str, dict]) -> dict:
    uniq = {
        "consistent_light_issue": set(), "consistent_dark_issue":  set(),
        "inconsistent_light_issue": set(), "inconsistent_dark_issue":  set(),
        "rule_mismatch_light_issue": set(), "rule_mismatch_dark_issue":  set(),
        "pages_with_inconsistency": set(),
    }
    for key, cons in cons_by_key.items():
        sets = _merge_consistency_sets(cons)
        if sets["inc_l"] or sets["inc_d"] or sets["mis_l"] or sets["mis_d"]:
            uniq["pages_with_inconsistency"].add(key)
        uniq["consistent_light_issue"]     |= sets["cons_l"]
        uniq["consistent_dark_issue"]      |= sets["cons_d"]
        uniq["inconsistent_light_issue"]   |= sets["inc_l"]
        uniq["inconsistent_dark_issue"]    |= sets["inc_d"]
        uniq["rule_mismatch_light_issue"]  |= sets["mis_l"]
        uniq["rule_mismatch_dark_issue"]   |= sets["mis_d"]
    return uniq

def _per_rule_counts(issue: set) -> Dict[str, int]:
    out = {}
    for rid, _ in issue:
        out[rid] = out.get(rid, 0) + 1
    return out

def export_application_summary(light: ScanOutput, dark: ScanOutput, run_dir: str, app: str, start_url: str):
    cons_by_key = dark.consistency_by_key

    pagewise = _sum_counts_pagewise(cons_by_key)
    uniq = _unique_sets_appwide(cons_by_key)
    unique_totals = {
        "consistent_issue": len(uniq["consistent_light_issue"]) + len(uniq["consistent_dark_issue"]),
        "inconsistent_issue": len(uniq["inconsistent_light_issue"]) + len(uniq["inconsistent_dark_issue"]),
        "rule_mismatch_issue": min(len(uniq["rule_mismatch_light_issue"]), len(uniq["rule_mismatch_dark_issue"])),
        "pages_with_inconsistency": len(uniq["pages_with_inconsistency"]),
    }
    per_rule_unique_inconsistent = _per_rule_counts(uniq["inconsistent_light_issue"] | uniq["inconsistent_dark_issue"])
    is_application_inconsistent = (unique_totals["inconsistent_issue"] > 0) or (unique_totals["rule_mismatch_issue"] > 0)

    out = {
        "app": app,
        "start_url": start_url,
        "summary": {
            "pagewise_sums": pagewise,
            "pages_with_inconsistency": sorted(list(uniq["pages_with_inconsistency"])),
            "is_application_inconsistent": is_application_inconsistent
        }
    }
    save_json(os.path.join(run_dir, "Application_summary.json"), out)


URLS = [
    "https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/logging-format-interpolation.html",
    "https://pylint.readthedocs.io/en/latest/development_guide/how_tos/transform_plugins.html",
    "https://pylint.readthedocs.io/en/latest/whatsnew/2/2.11/summary.html#new-checkers",
    "https://pylint.readthedocs.io/en/latest/whatsnew/1/1.8/summary.html",
]

# Optional: keep first occurrence if duplicates exist
URLS = list(dict.fromkeys(URLS))



def main():
    # Use the first URL as the start page; the rest will be followed exactly in order.
    assert URLS, "URLS must contain at least one URL."
    start_url = URLS[0]
    more_urls = URLS[1:]

    # Make the run step count exactly the number of provided URLs
    global STEPS
    STEPS = len(URLS)

    # Derive the app name the same way you do now (or your new clean way)
    # app = urlparse(start_url).netloc.replace("www.", "")
    app = urlparse(start_url).netloc.replace("www.", "").split('.')[0]
    run_dir   = mkdir_clean(os.path.join(OUT_ROOT, app))
    json_dir  = mkdir_clean(os.path.join(run_dir, "Json"))
    shots_dir = mkdir_clean(os.path.join(run_dir, "Screenshots"))

    print("=== LIGHT SCAN ===")
    # Light pass: start at first URL, then strictly follow the list you passed
    light = scan_mode("light", start_url, json_dir, shots_dir,
                      follow_urls=more_urls)

    print("\n=== DARK SCAN ===")
    # Dark pass: follow the SAME ordered list for pairing and consistent page_key
    dark  = scan_mode("dark",  start_url, json_dir, shots_dir,
                      follow_urls=more_urls,
                      counterpart_by_key=light.by_key_full)

    print("\n=== RECOLOR PASSES ===")
    recolor_light_screenshots(light, dark, shots_dir)
    print("dark mode")
    recolor_dark_screenshots(light, dark, shots_dir)

    # Combined flat export for analysis -> Json/
    all_flat = light.all_flat_violations + dark.all_flat_violations
    save_json(os.path.join(json_dir, "All_violations_combined.json"), all_flat)

    # Run-level exports
    export_run_level_categorized(light, dark, json_dir)
    export_run_level_grouped(light, dark, json_dir)

    # Application-level summary -> app root
    export_application_summary(light, dark, run_dir, app=app, start_url=start_url)

    print("\n=== RUN COMPLETE ===")
    print(f"JSONs:        {json_dir}")
    print(f"Screenshots:  {shots_dir}")
    print(f"Summary:      {os.path.join(run_dir, 'Application_summary.json')}")


if __name__ == "__main__":
    main()






