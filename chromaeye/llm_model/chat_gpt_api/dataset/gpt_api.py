'''
Gpt api model: "gpt-4o"

Compare the screenshots pairs of web-application pair in light and dark mode
aesthetic to detect the inconsistency.

Inconsistency such as invisible text, icon in dark mode.

'''

# Import
import os                       # For interacting with the file system
import time                     # For measuring execution time
import base64                   # For encoding images in base64 format
import json                     # For parsing and generating JSON
import cv2                      # For image processing (OpenCV)
import traceback                # For printing detailed error traces
import pandas as pd             # For data manipulation and exporting logs
from datetime import datetime   # For timestamp formatting
from tqdm import tqdm           # For displaying progress bars
from openai import OpenAI       # OpenAI Python SDK for GPT-4o


# Please pass your apikey
client = OpenAI(api_key="")
# Pass your image folder with light and dark mode screenshot
INPUT_FOLDER = "/llm_model/chat_gpt_api/dataset/input"
# Folder to save outputs and logs
OUTPUT_FOLDER = "/llm_model/gpt_api/dataset/output"
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
        #  clean if the output starts with a Markdown-style code block
        if response_text.strip().startswith("```json"):
            response_text = response_text.strip()
            response_text = response_text.lstrip("```json").rstrip("```").strip()

        # parse JSON
        data = json.loads(response_text)

        issues = data.get("issues", []) # List of detected issues
        box_label_pairs = []
        for issue in issues:
            label = issue.get("description", "Issue")
            coords = issue.get("bounding_box", [])
            if len(coords) == 4:
                box_label_pairs.append({"coords": tuple(coords), "label": label})
        return box_label_pairs, data.get("verdict", ""), data.get("summary", "")

    except json.JSONDecodeError as e:
        print(" JSON parsing error:", e)
        print(" Raw GPT Output:\n", response_text)
        # Return empty in case of failure
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

# send image pair to GPT-4o with vision and get structured result
def call_gpt(light_img_b64, dark_img_b64):
    response = client.chat.completions.create(
        model="gpt-4o",

        # let's experiment with new model
        # model = "gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Please analyze these screenshots. First is light mode, second is dark mode."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{light_img_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{dark_img_b64}"}}
            ]}
        ],
        max_tokens=1200,
    )
    # Return gpt's raw response
    return response.choices[0].message.content

# inconsistency detection
def inconsistency_detection():
    # List all input files
    files = sorted(os.listdir(INPUT_FOLDER))
    # Filter light mode files
    light_files = [f for f in files if f.endswith("_light.png")]

    for light_file in tqdm(light_files, desc="Processing image pairs"):
        dark_file = light_file.replace("_light.png", "_dark.png")
        image_id = light_file.replace("_light.png", "")
        light_path = os.path.join(INPUT_FOLDER, light_file)
        dark_path = os.path.join(INPUT_FOLDER, dark_file)

        if not os.path.exists(dark_path):
            print(f" {image_id}: dark image missing")
            continue

        try:
            start = time.time()
            # Encode both light and dark images
            light_b64 = encode_image_to_base64(light_path)
            dark_b64 = encode_image_to_base64(dark_path)

            # Send to gptapi and get response
            gpt_output = call_gpt(light_b64, dark_b64)

            # Save raw GPT output
            result_path = os.path.join(OUTPUT_FOLDER, f"{image_id}_result.txt")
            with open(result_path, "w") as f:
                f.write(gpt_output)

            # Extract bounding boxes, verdict, and summary
            boxes, verdict, summary = extract_boxes_from_text(gpt_output)
            if boxes:
                annotated_path = os.path.join(OUTPUT_FOLDER, f"{image_id}_annotated.png")
                draw_bounding_boxes(dark_path, boxes, annotated_path)

            # Log success
            log_result(image_id, start, time.time(), "success", verdict, summary)

        except Exception as e:
            # Log any error
            log_result(image_id, start, time.time(), f"error: {str(e)}")
            print(f" Error in {image_id}:\n{traceback.format_exc()}")

        # Delay to respect API rate limits

    # Write log to Excel
    log_df = pd.DataFrame(log_rows)
    log_df.to_excel(LOG_PATH, index=False)
    print(f"\n Log saved to {LOG_PATH}")

# run
if __name__ == "__main__":
    inconsistency_detection()
