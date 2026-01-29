'''
chromaeye detect the missing text:
missing text inconsistency means that the text that are presented in the light mode but the text are blended so well in the dark mode that give the illusion
that the text are actually missing in the dark mode.
'''

import cv2
import json
import re
import numpy as np

from typing import List, Dict, Any
from fuzzywuzzy import fuzz
from collections import Counter

def load_json(json_path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase and removing extra spaces."""
    return re.sub(r'\s+', ' ', text.strip().lower())


def calculate_overlap(box1, box2):
    """Calculate the overlap area between two bounding boxes."""
    x1, y1, x2, y2 = max(box1[0], box2[0]), max(box1[1], box2[1]), min(box1[2], box2[2]), min(box1[3], box2[3])
    overlap_width = max(0, x2 - x1)
    overlap_height = max(0, y2 - y1)
    return overlap_width * overlap_height


def calculate_center_distance(box1, box2):
    """Calculate Euclidean distance between bounding box centers."""
    center_x1, center_y1 = (box1[0] + box1[2]) / 2, (box1[1] + box1[3]) / 2
    center_x2, center_y2 = (box2[0] + box2[2]) / 2, (box2[1] + box2[3]) / 2
    return np.sqrt((center_x1 - center_x2) ** 2 + (center_y1 - center_y2) ** 2)


def get_bounding_box_vertices(bbox):
    """Convert bounding box vertices into (x1, y1, x2, y2)."""
    x_coords = [v['x'] for v in bbox]
    y_coords = [v['y'] for v in bbox]
    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]


def is_similar(text1: str, text2: str, threshold: int = 85) -> bool:
    """Check similarity using fuzzy matching."""
    return fuzz.ratio(text1, text2) >= threshold


def extract_text_structure(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts the text and bounding box information for each word from the JSON data."""
    words_info = []
    for page in data["pages"]:
        for word in page["words"]:
            text_content =(word['text'])
            bounding_box = get_bounding_box_vertices(word['boundingBox']['vertices'])
            words_info.append({
                "tex_info": text_content,
                "bounding_box": bounding_box,
            })
    return words_info



def compare_light_dark_mode_pixels(light_image, dark_image, bbox, threshold=15):
    """
    Compares pixel values of text bounding boxes between light and dark mode images.
    """
    x1, y1, x2, y2 = bbox

    # Extract text regions from both images
    light_text_region = light_image[y1:y2, x1:x2]
    dark_text_region = dark_image[y1:y2, x1:x2]

    # Convert to grayscale for comparison
    light_gray = cv2.cvtColor(light_text_region, cv2.COLOR_BGR2GRAY)
    dark_gray = cv2.cvtColor(dark_text_region, cv2.COLOR_BGR2GRAY)

    # Compute pixel-wise absolute difference
    pixel_diff = np.abs(light_gray.astype(np.int16) - dark_gray.astype(np.int16))

    # Calculate mean difference
    mean_diff = np.mean(pixel_diff)

    # If difference is small, it's likely embedded text
    return "text_in_image" if mean_diff < threshold else "normal_text"



def get_color_pixel_value(image, text_info):
    x_min, y_min, x_max, y_max = text_info['bounding_box']

    # Clamp coordinates within image bounds
    height, width = image.shape[:2]
    x_min, y_min = max(0, x_min), max(0, y_min)
    x_max, y_max = min(width, x_max), min(height, y_max)

    points = np.array([[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]])

    color_pixel_values = []
    for y in range(y_min, y_max):
        for x in range(x_min, x_max):
            if cv2.pointPolygonTest(points, (x, y), False) >= 0:
                color_pixel_values.append(tuple(image[y, x]))

    # Count the occurrence of each unique color
    color_counts = Counter(color_pixel_values)
    # Get the most common colors
    most_common_colors = color_counts.most_common(min(len(color_counts), 20))

    return most_common_colors


def get_contrast_ratio(foreground_color, background_color):
    """Calculate contrast ratio between text and background."""
    def relative_luminance(color):
        color = np.array(color) / 255.0
        R, G, B = color
        R = R / 12.92 if R <= 0.04045 else ((R + 0.055) / 1.055) ** 2.4
        G = G / 12.92 if G <= 0.04045 else ((G + 0.055) / 1.055) ** 2.4
        B = B / 12.92 if B <= 0.04045 else ((B + 0.055) / 1.055) ** 2.4
        return 0.2126 * R + 0.7152 * G + 0.0722 * B

    L1 = relative_luminance(foreground_color)
    L2 = relative_luminance(background_color)
    if L1 > L2:
        return (L1 + 0.05) / (L2 + 0.05)
    else:
        return (L2 + 0.05) / (L1 + 0.05)


def extract_edges(image, bbox, low=10, high=55):
    """
    Extract Canny edges from a bounding box region.
    """
    x1, y1, x2, y2 = bbox
    region = image[y1:y2, x1:x2]

    if region.size == 0:
        return None

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, low, high)

    return edges


def edge_similarity(light_edges, dark_edges):
    """
    Compute edge similarity using intersection-over-union.
    Returns a value in [0, 1].
    """
    if light_edges is None or dark_edges is None:
        return 0.0

    if light_edges.shape != dark_edges.shape:
        dark_edges = cv2.resize(dark_edges, light_edges.shape[::-1])

    light_bin = (light_edges > 0).astype(np.uint8)
    dark_bin = (dark_edges > 0).astype(np.uint8)

    intersection = np.sum(light_bin & dark_bin)
    union = np.sum(light_bin | dark_bin)

    if union == 0:
        return 0.0

    return intersection / union




def find_missing_texts(light_texts: List[Dict[str, Any]], dark_texts: List[Dict[str, Any]], light_image, dark_image) -> List[Dict[str, Any]]:
    """
    Find texts in light mode that are missing or mismatched in dark mode based on IoU and occurrences.
    """
    fuzz_threshold = 75  # Fixed: was incorrectly defined as a tuple
    spatial_threshold = 0.5  # Fractional overlap threshold
    max_distance_ratio = 0.3
    minimum_threshold = 1.5

    missing_texts = []
    unmatched_dark_texts = []

    match_dark_indices = set()
    match_light_indices = set()

    for i,light_element in enumerate(light_texts):

        EDGE_SIMILARITY_THRESHOLD = 0.3

        # print('all',light_element['content'])
        bbox = light_element['bounding_box']
        # Skip single letters, spaces, commas, or symbols
        if len(light_element['tex_info'].strip()) <= 2 or light_element['tex_info'] in {',', '.', '!', '?', '-', '_', ':' ,' '}:
            continue
        text_found = False
        compare_pixel = compare_light_dark_mode_pixels(light_image, dark_image, bbox, threshold=15)

        if compare_pixel == "normal_text":
            for j,dark_element in enumerate(dark_texts):
                # Check text similarity
                if is_similar(light_element['tex_info'], dark_element['tex_info'], fuzz_threshold):
                    # Check spatial overlap
                    light_bbox = light_element['bounding_box']
                    dark_bbox = dark_element['bounding_box']
                    overlap_area = calculate_overlap(light_bbox, dark_bbox)
                    light_area = (light_bbox[2] - light_bbox[0]) * (light_bbox[3] - light_bbox[1])
                    center_distance = calculate_center_distance(light_bbox, dark_bbox)

                    if (overlap_area / light_area > spatial_threshold) or (center_distance < 30):
                        text_found = True
                        # print(dark_element)
                        match_light_indices.add(i)
                        match_dark_indices.add(j)
                        break
                    # for j, dark_element in enumerate(dark_texts):
                    #     # print(match_dark_indices)
                    #     if j not in match_dark_indices:
                    #         unmatched_dark_texts.append(dark_element)

            if not text_found:
                # print(light_element)
                # Extract color values from the dark mode image bounding box
                color_values = get_color_pixel_value(dark_image, light_element)

                if len(color_values) < 2:
                    missing_texts.append(light_element)  # Add if we can't determine contrast properly
                    continue

                # Assign background & text colors (most frequent = background, second most = text)
                background_color = color_values[0][0]  # Most frequent color
                text_color = color_values[1][0]  # Second most frequent color

                # Compute contrast ratio
                contrast_ratio = get_contrast_ratio(background_color, text_color)
                if contrast_ratio < minimum_threshold:

                    light_edges = extract_edges(light_image, bbox)
                    dark_edges = extract_edges(dark_image, bbox)

                    edge_sim = edge_similarity(light_edges, dark_edges)

                    if edge_sim < EDGE_SIMILARITY_THRESHOLD:
                        missing_texts.append(light_element)

                # print(contrast_ratio)
                # Only add to missing texts if contrast is too low
                # if contrast_ratio < minimum_threshold:
                #     missing_texts.append(light_element)

    return missing_texts


def save_missing_info_to_json(missing_elements: List[Dict[str, Any]], output_json_path: str):
    """Save missing information to a JSON file."""
    with open(output_json_path, 'w') as file:
        json.dump(missing_elements, file, indent=4)


def missing_text(light_image_path: str, dark_image_path: str, light_json_path: str, dark_json_path: str,
                 output_image_path: str, output_json_path: str):

    """Visualize the side-by-side comparison and highlight missing areas."""
    light_img = cv2.imread(light_image_path)
    dark_img = cv2.imread(dark_image_path)
    summary_data = []

    if light_img is None or dark_img is None:
        print("Error: Could not load images.")
        return

    if light_img.shape[:2] != dark_img.shape[:2]:
        dark_img = cv2.resize(dark_img, (light_img.shape[1], light_img.shape[0]))

    light_json = load_json(light_json_path)
    dark_json = load_json(dark_json_path)

    light_texts = extract_text_structure(light_json)
    dark_texts = extract_text_structure(dark_json)

    missing_texts = find_missing_texts(light_texts, dark_texts, light_img, dark_img)
    len_missing_text = len(missing_texts)

    if len_missing_text > 0:

        for elem in missing_texts:
            bbox = elem['bounding_box']
            cv2.rectangle(dark_img, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 0, 255), 2)

        combined_image = np.hstack((light_img, dark_img))

        cv2.imwrite(output_image_path, combined_image)
        save_missing_info_to_json(missing_texts, output_json_path)
        print('missing_texts', missing_texts)

        summary_data = {
            "file": output_json_path,
            "missing_info": missing_texts,
            "missing_texts": len_missing_text

        }
    return summary_data





