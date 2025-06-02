'''
claude api model: claude-opus-4-20250514

Compare the screenshots pairs of web-application pair in light and dark mode
aesthetic to detect the inconsistency.

Inconsistency such as invisible text, icon in dark mode.

'''



# Import
import re
import os
import time
import base64
import json
import cv2
import traceback
import pandas as pd
from datetime import datetime
from tqdm import tqdm
import anthropic

# Please pass your apikey
client = anthropic.Anthropic(api_key="")

# Pass your image folder with light and dark mode screenshot
INPUT_FOLDER = "/llm_api/claude_api/dataset/input"
# Folder to save outputs and logs
OUTPUT_FOLDER = "/llm_api/claude_api/dataset/output"
# Create output folder if it doesn't exist
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
# Path to Excel log file
LOG_PATH = os.path.join(OUTPUT_FOLDER, "log.xlsx")

# List to store log data for all image pairs
log_rows = []

# Prompt
SYSTEM_PROMPT = """
You are a senior UI/UX designer and web accessibility expert with over 10 years of experience. You are well-versed in:
Dark mode design principles
WCAG 2.1 accessibility guidelines
ISO 9241-210 human-centered design principles
UI consistency standards across light and dark themes

Your task is to carefully analyze a pair of screenshots from the same application — one in light mode and one in dark mode — and identify any visual or accessibility inconsistencies in the dark mode version.

Please perform a side-by-side comparison and assess the dark mode screenshot across the following four categories:
Text visibility and contrast
Borders, edges, or separators
Icons or graphical elements
Dark mode consistency

Output Instructions:
Return a structured JSON output using this format:
{
 "issues": [
  {
   "category": "<One of: 'Text', 'Borders', 'Icons', 'Conversion'>",
   "description": "<Clear explanation of the inconsistency>",
   "bounding_box": [x1, y1, x2, y2]
  }
 ],
 "verdict": "<One of: 'Consistent', 'Inconsistent'>",
 "summary": "<One-sentence justification of the verdict>"
}

If no issues are found, return:
{
 "issues": [],
 "verdict": "Consistent",
 "summary": "No accessibility or UX issues were detected in the dark mode screenshot."
}
"""

# to encode an image to base64 format for API input
def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

# extract bounding boxes and verdict from response text
def extract_boxes_from_text(response_text):
    try:
        # Check for empty or invalid response
        if not response_text or response_text.strip() == "":
            print("Claude returned an empty response.")
            return [], "", ""

        # Extract JSON block from text using regex
        json_match = re.search(r'{\s*"issues":\s*\[.*?\]\s*,\s*"verdict":\s*".*?",\s*"summary":\s*".*?"\s*}', response_text, re.DOTALL)
        if not json_match:
            print("No valid JSON block found in the response.")
            print(f" Raw response text:\n{response_text}\n")
            return [], "", ""

        json_str = json_match.group(0)

        # Parse the extracted JSON string
        data = json.loads(json_str)

        # Extract issues and format bounding boxes
        issues = data.get("issues", [])
        box_label_pairs = []
        for issue in issues:
            label = issue.get("description", "Issue")
            coords = issue.get("bounding_box", [])
            if len(coords) == 4:
                box_label_pairs.append({"coords": tuple(coords), "label": label})

        verdict = data.get("verdict", "")
        summary = data.get("summary", "")
        return box_label_pairs, verdict, summary

    except json.JSONDecodeError as e:
        print(f" JSON parsing error: {e}")
        print(f" Extracted JSON string:\n{json_str}\n")
        return [], "", ""

# draw bounding boxes on the image and save it
def draw_bounding_boxes(image_path, boxes, output_path):
    img = cv2.imread(image_path)
    for box in boxes:
        x1, y1, x2, y2 = box["coords"]
        label = box["label"]
        # draw rectangle and label
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(img, label, (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    # Save annotated image
    cv2.imwrite(output_path, img)

# log the result for a given image pair
def log_result(image_id, start, end, status, verdict="", summary=""):
    duration = round(end - start, 2)
    log_rows.append({
        "Image ID": image_id,
        "Status": status,
        "Verdict": verdict,
        "Start Time": datetime.fromtimestamp(start).strftime("%Y-%m-%d %H:%M:%S"),
        "End Time": datetime.fromtimestamp(end).strftime("%Y-%m-%d %H:%M:%S"),
        "Duration (sec)": duration,
        "Summary": summary
    })

# call claude
def call_claude(light_image_path, dark_image_path):
    try:
        light_b64 = encode_image_to_base64(light_image_path)
        dark_b64 = encode_image_to_base64(dark_image_path)

        response = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=1200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": light_b64,
                            },
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": dark_b64,
                            },
                        },
                        {"type": "text", "text": "Please compare the above screenshots and return the JSON result."}
                    ],
                }
            ],
        )

        if not response or not response.content:
            print("Claude API returned no content.")
            return ""

        return response.content[0].text.strip()

    except Exception as e:
        print(f" Claude API call failed: {e}")
        return ""

# inconsistency detection
def process_all_pairs():
    files = sorted(os.listdir(INPUT_FOLDER))
    light_files = [f for f in files if f.endswith("_light.png")]

    for light_file in tqdm(light_files, desc="Processing image pairs"):
        dark_file = light_file.replace("_light.png", "_dark.png")
        image_id = light_file.replace("_light.png", "")
        light_path = os.path.join(INPUT_FOLDER, light_file)
        dark_path = os.path.join(INPUT_FOLDER, dark_file)

        if not os.path.exists(dark_path):
            print(f" {image_id}: dark image missing")
            continue

        start = time.time()
        try:
            claude_output = call_claude(light_path, dark_path)

            # Save raw output for inspection
            result_path = os.path.join(OUTPUT_FOLDER, f"{image_id}_claude_raw_output.txt")
            with open(result_path, "w") as f:
                f.write(claude_output)

            boxes, verdict, summary = extract_boxes_from_text(claude_output)

            if boxes:
                annotated_path = os.path.join(OUTPUT_FOLDER, f"{image_id}_annotated.png")
                draw_bounding_boxes(dark_path, boxes, annotated_path)

            log_result(image_id, start, time.time(), "success", verdict, summary)

        except Exception as e:
            log_result(image_id, start, time.time(), f"error: {str(e)}")
            print(f" Error in {image_id}:\n{traceback.format_exc()}")

        time.sleep(0.5)

    log_df = pd.DataFrame(log_rows)
    log_df.to_excel(LOG_PATH, index=False)
    print(f"\n Log saved to {LOG_PATH}")

# run
if __name__ == "__main__":
    process_all_pairs()