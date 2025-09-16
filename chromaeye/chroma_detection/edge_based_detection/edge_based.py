'''
chrome eye: edge based inconsistency detection
red pixel - light mode edges
green pixel - dark mode edges
yellow pixel - consistent edge
'''


import cv2
import numpy as np
import os
from scipy.spatial import cKDTree  # Efficient to find nearest-neighbor edges

def edge_difference(light_image, dark_image, edge_overlay_dir, missing_edge_dir):

    DISTANCE_THRESHOLD = 3
    edge_difference_summary = []

    light_gray = cv2.cvtColor(light_image, cv2.COLOR_BGR2GRAY)
    dark_gray = cv2.cvtColor(dark_image, cv2.COLOR_BGR2GRAY)
    light_gray_blurred = cv2.GaussianBlur(light_gray, (5, 5), 0)
    dark_gray_blurred = cv2.GaussianBlur(dark_gray, (5, 5), 0)

    # # Apply Gaussian blur and edge detection
    # light_edges = cv2.Canny(cv2.GaussianBlur(light_gray, (5, 5), 0), 10, 55)
    # dark_edges = cv2.Canny(cv2.GaussianBlur(dark_gray, (5, 5), 0), 10, 55)

    # Apply Canny edge detection with adjusted threshold
    light_edges = cv2.Canny(light_gray, 10, 55)
    dark_edges = cv2.Canny(dark_gray, 10, 55)

    # Extract edge coordinates (non-zero pixels)
    light_coords = np.column_stack(np.where(light_edges > 0))
    dark_coords = np.column_stack(np.where(dark_edges > 0))

    # Create KD-trees for efficient nearest-neighbor search
    light_tree = cKDTree(light_coords)
    dark_tree = cKDTree(dark_coords)

    # Find problematic edges in light mode
    distances_light, _ = dark_tree.query(light_coords)
    problematic_light_coords = light_coords[distances_light > DISTANCE_THRESHOLD]

    # Find problematic edges in dark mode
    distances_dark, _ = light_tree.query(dark_coords)
    problematic_dark_coords = dark_coords[distances_dark > DISTANCE_THRESHOLD]

    # Create blank masks for visualization
    problematic_light = np.zeros_like(light_edges, dtype=np.uint8)
    problematic_dark = np.zeros_like(dark_edges, dtype=np.uint8)

    # Mark problematic edges
    problematic_light[problematic_light_coords[:, 0], problematic_light_coords[:, 1]] = 255
    problematic_dark[problematic_dark_coords[:, 0], problematic_dark_coords[:, 1]] = 255

    # Combine problematic edges for visualization
    edge_diff_ligdak = cv2.bitwise_or(problematic_light, problematic_dark)

    # Create a color overlay for problematic areas
    highlight_overlay = np.zeros_like(light_image, dtype=np.uint8)
    highlight_overlay[problematic_light > 0] = [0, 0, 255]  # Red for light-only edges
    highlight_overlay[problematic_dark > 0] = [0, 255, 0]  # Green for dark-only edges

    # Create Color Overlay

    color_overlay = np.zeros((light_edges.shape[0], light_edges.shape[1], 3), dtype=np.uint8)

    color_overlay[:, :, 2] = light_edges
    color_overlay[:, :, 1] = dark_edges

    # Save results with proper file names
    cv2.imwrite(edge_overlay_dir, color_overlay)
    cv2.imwrite(missing_edge_dir, edge_diff_ligdak)

    edge_count_light =np.count_nonzero(problematic_light)
    edge_count_dark = np.count_nonzero(problematic_dark)

    light_edge_missing= edge_count_light > 1500

    dark_edge_missing = edge_count_dark > 1500

    if light_edge_missing or (light_edge_missing and dark_edge_missing):
        edge_difference_summary.append({"edge_overlay": edge_overlay_dir})

    return edge_difference_summary


# load the input image
def load_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Failed to load image at path: {image_path}")
    return image


# detect the edge inconsistency
def edge_inconsistency(light_image_path:str, dark_image_path:str, edge_overlay_dir:str, missing_edge_dir:str ):

    light_image = load_image(light_image_path)
    dark_image = load_image(dark_image_path)

    if light_image is None or dark_image is None:
        print(f"Error: Image not found or cannot be read at specified paths.")
        return
    if light_image.shape[:2] != dark_image.shape[:2]:
        dark_image = cv2.resize(dark_image, (light_image.shape[1], light_image.shape[0]))

    edge_inc_detection = edge_difference(light_image, dark_image, edge_overlay_dir, missing_edge_dir)

    return edge_inc_detection


