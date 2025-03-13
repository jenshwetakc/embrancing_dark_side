'''
Chromaeye: detect the partial conversion of the application
chroma eye will check whether the application support the dark mode throughout the application.
'''


import os
import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

# Load the image
def load_image(image_path):

    # update: Ticket: I-PC-4
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path:{image_path}")
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    return image

# Load the JSON file
def load_json(json_path):

    # update: Ticket: I-PC-4
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Json file not found at path:{json_path}")

    with open(json_path, 'r') as f:
        json_data = json.load(f)
    if 'compos' not in json_data:
        raise KeyError("JSON file does not contain the expected 'compos' key.")
    return json_data

# Create a mask that excludes all UI elements
def create_non_ui_mask(image, bounding_boxes):
    non_ui_mask = np.ones(image.shape[:2], dtype=np.uint8)
    for box in bounding_boxes:
        x1, y1, x2, y2 = box['position']['column_min'], box['position']['row_min'], \
            box['position']['column_max'], box['position']['row_max']
        non_ui_mask[y1:y2, x1:x2] = 0
    return non_ui_mask


# Calculate dominant color in a masked area using K-means
def calculate_dominant_color(image, mask, k=3):
    masked_area = image[mask == 1]
    pixels = np.float32(masked_area.reshape(-1, 3))
    _, labels, palette = cv2.kmeans(pixels, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2), 10, cv2.KMEANS_RANDOM_CENTERS)
    dominant_color = palette[np.argmax(np.bincount(labels.flatten()))]
    return tuple(int(c) for c in dominant_color)


# Calculate the most frequent color in a masked area
def calculate_most_frequent_color(image, mask):
    masked_area = image[mask == 1]
    pixels = [tuple(pixel) for pixel in masked_area]
    most_common_color = Counter(pixels).most_common(1)[0][0]
    return most_common_color


# Check if color falls within specified RGB range
def is_color_in_range(color, min_values, max_values):
    return all(min_val <= channel <= max_val for channel, min_val, max_val in zip(color, min_values, max_values))

def highlight_partial_conversion(image, non_ui_mask):
    highlight_image = image.copy()
    highlight_image[non_ui_mask ==1] = [0, 0, 255] # fill red color to partially converted area

    # apply highlight in the image
    plt.imshow(cv2.cvtColor(highlight_image, cv2.COLOR_BGR2RGB))
    plt.title("Highlighted Areas with Improper Conversion")
    plt.axis('off')
    # plt.show()
    return highlight_image


# Highlight insufficient color changes in HSV
def partial_conversion_areas_hsv(light_image, dark_image, non_ui_mask):
    hue_threshold = 10,
    saturation_threshold = 20,
    brightness_threshold = 20
    # output_path = "highlighted_no_conversion.png"
    light_hsv = cv2.cvtColor(light_image, cv2.COLOR_BGR2HSV)
    dark_hsv = cv2.cvtColor(dark_image, cv2.COLOR_BGR2HSV)
    hue_diff = np.abs(light_hsv[:, :, 0] - dark_hsv[:, :, 0])
    saturation_diff = np.abs(light_hsv[:, :, 1] - dark_hsv[:, :, 1])
    brightness_diff = np.abs(light_hsv[:, :, 2] - dark_hsv[:, :, 2])
    no_conversion_mask = (
            (hue_diff < hue_threshold) &
            (saturation_diff < saturation_threshold) &
            (brightness_diff < brightness_threshold) &
            (non_ui_mask == 1)
    )
    highlighted_image = highlight_partial_conversion(dark_image, no_conversion_mask)
    return highlighted_image

# Analyze color conversion for a single light-dark image pair
def analyze_color_conversion(light_image, dark_image, json_path, output_image_path):
    partial_conversion_area = None

    # Load images and JSON data
    light_image = light_image
    # print(light_image)
    dark_image = dark_image
    json_data = load_json(json_path)
    bounding_boxes = json_data.get('compos', [])

    non_ui_mask = create_non_ui_mask(light_image, bounding_boxes)

    plt.imshow(non_ui_mask, cmap='gray')
    # plt.show()

    # Calculate colors
    light_dominant_color = calculate_dominant_color(light_image, non_ui_mask)
    dark_dominant_color = calculate_dominant_color(dark_image, non_ui_mask)
    light_most_frequent_color = calculate_most_frequent_color(light_image, non_ui_mask)
    dark_most_frequent_color = calculate_most_frequent_color(dark_image, non_ui_mask)

    # range for the light mode background color
    light_mode_low_range = [200, 200, 200]
    light_mode_high_range = [255, 255, 255]

    # range for the dark mode background color
    dark_mode_low_range = [0, 0, 0]
    dark_mode_high_range = [90, 90, 90]

    # Color range checks
    light_in_bright_range = is_color_in_range(light_dominant_color, light_mode_low_range, light_mode_high_range)
    dark_in_dark_range = is_color_in_range(dark_dominant_color, dark_mode_low_range, dark_mode_high_range)
    dark_in_bright_range = is_color_in_range(dark_dominant_color, light_mode_low_range, light_mode_high_range)

    light_in_dark_range = is_color_in_range(light_dominant_color, dark_mode_low_range, dark_mode_high_range)


    # Additional check: Compare most frequent color with light and dark ranges
    light_frequent_in_bright_range = is_color_in_range(light_most_frequent_color, light_mode_low_range,
                                                       light_mode_high_range)
    dark_frequent_in_dark_range = is_color_in_range(dark_most_frequent_color, dark_mode_low_range, dark_mode_high_range)
    dark_frequent_in_bright_range = is_color_in_range(dark_most_frequent_color, light_mode_low_range,
                                                      light_mode_high_range)

    light_frequent_in_dark_range = is_color_in_range(light_most_frequent_color, dark_mode_low_range, dark_mode_high_range)

    dark_matches_light = dark_dominant_color == light_dominant_color or dark_most_frequent_color == light_most_frequent_color


    if dark_in_bright_range or dark_frequent_in_bright_range:
        conversion_status = ("Improper conversion detected: Dark mode background appear to be light color,"
                             "indicating the insufficient changes for dark mode adaptation.")
        partial_conversion_area = partial_conversion_areas_hsv(light_image, dark_image, non_ui_mask)

    elif light_in_dark_range or light_frequent_in_dark_range:
        # print('Light mode large section consist of the dark region, might be the feature of application. skip the partial inconsistency comparison...')
        conversion_status = ("Light mode large section consist of the dark region, might be the feature of application. skip the partial inconsistency comparison...")

    elif dark_matches_light:
        conversion_status = "Improper conversion detected: Dark mode background match the light background, which indicates the improper conversion"
        partial_conversion_area = partial_conversion_areas_hsv(light_image, dark_image, non_ui_mask)
    else:
        conversion_status = "Proper conversion of the mode: Light and dark background are sufficiently distinct."

    if partial_conversion_area is not None:
        cv2.imwrite(output_image_path, partial_conversion_area)

    return {"Conversion Status": conversion_status}


# check whether the application support the dark mode
def partial_conversion_inconsistency(light_image_path:str, dark_image_path:str, json_dir:str, output_image:str):
    total_image = 0
    image_with_issues = 0
    issues_details = []

    light_image = load_image(light_image_path)
    dark_image = load_image(dark_image_path)

    if light_image is None or dark_image is None:
        print(f"Error: Image not found or cannot be read at specified path.")
        return
    if light_image.shape[:2] != dark_image.shape[:2]:
        dark_image =cv2.resize(dark_image, (light_image.shape[1], light_image.shape[0]))

    total_image +=1

    conversion_result = analyze_color_conversion(light_image, dark_image, json_dir, output_image)

    issue_percentage = (image_with_issues/total_image) * 100 if total_image > 0 else 0

    if "Improper conversion" in conversion_result['Conversion Status']:
        issues_details.append({
            "image": output_image,
            "issue": conversion_result["Conversion Status"]

        })
    return issues_details