
'''
gemini api model: gemini-2.5-pro

Compare the screenshots pairs of web-application pair in light and dark mode
aesthetic to detect the inconsistency.

Inconsistency such as invisible text, icon in dark mode.

'''

# Import
import os
import time
import base64
import json
import re
import cv2
import traceback
import pandas as pd
from datetime import datetime
from tqdm import tqdm
# import google.generativeai as genai
import google.generativeai as genai

# Please pass your apikey
genai.configure(api_key=" ")


log_rows = []


FEWSHOT_EXAMPLES = [
    {"type": "Consistent", "light": "example/cons1_light.png", "dark": "example/cons1_dark.png"},
    {"type": "Consistent", "light": "example/cons2_light.png", "dark": "example/cons2_dark.png"},
    {"type": "Inconsistent", "light": "example/incons1_light.png", "dark": "example/incons1_dark.png"},
    {"type": "Inconsistent", "light": "example/incons2_light.png", "dark": "example/incons2_dark.png"}
]

def build_fewshot_prompt(light_img_path, dark_img_path):
    contents = [SYSTEM_PROMPT]

    # Add few-shot examples
    for ex in FEWSHOT_EXAMPLES:
        with open(ex["light"], "rb") as f1, open(ex["dark"], "rb") as f2:
            contents.extend([
                f"Example ({ex['type']}): First is light mode, second is dark mode.",
                {
                    "mime_type": "image/png",
                    "data": f1.read()
                },
                {
                    "mime_type": "image/png",
                    "data": f2.read()
                },
                f"Label: {ex['type']}"
            ])

    # Add actual test pair
    with open(light_img_path, "rb") as f1, open(dark_img_path, "rb") as f2:
        contents.extend([
            "Now analyze this new pair:",
            {
                "mime_type": "image/png",
                "data": f1.read()
            },
            {
                "mime_type": "image/png",
                "data": f2.read()
            },
            "Return the JSON response as specified."
        ])

    return contents
# Prompt
SYSTEM_PROMPT = """
You are a senior UI/UX designer and web accessibility expert with over 10 years of experience. You are well-versed in:
Dark mode design principles
WCAG 2.1 accessibility guidelines
ISO 9241-210 human-centered design principles
UI consistency standards across light and dark themes

Your task is to carefully analyze a pair of screenshots from the same application — one in light mode and one in dark mode — and identify any visual or accessibility inconsistencies in the dark mode version.

You will first see example pairs labeled as "Consistent" or "Inconsistent".
Learn the patterns from these examples.
Each pair contains:\n
- First image: Light mode\n
- Second image: Dark mode\n\n
Learn from these before analyzing the final pair.

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




# to extract bounding boxes and verdict from gemini response text
def extract_boxes_from_text(response_text):
    if not response_text.strip():
        print(" Warning: Empty response received from Gemini.")
        return [], "", ""

    # print("\n Raw Gemini response:")
    print(response_text)

    #  Remove Markdown-style code block if present
    if response_text.strip().startswith("```json"):
        response_text = response_text.strip()
        response_text = response_text.lstrip("```json").rstrip("```").strip()

    try:
        data = json.loads(response_text)
        issues = data.get("issues", [])
        box_label_pairs = []
        for issue in issues:
            label = issue.get("description", "Issue")
            coords = issue.get("bounding_box", [])
            if len(coords) == 4:
                box_label_pairs.append({"coords": tuple(coords), "label": label})
        return box_label_pairs, data.get("verdict", ""), data.get("summary", "")
    except json.JSONDecodeError as e:
        print(f" JSON parsing error: {e}")
        return [], "", ""


def draw_bounding_boxes(image_path, boxes, output_path):
    img = cv2.imread(image_path)

    if img is None:
        print(f" Error loading image at {image_path}")
        return

    for box in boxes:
        coords = box["coords"]
        label = box["label"]

        # Validate that coords are all integers and not None
        if not coords or len(coords) != 4 or any(c is None for c in coords):
            print(f" Skipping box with invalid coordinates: {coords}")
            continue

        x1, y1, x2, y2 = map(int, coords)
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
        "Start Time": datetime.fromtimestamp(start).strftime("%Y-%m-%d %H:%M:%S"),
        "End Time": datetime.fromtimestamp(end).strftime("%Y-%m-%d %H:%M:%S"),
        "Duration (sec)": duration,
        "Status": status,
        "Verdict": verdict,
        "Summary": summary
    })


def call_gemini_vision(light_img_path, dark_img_path):
    model = genai.GenerativeModel('gemini-2.5-pro')  # safer than preview model

    contents = build_fewshot_prompt(light_img_path, dark_img_path)

    response = model.generate_content(contents)

    return response.text if hasattr(response, "text") else ""



ROOT_DIR = "sample_dataset/"
def run_inconsistency_detection(INPUT_FOLDER, OUTPUT_FOLDER, LOG_PATH):
    files = sorted(os.listdir(INPUT_FOLDER))
    light_files = [f for f in files if f.endswith("_light.png")]

    for light_file in tqdm(light_files, desc=f"Processing {INPUT_FOLDER}"):
        dark_file = light_file.replace("_light.png", "_dark.png")
        image_id = light_file.replace("_light.png", "")

        light_path = os.path.join(INPUT_FOLDER, light_file)
        dark_path = os.path.join(INPUT_FOLDER, dark_file)

        if not os.path.exists(dark_path):
            print(f"{image_id}: dark image missing")
            continue

        try:
            start = time.time()

            gemini_output = call_gemini_vision(light_path, dark_path)

            result_path = os.path.join(OUTPUT_FOLDER, f"{image_id}_result.txt")
            with open(result_path, "w") as f:
                f.write(gemini_output)

            boxes, verdict, summary = extract_boxes_from_text(gemini_output)

            if boxes:
                annotated_path = os.path.join(OUTPUT_FOLDER, f"{image_id}_annotated.png")
                draw_bounding_boxes(dark_path, boxes, annotated_path)

            log_result(image_id, start, time.time(), "success", verdict, summary)

        except Exception as e:
            log_result(image_id, start, time.time(), f"error: {str(e)}")
            print(f"Error in {image_id}:\n{traceback.format_exc()}")

    pd.DataFrame(log_rows).to_excel(LOG_PATH, index=False)
    print(f"Log saved to {LOG_PATH}")

def process_dataset(dataset_path):
    input_folder = os.path.join(dataset_path, "input")
    output_folder = os.path.join(dataset_path, "fewshot_output")

    os.makedirs(output_folder, exist_ok=True)

    log_path = os.path.join(output_folder, "log.xlsx")

    # reset log for each dataset
    global log_rows
    log_rows = []

    run_inconsistency_detection(input_folder, output_folder, log_path)

def process_all_datasets():
    datasets = sorted(os.listdir(ROOT_DIR))  # alphabetical order

    for dataset in datasets:
        dataset_path = os.path.join(ROOT_DIR, dataset)

        # skip files, only directories
        if not os.path.isdir(dataset_path):
            continue

        print(f"\nProcessing dataset: {dataset}")

        input_path = os.path.join(dataset_path, "input")

        # skip if no input folder
        if not os.path.exists(input_path):
            print(f"Skipping {dataset}, no input folder found")
            continue

        process_dataset(dataset_path)

if __name__ == "__main__":
    process_all_datasets()