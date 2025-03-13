'''
chromaeye: text based detection
chromaeye check for the text that are invisible to the dark mode (based on the WCAG guidelines to meet the minimum contrast ratio of
4.5:1 for normal text and 3:1 for bold and large text)
'''

import os
import cv2
import math
import numpy as np
import json
from typing import List, Dict, Any
from collections import Counter


# Load the JSON file
def load_json(json_path: str) -> Dict[str, Any]:
    """Load JSON file."""
    # code update, november 18
    # Ticket: I-TI3,
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found at path: {json_path}")
    with open(json_path, 'r') as f:
        return json.load(f)


# Function to save information to JSON
def save_failed_contrast_info_to_json(failed_texts: List[Dict[str, Any]], output_json_path: str):
    """Save text elements that fail the contrast ratio check to a JSON file."""
    with open(output_json_path, 'w') as file:
        json.dump(failed_texts, file, indent=4)


# Extract bounding box  from vertices
def extract_bounding_box(text_info):
    """Extract bounding box coordinates from the text information."""
    vertices = text_info['boundingBox']['vertices']
    xmin = min([v['x'] for v in vertices])
    ymin = min([v['y'] for v in vertices])
    xmax = max([v['x'] for v in vertices])
    ymax = max([v['y'] for v in vertices])
    return xmin, ymin, xmax, ymax


def bgr_to_rgb(image):
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image_rgb

def get_color_pixel_value(image, text_info):
    # Get bounding box
    x_min, y_min, x_max, y_max = extract_bounding_box(text_info)

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


def calculate_std_deviation(image, text_info):
    image_rgb = bgr_to_rgb(image)
    # Get bounding box coordinates
    x_min, y_min, x_max, y_max = extract_bounding_box(text_info)

    # Define the bounding box points as a quadrilateral
    points = np.array([[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]], dtype=np.int32)

    # create a mask for the bounding box region
    mask = np.zeros(image_rgb.shape[:2], dtype=np.uint8)
    polygon = np.array(points, dtype=np.int32)
    cv2.fillPoly(mask, [points.reshape((-1, 1, 2))], 255)

    roi = cv2.bitwise_and(image_rgb, image, mask=mask)
    roi_pixels = roi[mask == 255].reshape(-1, 3)
    all_pixels_array = np.array(roi_pixels)
    std_dev = np.std(all_pixels_array)
    return std_dev


def is_large_text(text_info) -> bool:
    """Check if the text is large based on the height of the bounding box."""
    x_min, y_min, x_max, y_max = extract_bounding_box(text_info)
    text_height = y_max - y_min
    large_text_threshold = 24  # Threshold for large text (e.g., 18-point or larger)
    return text_height >= large_text_threshold


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


# Convert RGB to HSV and identify color family
def rgb_to_hsv(rgb_color):
    """Convert RGB to HSV color space."""
    rgb_normalized = np.array(rgb_color) / 255.0
    hsv_color = cv2.cvtColor(np.uint8([[rgb_normalized * 255]]), cv2.COLOR_RGB2HSV)[0][0]
    return hsv_color


def rgb_to_hsl(rgb_color):
    """Convert RGB to HSL color space."""
    rgb_normalized = np.array(rgb_color) / 255.0
    hsl_color = cv2.cvtColor(np.uint8([[rgb_normalized * 255]]), cv2.COLOR_RGB2HLS)[0][0]
    return hsl_color


def is_light_or_dark(hsl_color):
    """Determine if the color is light or dark based on the lightness value in HSL."""
    lightness = hsl_color[1] / 255.0  # Normalize the lightness value to be between 0 and 1
    if lightness >= 0.8:
        return "light"
    elif lightness <= 0.2:
        return "dark"
    else:
        return "neutral"


def analyze_text_background_colors_hsl(text_color, background_color):
    """Determine if the text and background fall under problematic categories using HSL."""
    hsl_text = rgb_to_hsl(text_color)
    hsl_background = rgb_to_hsl(background_color)

    txt_brightness = is_light_or_dark(hsl_text)
    bg_brightness = is_light_or_dark(hsl_background)

    if txt_brightness == "light" and bg_brightness == "light":
        return "Light text on light background"
    elif txt_brightness == "dark" and bg_brightness == "dark":
        return "Dark text on dark background"
    text_saturation = hsl_text[1]
    background_saturation = hsl_background[1]
    if text_saturation < 50 and background_saturation < 50:
        return "Low saturation - muted colors"

    # Default case for general contrast issue
    return "Color contrast issue"


def euclidean_distance(color1, color2):
    """Calculate the Euclidean distance between two colors in BGR format."""
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))


def convert_color_format(bgr_color):
    # color_rgb = (int(bgr_color[2]), int(bgr_color[1]), int(bgr_color[0]))
    color_rgb = (float(bgr_color[2]), float(bgr_color[1]), float(bgr_color[0]))
    return color_rgb


def compare_light_dark_mode_pixels(light_image, dark_image, text, threshold=15):
    """
    Compares pixel values of text bounding boxes between light and dark mode images.
    """
    x1, y1, x2, y2 = extract_bounding_box(text)

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


def rgb_to_hex(rgb):
    """
    Convert an RGB tuple (R, G, B) to a HEX color string.
    """
    r, g, b = map(lambda x: int(round(x)), rgb)  # Ensure RGB values are integers
    return "#{:02x}{:02x}{:02x}".format(r, g, b)



def check_contrast_and_draw_bounding_boxes(light_image, dark_image, light_texts, dark_texts, output_image_path,
                                           output_json_path):
    """Check the contrast ratio for both light and dark mode images, draw bounding boxes, and save failing cases."""
    minimum_contrast_ratio_normal = 4.5  # WCAG minimum contrast ratio for regular text
    minimum_contrast_ratio_large = 3.0  # WCAG minimum contrast ratio for large text

    chroma_threshold = 2.9
    failed_texts = []  # List to store texts that fail the contrast check
    std_threshold = 20  # Standard deviation threshold

    # Dictionary to store text that passes the contrast in light mode
    light_mode_pass = {}
    summary_data = []
    light_failed_text = []
    dark_failed_text = []

    # Light mode contrast check
    for page in light_texts['pages']:
        for text in page['words']:

            wcag_threshold = minimum_contrast_ratio_large if is_large_text(text) else minimum_contrast_ratio_normal
            std = calculate_std_deviation(light_image, text)

            most_common_colors = get_color_pixel_value(light_image, text)

            if len(most_common_colors) >= 2:
                background_color_bgr = most_common_colors[0][0]
                text_color_bgr = most_common_colors[1][0]

            remaining_colors = most_common_colors[2:]

            # Ticket: I-TI1 end
            background_color = convert_color_format(background_color_bgr)
            text_color = convert_color_format(text_color_bgr)
            contrast = get_contrast_ratio(text_color, background_color)

            # If contrast fails in light mode
            if contrast < wcag_threshold:

                # Attempt to adjust text color if needed
                text_color_candidates = [color[0] for color in remaining_colors]
                if text_color_candidates:
                    #  ticket: I- TI-5
                    background_color_bgr = np.array(background_color_bgr, dtype=np.int32)
                    text_color_candidates = [np.array(color, dtype=np.int32) for color in text_color_candidates]

                    new_text_color_bgr = max(text_color_candidates,
                                             key=lambda color: euclidean_distance(background_color_bgr, color))
                    new_text_color = convert_color_format(new_text_color_bgr)
                    new_ratio = get_contrast_ratio(new_text_color, background_color)

                    if new_ratio < chroma_threshold:
                        failure_category = analyze_text_background_colors_hsl(new_text_color, background_color)
                        compare_pixel = compare_light_dark_mode_pixels(light_image, dark_image, text, threshold=15)
                        bg_hexcolor = rgb_to_hex(background_color)
                        text_hexcolor = rgb_to_hex(text_color)
                        newtext_hexcolor = rgb_to_hex(new_text_color)

                        if compare_pixel == "normal_text":
                            light_failed_text.append({
                                "mode": "light",
                                "text": text['text'],
                                "rgb_text_color": text_color,
                                "rgb_background_color": background_color,
                                "text_color": newtext_hexcolor,
                                "background_color": bg_hexcolor,
                                "contrast_ratio": new_ratio,
                                "failure_category": failure_category,
                                "bounding_box": extract_bounding_box(text)
                            })
                        # Draw bounding box on light image
                        # x_min, y_min, x_max, y_max = extract_bounding_box(text)
                        # cv2.rectangle(light_image, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)
                        else:
                            # Save as passed with adjusted color
                            light_mode_pass[text['text']] = {
                                "bounding_box": extract_bounding_box(text),
                                "text_color": new_text_color,
                                "background_color": background_color,
                                "contrast_ratio": new_ratio
                            }
            else:
                # If contrast passes in light mode, save the info for later comparison with dark mode
                light_mode_pass[text['text']] = {
                    "bounding_box": extract_bounding_box(text),
                    "text_color": text_color,
                    "background_color": background_color,
                    "contrast_ratio": contrast
                }

    # Dark mode contrast check
    for page in dark_texts['pages']:
        for text in page['words']:

            contrast_threshold = minimum_contrast_ratio_large if is_large_text(text) else minimum_contrast_ratio_normal
            std = calculate_std_deviation(dark_image, text)

            most_common_colors = get_color_pixel_value(dark_image, text)

            if len(most_common_colors) >= 2:
                background_color_bgr = most_common_colors[0][0]
                text_color_bgr = most_common_colors[1][0]

            remaining_colors_bgr = most_common_colors[2:]

            background_color = convert_color_format(background_color_bgr)
            text_color = convert_color_format(text_color_bgr)
            contrast = get_contrast_ratio(text_color, background_color)

            # If contrast fails in dark mode
            if contrast < contrast_threshold:

                # Attempt to adjust text color if needed
                text_color_candidates = [color[0] for color in remaining_colors_bgr]
                if text_color_candidates:
                    #  ticket: I- TI-5
                    background_color_bgr = np.array(background_color_bgr, dtype=np.int32)
                    text_color_candidates = [np.array(color, dtype=np.int32) for color in text_color_candidates]

                    new_text_color_bgr = max(text_color_candidates,
                                             key=lambda color: euclidean_distance(background_color_bgr, color))
                    new_text_color = convert_color_format(new_text_color_bgr)
                    new_ratio = get_contrast_ratio(new_text_color, background_color)
                    text_content = text['text']

                    if new_ratio < chroma_threshold:
                        failure_category = analyze_text_background_colors_hsl(new_text_color, background_color)
                        if text_content in light_mode_pass:

                            light_contrast = light_mode_pass[text_content]["contrast_ratio"]

                            if light_contrast >= contrast_threshold:
                                failure_reason = "text inconsistency"
                            else:
                                failure_reason = "contrast ratio issue"
                        else:
                            # If the text also fails in light mode, label as "contrast ratio issue"
                            failure_reason = "contrast ratio issue"

                        compare_pixel = compare_light_dark_mode_pixels(light_image, dark_image, text, threshold=15)

                        bg_hexcolor = rgb_to_hex(background_color)
                        text_hexcolor = rgb_to_hex(text_color)
                        newtext_hexcolor = rgb_to_hex(new_text_color)

                        if compare_pixel == "normal_text":
                            dark_failed_text.append({
                                "mode": "dark",
                                "text": text_content,
                                "rgb_text_color": text_color,
                                "rgb_background_color": background_color,
                                "text_color": newtext_hexcolor,
                                "background_color": bg_hexcolor,
                                "contrast_ratio": new_ratio,
                                "failure_reason": failure_reason,
                                "failure_category": failure_category,
                                "bounding_box": extract_bounding_box(text)
                            })
                            x_min, y_min, x_max, y_max = extract_bounding_box(text)
                            cv2.rectangle(dark_image, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)

    failed_texts = {
        "failed_texts_light": light_failed_text,
        "failed_texts_dark": dark_failed_text
    }

    combined_image = np.hstack((light_image, dark_image))
    cv2.imwrite(output_image_path, combined_image)

    # added if condition to save the information when there exist the invisible text in dark mode otherwise don't save the result
    if dark_failed_text:
        # Save all failed contrast information to JSON
        save_failed_contrast_info_to_json(failed_texts, output_json_path)

        # Combine images for visualization and save
        combined_image = np.hstack((light_image, dark_image))
        cv2.imwrite(output_image_path, combined_image)

        if light_failed_text or dark_failed_text:
            summary_data.append({
                "File": output_image_path,

                # Summary Count
                "Light mode failed text count": len(light_failed_text),
                "Dark mode failed text count": len(dark_failed_text),

                # Extract only relevant fields for failed text
                "Light mode failed text": [
                    {
                        "text": text_info["text"],
                        "contrast_ratio": float(text_info["contrast_ratio"]),
                        "text_color": text_info["text_color"],
                        "background_color": text_info["background_color"],
                        "bounding_box": text_info["bounding_box"]

                    }
                    for text_info in light_failed_text
                ],

                "Dark mode failed text": [
                    {
                        "text": text_info["text"],
                        "contrast_ratio": float(text_info["contrast_ratio"]),
                        "text_color": text_info["text_color"],
                        "background_color": text_info["background_color"],
                        "bounding_box": text_info["bounding_box"]
                    }
                    for text_info in dark_failed_text
                ]
            })

    return summary_data


def load_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Failed to load image at path: {image_path}")
    return image


def invisible_text_inconsistency(light_image_path: str, dark_image_path: str, light_json_path: str, dark_json_path: str,
                                 output_image_path: str, output_json_path: str):
    """Check contrast for both light and dark mode, draw bounding boxes, and save failing cases."""

    light_img = load_image(light_image_path)
    dark_img = load_image(dark_image_path)

    if light_img is None or dark_img is None:
        print(f"Error: Image not found or cannot be read at specified paths.")
        return

    if light_img.shape[:2] != dark_img.shape[:2]:
        # Resize dark image to match the light image dimensions
        dark_img = cv2.resize(dark_img, (light_img.shape[1], light_img.shape[0]))

    # Load JSON data
    light_json_data = load_json(light_json_path)
    dark_json_data = load_json(dark_json_path)

    summary_data = check_contrast_and_draw_bounding_boxes(light_img, dark_img, light_json_data, dark_json_data,
                                                          output_image_path, output_json_path)
    return summary_data