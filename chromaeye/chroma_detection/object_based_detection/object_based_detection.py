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


def analyze_icon_contrast(image, json_data):
    wcag_ratio = 2.9
    results = []

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

            # Try alternative foreground if needed
            # if ratio < wcag_ratio and remaining_colors:
            #     candidates = [c[0] for c in remaining_colors]
            #     new_fg_bgr = max(candidates,
            #                      key=lambda c: euclidean_distance(background_bgr, c))
            #     nratio = get_contrast_ratio(background,
            #                                convert_color_format(new_fg_bgr))
            #     if nratio < wcag_ratio:
            #         results.append({
            #             "bbox": (col_min, row_min, col_max, row_max),
            #             "ratio": nratio
            #         })
            if ratio < wcag_ratio:
                foreground_color_candidates = [color[0] for color in remaining_colors]
                if foreground_color_candidates:
                    new_foreground_color_bgr = max(foreground_color_candidates,
                                                   key=lambda color: euclidean_distance(background_color, color))
                    new_foreground_color = convert_color_format(new_foreground_color_bgr)
                    new_ratio = get_contrast_ratio(background_color, new_foreground_color)
                    if new_ratio < wcag_ratio:
                        # cv2.rectangle(image, (col_min, row_min), (col_max, row_max), (0, 0, 255), 2)
                        results.append({
                            "contrast_ratio": new_ratio,
                            "bbox": (col_min, row_min, col_max, row_max),\
                        })

    return results


def combine_images_side_by_side(image1, image2):
    return np.concatenate((image1, image2), axis=1)


def load_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path:{image_path}")
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Failed to laod image at path: {image_path}")
    return image


def compare_light_dark_mode_pixels(light_image, dark_image, bbox, threshold=15):
    """
    Compare pixel values between light and dark mode images for a given bounding box.

    Args:
        light_image: np.array, light mode image
        dark_image: np.array, dark mode image
        bbox: tuple (x1, y1, x2, y2) bounding box
        threshold: int, mean pixel difference threshold to consider "same"

    Returns:
        bool: True if pixels are essentially same, False otherwise
    """
    x1, y1, x2, y2 = bbox

    # Extract regions
    light_region = light_image[y1:y2, x1:x2]
    dark_region = dark_image[y1:y2, x1:x2]

    # Convert to grayscale for simple comparison
    light_gray = cv2.cvtColor(light_region, cv2.COLOR_BGR2GRAY)
    dark_gray = cv2.cvtColor(dark_region, cv2.COLOR_BGR2GRAY)

    # Compute absolute pixel-wise difference
    pixel_diff = np.abs(light_gray.astype(np.int16) - dark_gray.astype(np.int16))
    mean_diff = np.mean(pixel_diff)

    # If mean difference is below threshold, consider pixels identical
    return mean_diff < threshold


def icon_inconsistency(light_image_path, dark_image_path, json_path, output_image_dir):
    light_image = load_image(light_image_path)
    dark_image = load_image(dark_image_path)
    json_data = load_json(json_path)

    if light_image.shape[:2] != dark_image.shape[:2]:
        dark_image = cv2.resize(dark_image,
                                (light_image.shape[1], light_image.shape[0]))

    light_results = analyze_icon_contrast(light_image, json_data)
    dark_results = analyze_icon_contrast(dark_image, json_data)
    # print(light_results)
    # print(dark_results)

    failed = []

    for light_res, dark_res in zip(light_results, dark_results):
        light_ratio = light_res["contrast_ratio"]

        print("l", light_ratio)
        dark_ratio = dark_res["contrast_ratio"]
        print("d",dark_ratio)
        col_min, row_min, col_max, row_max = dark_res["bbox"]

        # Check 1: both low contrast? ignore
        # if light_ratio < 0.5 and dark_ratio < 0.5:
        #     continue

        # Check 2: pixel similarity? ignore
        # if compare_light_dark_mode_pixels(light_image, dark_image, dark_res["bbox"]):
        #     continue

        # Otherwise, draw bounding box
        cv2.rectangle(
            dark_image,
            (col_min, row_min),
            (col_max, row_max),
            (0, 0, 255),
            2
        )

        failed.append({
            "light_ratio": light_ratio,
            "dark_ratio": dark_ratio,
            "bbox": dark_res["bbox"]
        })

    combined = combine_images_side_by_side(light_image, dark_image)
    cv2.imwrite(output_image_dir, combined)

    return failed



