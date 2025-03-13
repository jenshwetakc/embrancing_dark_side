'''
chromaeye: object based detection
detect inconsistency for gui component, like button icon that are inconsistent between light and dark mode.
'''

import math
import os
import json
import cv2
import numpy as np
from collections import Counter


def load_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data

def get_top_colors(image):
    num_colors = 100
    pixels = image.reshape(-1, image.shape[-1])
    colors_rgb = [tuple(pixel) for pixel in pixels]
    color_counter = Counter(colors_rgb)
    most_appear = color_counter.most_common(num_colors)

    return most_appear

def relative_luminance(color):
    color = np.array(color) / 255.0
    R, G, B = color
    R = R / 12.92 if R <= 0.04045 else ((R + 0.055) / 1.055) ** 2.4
    G = G / 12.92 if G <= 0.04045 else ((G + 0.055) / 1.055) ** 2.4
    B = B / 12.92 if B <= 0.04045 else ((B + 0.055) / 1.055) ** 2.4
    return 0.2126 * R + 0.7152 * G + 0.0722 * B


def get_contrast_ratio(foreground_color, background_color):
    """Calculate contrast ratio between text and background."""

    L1 = relative_luminance(foreground_color)
    L2 = relative_luminance(background_color)

    if L1 > L2:
        return (L1 + 0.05) / (L2 + 0.05)
    else:
        return (L2 + 0.05) / (L1 + 0.05)


def euclidean_distance(color1, color2):
    '''Calculate the Euclidean distance between two colors in BGR format.'''
    return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))


def convert_color_format(bgr_color):
    color_rgb = (float(bgr_color[2]), float(bgr_color[1]), float(bgr_color[0]))
    return color_rgb


# analyze the contrast ratio based on WCAG guidelines
def analyze_icon_constrast(image, json_data, draw_bounding_box= False):
    wcag_ratio = 2.9
    failed_ratio = []

    for compo in json_data["compos"]:
        if compo["class"] == "Compo" and compo["height"] < 50 and compo["width"] < 50:
            position = compo["position"]
            padding = 2

            col_min = max(0, position["column_min"] - padding)
            row_min = max(0, position["row_min"] - padding)
            col_max = position["column_max"] + padding
            row_max = position["row_max"] + padding

            # Extract bounding box area from image
            component_image = image[row_min:row_max, col_min:col_max]

            # Get the most and second most common colors
            most_appear = get_top_colors(component_image)

            if len(most_appear) < 2:
                continue

            # assign the colors
            background_color_bgr = most_appear[0][0]
            foreground_color_bgr = most_appear[1][0]
            remaining_colors = most_appear[2:]

            # convert the color to the rgb
            background_color = convert_color_format(background_color_bgr)
            foreground_color = convert_color_format(foreground_color_bgr)

            # Calculate contrast ratio
            ratio = get_contrast_ratio(background_color, foreground_color)

            # Draw a bounding box if the contrast ratio fails the WCAG guidelines
            if ratio < wcag_ratio and draw_bounding_box:
                foreground_color_candidates = [color[0] for color in remaining_colors]
                if foreground_color_candidates:
                    new_foreground_color_bgr = max(foreground_color_candidates,
                                                   key=lambda color: euclidean_distance(background_color, color))
                    new_foreground_color = convert_color_format(new_foreground_color_bgr)
                    new_ratio = get_contrast_ratio(background_color, new_foreground_color)
                    if new_ratio < wcag_ratio:
                        cv2.rectangle(image, (col_min, row_min), (col_max, row_max), (0, 0, 255), 2)
                        failed_ratio.append({
                            "contast ratio": new_ratio
                        })
    return image, failed_ratio


def combine_images_side_by_side(image1, image2):
    return np.concatenate((image1, image2), axis=1)


def load_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path:{image_path}")
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Failed to laod image at path: {image_path}")
    return image


def icon_inconsistency(light_image_path: str, dark_image_path: str, json_path: str, output_image_dir: str):
    final_ratio = []

    light_image = load_image(light_image_path)
    dark_image = load_image(dark_image_path)
    json_data = load_json(json_path)

    if light_image is None or dark_image is None:
        print(f"Error: Image not found or cannot be read at specified paths.")
        return
    if light_image.shape[:2] != dark_image.shape[:2]:
        dark_image = cv2.resize(dark_image, (light_image.shape[1], light_image.shape[0]))



    light_image_detection, failed_ratio_light = analyze_icon_constrast(light_image, json_data, draw_bounding_box = False)
    dark_image_detection, failed_ratio_dark = analyze_icon_constrast(dark_image, json_data, draw_bounding_box = True)

    # combine the light and dark mode image result
    combine_light_dark_image = combine_images_side_by_side(light_image_detection, dark_image_detection)

    # save the image in icon inconsistency directory
    cv2.imwrite(output_image_dir, combine_light_dark_image)

    combine_ratio = failed_ratio_light + failed_ratio_dark

    if failed_ratio_dark or (failed_ratio_light and failed_ratio_dark):
        final_ratio.append({
            "low_contrast_icon_light": failed_ratio_light,
            "low_contrast_icon_dark": failed_ratio_dark,
            "problematic file": output_image_dir
        })

    return final_ratio


