'''
Chroma eye
Detect inconsistency in application that support:

- application that support light and dark mode
- application support light and dark mode with toggle button
- application based on system preference
- application, used extension to convert into the dark mode

Chroma eye take the light and dark mode screenshot as an input and find the inconsistency between the light and dark mode.
1. edge_based_inconsistency
2. object based inconsistency
3. partial conversion
4. text based inconsistency
    a. invisible text
    b. missing text

    # add path to

'''

import shutil
import json
import os
from tqdm import tqdm
from collections import defaultdict
from typing import List, Dict, Any

from chromaeye.chroma_detection.edge_based_detection.edge_based import edge_inconsistency
from chromaeye.chroma_detection.object_based_detection.object_based_detection import icon_inconsistency
from chromaeye.chroma_detection.partial_conversion_detection.partial_conversion import partial_conversion_inconsistency
from chromaeye.chroma_detection.text_based_detection.invisible_text import invisible_text_inconsistency
from chromaeye.chroma_detection.text_based_detection.missing_text import missing_text


def create_folder(folder_name):
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)
    return folder_name


def load_json(json_path: str) -> Dict[str, Any]:
    """Load JSON file."""
    # code update, november 18
    # Ticket: I-TI3,
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found at path: {json_path}")
    with open(json_path, 'r') as f:
        return json.load(f)


# detect the edge and text inconsistency
def edge_text_inconsistency_detection(image_dir, json_dir, output_dir):
    # 1 Edge Inconsistency
    edge_inconsistency_output_folder = create_folder(os.path.join(output_dir, 'edge_inconsistency'))
    edgeld = create_folder(os.path.join(edge_inconsistency_output_folder, 'edge_overlay'))
    missing_edges = create_folder(os.path.join(edge_inconsistency_output_folder, 'missing_edges'))

    # 2 Text Inconsistency
    text_inconsistency_output_folder = create_folder(os.path.join(output_dir, 'text_inconsistency'))
    missing_text_output_folder = create_folder(os.path.join(text_inconsistency_output_folder, 'missing_text'))
    invisible_text_output_folder = create_folder(os.path.join(text_inconsistency_output_folder, 'invisible_text'))

    # Initialize summaries for each type
    edge_inconsistency_detection = []
    invisible_text_detection = []
    missing_text_detection = []

    # Sort files in ascending order
    files = sorted(
        [f for f in os.listdir(image_dir) if f.endswith('light.png')],
        key=lambda x: int(x.split('light')[0]) if x.split('light')[0].isdigit() else x
    )

    for filename in tqdm(files):
        try:
            # Define base filename
            base_filename = filename.replace('light.png', '')
            id = base_filename.split("_")[0]

            # Input files
            light_image_file = os.path.join(image_dir, filename)
            dark_image_file = os.path.join(image_dir, filename.replace('light', 'dark'))

            # JSON paths
            light_json_file = os.path.join(json_dir, f"{base_filename}light.json")
            dark_json_file = os.path.join(json_dir, f"{base_filename}dark.json")

            '''Output directory'''
            # 1.Edge Inconsistency
            edge_overlay = os.path.join(edgeld, f"{base_filename}_overlay.png")
            problematic_edge = os.path.join(missing_edges, f"{base_filename}_problematic_area.png")

            # 2.Text Inconsistency

            # a. Invisible text
            invisible_text_image = os.path.join(invisible_text_output_folder, f"{base_filename}invisible.png")
            invisible_text_json = os.path.join(invisible_text_output_folder, f"{base_filename}invisible.json")

            # b. Missing text
            missing_text_image = os.path.join(missing_text_output_folder, f"{base_filename}missing.png")
            missing_text_json = os.path.join(missing_text_output_folder, f"{base_filename}missing.json")

            '''Inconsistency detection'''

            # 1. Edge Inconsistency
            edge_output = edge_inconsistency(
                light_image_file,
                dark_image_file,
                edge_overlay,
                problematic_edge
            )

            # text inconsistency
            # a. invisible text inconsistencies
            invisible_text_output = invisible_text_inconsistency(
                light_image_file,
                dark_image_file,
                light_json_file,
                dark_json_file,
                invisible_text_image,
                invisible_text_json
            )

            # b.  missing text inconsistencies
            missing_text_output = missing_text(
                light_image_file,
                dark_image_file,
                light_json_file,
                dark_json_file,
                missing_text_image,
                missing_text_json
            )

            '''Add to respective summaries'''

            # get the scroll_percentage

            def scroll_percentage(basefilename: str) -> int:
                scroll_value = int(basefilename.split("_")[-2])
                return scroll_value

            # 1. Edge Inconsistency
            if edge_output:
                edge_inconsistency_detection.append({
                    "id": id,
                    "file": base_filename,
                    "scroll_percentage": scroll_percentage(base_filename),
                    "image_directory": edge_output
                })

            # 2. Text Inconsistency
            # a. Invisible text
            if invisible_text_output:
                invisible_text_detection.append({
                    "id": id,
                    "file": base_filename,
                    "scroll_percentage": scroll_percentage(base_filename),
                    "invisible_text_summary": invisible_text_output
                })

            # b. Missing text
            if missing_text_output:
                missing_text_detection.append({
                    "id": id,
                    "file": base_filename,
                    "scroll_percentage": scroll_percentage(base_filename),
                    "missing_text_summary": missing_text_output
                })

        except Exception as e:
            print(f"Error processing file {base_filename}: {e}")

    # sort the file name to save the result in ascending order
    edge_inconsistency_detection.sort(key=lambda x: x['file'])
    invisible_text_detection.sort(key=lambda x: x['file'])
    missing_text_detection.sort(key=lambda x: x['file'])

    # path to save the result of each inconsistency type
    edge_summary_path = os.path.join(edge_inconsistency_output_folder, 'edge_inconsistency.json')
    invisible_text_summary_path = os.path.join(invisible_text_output_folder, 'invisible_text.json')
    missing_text_summary_path = os.path.join(missing_text_output_folder, 'missing_text.json')

    with open(edge_summary_path, 'w') as edges_file:
        json.dump(edge_inconsistency_detection, edges_file, indent=4)

    with open(missing_text_summary_path, 'w') as missing_file:
        json.dump(missing_text_detection, missing_file, indent=4)

    with open(invisible_text_summary_path, 'w') as invisible_file:
        json.dump(invisible_text_detection, invisible_file, indent=4)

    return edge_inconsistency_detection, invisible_text_detection, missing_text_detection


# detect the partial and icon inconsistency
def partial_conversion_icon_detection(image_dir, uied_json_dir, output_dir):
    """Process a batch of images and JSON files for invisible and missing text checks, with separate summaries."""

    # Create output folder

    # 3. Partial Conversion
    partial_conversion_output_folder = create_folder(os.path.join(output_dir, 'partial_conversion_inconsistency'))

    # 4. Icon Inconsistency
    icon_inconsistency_output_folder = create_folder(os.path.join(output_dir, 'icon_inconsistency'))

    # Initialize summaries
    partial_conversion_detection = []
    invisible_icon_detection = []

    # Sort files in ascending order
    files = sorted(
        [f for f in os.listdir(image_dir) if f.endswith('light.png')],
        key=lambda x: int(x.split('light')[0]) if x.split('light')[0].isdigit() else x
    )

    for filename in tqdm(files):
        try:
            # Define base filename
            base_filename = filename.replace('light.png', '')
            id = base_filename.split("_")[0]

            # Input files
            light_image_file = os.path.join(image_dir, filename)
            dark_image_file = os.path.join(image_dir, filename.replace('light', 'dark'))

            uied_json = os.path.join(uied_json_dir, f"{base_filename}light.json")

            '''Output directory'''

            # 3. Partial conversion
            partial_conversion_image = os.path.join(partial_conversion_output_folder,
                                                    f"{base_filename}partial_conversion.png")

            # 4. Icon Inconsistency
            icon_inconsistency_image = os.path.join(icon_inconsistency_output_folder,
                                                    f"{base_filename}icon_inconsistency.png")

            '''Inconsistency detection'''
            # 3. Partial Conversion Inconsistency
            partial_conversion_output = partial_conversion_inconsistency(
                light_image_file,
                dark_image_file,
                uied_json,
                partial_conversion_image
            )

            # 4. Icon inconsistency
            invisible_icon_output = icon_inconsistency(
                light_image_file,
                dark_image_file,
                uied_json,
                icon_inconsistency_image
            )

            '''Add to respective summaries'''

            # get the scroll_percentage

            def scroll_percentage(basefilename: str) -> int:
                scroll_value = int(basefilename.split("_")[-2])
                return scroll_value

            if partial_conversion_output:
                partial_conversion_detection.append({
                    "id": id,
                    "file": base_filename,
                    "scroll_percentage": scroll_percentage(base_filename),
                    'partial_conversion_summary': partial_conversion_output
                })

            if invisible_icon_output:
                invisible_icon_detection.append({
                    "id": id,
                    "file": base_filename,
                    "scroll_percentage": scroll_percentage(base_filename),
                    "invisible_icon": invisible_icon_output
                })

        except Exception as e:
            print(f"Error processing file {base_filename}: {e}")

    # Sort summaries in ascending order by file name

    partial_conversion_detection.sort(key=lambda x: x['file'])
    invisible_icon_detection.sort(key=lambda x: x['file'])

    # path to save the inconsistency result
    partial_conversion_summary_path = os.path.join(partial_conversion_output_folder,
                                                   "partial_conversion_inconsistency.json")
    invisible_icon_summary_path = os.path.join(icon_inconsistency_output_folder, "icon_inconsistency.json")

    with open(partial_conversion_summary_path, 'w') as partial_conversion_inconsistency_file:
        json.dump(partial_conversion_detection, partial_conversion_inconsistency_file, indent=4)

    with open(invisible_icon_summary_path, "w") as invisible_icon_file:
        json.dump(invisible_icon_detection, invisible_icon_file, indent=4)

    return partial_conversion_detection, invisible_icon_detection


# inconsistency detection
def inconsistency_detection(image_dir, json_dir, uied_image_dir, uied_json_dir, screenshot_mata_dir, output_dir):
    screenshot_meta_information = load_json(screenshot_mata_dir)
    print("edge and text inconsistency detection started....")
    edge_inconsistency_detection, invisible_text_detection, missing_text_detection = edge_text_inconsistency_detection(
        image_dir, json_dir, output_dir)
    print("edge and text inconsistency detection completed....")

    print("partial conversion and icon inconsistency detection started")
    partial_conversion_detection, invisible_icon_detection = partial_conversion_icon_detection(uied_image_dir,
                                                                                               uied_json_dir,
                                                                                               output_dir)

    inconsistency_report_path = os.path.join(output_dir, "inconsistency.json")

    report = generate_inconsistency_report(screenshot_meta_information, edge_inconsistency_detection,
                                           invisible_text_detection, missing_text_detection,
                                           partial_conversion_detection, invisible_icon_detection)

    print('Inconsistency detection complete')

    with open(inconsistency_report_path, 'w') as invisible_file:
        json.dump(report, invisible_file, indent=4)


def generate_inconsistency_report(screenshot_meta_information, edge_inconsistency_detection, invisible_text_detection,
                                  missing_text_detection, partial_conversion_detection, invisible_icon_detection):
    # Load JSON data
    application_name = screenshot_meta_information["applications"]
    screenshot_data = screenshot_meta_information["screenshots"]

    edge_inc_info = edge_inconsistency_detection
    invisible_text_info = invisible_text_detection
    missing_text_info = missing_text_detection

    partial_conversion_info = partial_conversion_detection
    invisible_icon_info = invisible_icon_detection

    # Organize data
    page_info = {item['id']: {"title": item['page_title'], "url": item['url']} for item in screenshot_data.values()}

    # Categorize inconsistencies
    partial_conversion_issues = defaultdict(set)
    partial_conversion_details = defaultdict(list)

    edge_page_map = {}
    invisible_text_page_map = {}
    missing_page_map = {}
    partial_conversion_page_map = {}
    icon_page_map = {}

    structured_edge_data = {"pages": []}
    structured_invisible_text = {"pages": []}
    structured_missing_text = {"pages": []}
    structured_partial_conversion_data = {"pages": []}
    structured_icon_data = {"pages": []}

    # 1.  Organizing edge inconsistencies per page
    for entry in edge_inc_info:
        page_id = entry.get('id')
        scroll_percentage = entry.get('scroll_percentage', 0)

        if page_id not in page_info:
            continue  # Skip missing page IDs

        page_title = page_info[page_id]['title']
        url = page_info[page_id]['url']

        # If the page is not in structured_edge_data, add a new entry
        if url not in edge_page_map:
            page_entry = {
                "url": url,
                "page_title": page_title,
                "edge_inconsistencies": [],
            }
            structured_edge_data["pages"].append(page_entry)
            edge_page_map[url] = page_entry  # Map URL to page entry

        # Reference existing page entry
        page_entry = edge_page_map[url]

        # Extract edge overlay path if available
        image_directory = entry.get("image_directory", [{}])
        edge_overlay_path = image_directory[0].get("edge_overlay", "No overlay image found")

        # Append scroll data entry
        page_entry["edge_inconsistencies"].append({
            "scroll_percentage": scroll_percentage,
            "image_directory": edge_overlay_path  # Added image directory path
        })

    # Organizing text inconsistency
    # a. invisible text inconsistencies
    for entry in invisible_text_info:
        page_id = entry.get('id')
        if page_id not in page_info:
            continue  # Skip missing page IDs

        url = page_info[page_id].get('url', 'Unknown URL')
        page_title = page_info[page_id].get('title', 'Unknown Title')
        scroll_percentage = entry.get('scroll_percentage', 0)

        # Check if the page exists in structured_data, if not, create a new entry
        if url not in invisible_text_page_map:
            page_entry = {
                "url": url,
                "page_title": page_title,
                "failed_text": [],
            }
            structured_invisible_text["pages"].append(page_entry)
            invisible_text_page_map[url] = page_entry  # Map URL to page entry

        # Reference existing page entry
        page_entry = invisible_text_page_map[url]

        for item in entry.get('invisible_text_summary', []):
            dark_mode_failed_texts = item.get('Dark mode failed text', [])

            if not dark_mode_failed_texts:
                continue  # Skip if no failed texts

            failed_texts = [
                {
                    "text": text_entry["text"],
                    "bounding_box": text_entry["bounding_box"],
                    "contrast_ratio": float(text_entry["contrast_ratio"]),
                    "text_color": text_entry["text_color"],
                    "background_color": text_entry["background_color"]
                }
                for text_entry in dark_mode_failed_texts
            ]

            # Append scroll data entry
            page_entry["failed_text"].append({
                "scroll_percentage": scroll_percentage,
                "out_dir": item.get("File", "Unknown File"),
                "light_mode_failed_text": len(item.get('Light mode failed text', [])),
                "dark_mode_failed_text": len(dark_mode_failed_texts),
                "failed_text": failed_texts
            })

    # b missing text

    for entry in missing_text_info:
        page_id = entry.get('id')
        scroll_percentage = entry.get('scroll_percentage', 0)

        if page_id not in page_info:
            continue  # Skip missing page IDs

        page_title = page_info[page_id]['title']
        url = page_info[page_id]['url']

        # If the page is not in structured_missing_text, add a new entry
        if url not in missing_page_map:
            page_entry = {
                "url": url,
                "page_title": page_title,
                "missing_text": [],
            }
            structured_missing_text["pages"].append(page_entry)
            missing_page_map[url] = page_entry  # Map URL to page entry

        # Reference existing page entry
        page_entry = missing_page_map[url]

        # Extract only the missing text information (ignoring bounding box)
        missing_text_only = [
            text_entry["tex_info"]  # Extract only text info, ignore bounding box
            for text_entry in entry.get('missing_text_summary', {}).get('missing_info', [])
        ]

        # Append scroll data entry
        page_entry["missing_text"].append({
            "scroll_percentage": scroll_percentage,
            "missing_text_count": entry.get('missing_text_summary', {}).get('missing_texts', 0),
            "missing_text_info": missing_text_only  # Store only text info
        })

    # Organizing partial conversion inconsistencies per page
    structured_partial_conversion_data = {"pages": []}
    partial_conversion_page_map = {}

    for entry in partial_conversion_info:
        page_id = entry.get('id')
        scroll_percentage = entry.get("scroll_percentage", 0)

        if page_id not in page_info:
            continue  # Skip missing page IDs

        page_title = page_info[page_id]['title']
        url = page_info[page_id]['url']

        # If the page is not in structured_partial_conversion_data, add a new entry
        if url not in partial_conversion_page_map:
            page_entry = {
                "url": url,
                "page_title": page_title,
                "partial_conversion": [],
            }
            structured_partial_conversion_data["pages"].append(page_entry)
            partial_conversion_page_map[url] = page_entry  # Map URL to page entry

        # Reference existing page entry
        page_entry = partial_conversion_page_map[url]

        # Extract the image directory from partial_conversion_summary
        image_path = entry.get('partial_conversion_summary', [{}])[0].get('image', "No image found")

        # Append structured partial conversion details
        page_entry["partial_conversion"].append({
            "scroll_percentage": scroll_percentage,
            "image_directory": image_path  # Added image path
        })

    # 4. invisible icon
    # # Organizing invisible icon inconsistencies per page
    for entry in invisible_icon_info:
        page_id = entry.get('id')
        scroll_percentage = entry.get("scroll_percentage", 0)

        if page_id not in page_info:
            continue  # Skip missing page IDs

        page_title = page_info[page_id]['title']
        url = page_info[page_id]['url']

        # If the page is not in structured_icon_data, add a new entry
        if url not in icon_page_map:
            page_entry = {
                "url": url,
                "page_title": page_title,
                "invisible_icons": [],
            }
            structured_icon_data["pages"].append(page_entry)
            icon_page_map[url] = page_entry  # Map URL to page entry

        # Reference existing page entry
        page_entry = icon_page_map[url]

        # Extract problematic file (filename)
        file_name = entry.get('invisible_icon', [{}])[0].get('problematic file', "No file found")

        # Extract all contrast ratios for `low_contrast_icon_light`
        light_contrast_ratios = [
            float(icon.get("contast ratio", 0))  # Convert to float for consistency
            for icon in entry.get('invisible_icon', [{}])[0].get('low_contrast_icon_light', [])
        ]

        # Extract all contrast ratios for `low_contrast_icon_dark`
        dark_contrast_ratios = [
            float(icon.get("contast ratio", 0))  # Convert to float for consistency
            for icon in entry.get('invisible_icon', [{}])[0].get('low_contrast_icon_dark', [])
        ]

        # Append structured invisible icon details
        page_entry["invisible_icons"].append({
            "scroll_percentage": scroll_percentage,
            "file_name": file_name,  # Added filename
            "low_contrast_icon_light": light_contrast_ratios,  # Light contrast ratios
            "low_contrast_icon_dark": dark_contrast_ratios  # Dark contrast ratios
        })

    # Structure the JSON report
    report = {
        "application_name": application_name,
        # "edge_inconsistency": [{"details": edge_inconsistency_detail[page]} for page in edge_issues],
        "edge_inconsistency": structured_edge_data,
        "text_inconsistency": {
            "invisible_text": structured_invisible_text,
            "missing_text": structured_missing_text
        },

        "partial_conversion": structured_partial_conversion_data,
        "icon_inconsistency": structured_icon_data

        # "partial_conversion":[{'details': partial_conversion_details[page] for page in partial_conversion_issues}],
        # "icon_inconsistency":[{'details': invisible_icon_details[page] for page in invisible_icon_issues}]
    }

    return report


def main():
    # image with normal size
    image_dir = '/chromaeye/example_dataset/edge_based/flashscore/input/image/org_size'

    # json file directory detected using upstage ocr
    json_dir = '/chromaeye/example_dataset/edge_based/flashscore/input/ocr'

    # image directory, resize the image into uied(detection result)
    uied_json_dir = '/chromaeye/example_dataset/edge_based/flashscore/input/uied_dl_json'

    # json file directory from uied detection
    uied_image_dir = '/chromaeye/example_dataset/edge_based/flashscore/input/image/uied_size'

    # meta information of the data that we have collected while collecting the dataset
    screenshot_meta_data = '/chromaeye/example_dataset/edge_based/flashscore/input/flashscore.json'

    # output directory where you want to save the result
    output_dir = '/chromaeye/example_dataset/edge_based/flashscore/output'

    inconsistency_detection(image_dir, json_dir, uied_image_dir, uied_json_dir, screenshot_meta_data, output_dir)


if __name__ == '__main__':
    main()