
import cv2
import numpy as np
from scipy.spatial import cKDTree
import os

def edge_difference(light_image_path, dark_image_np):
    distance_threshold = 3,
    canny_thresh1 = 10,
    canny_thresh2 = 55,
    edge_count_threshold = 5000

    if not os.path.exists(light_image_path):
        print(f" Light image does not exist: {light_image_path}")
        return {"skip_dark": False, "reason": "No light image"}

    light_image = cv2.imread(light_image_path)
    dark_image = dark_image_np

    # Convert to grayscale
    light_gray = cv2.cvtColor(light_image, cv2.COLOR_BGR2GRAY)
    dark_gray = cv2.cvtColor(dark_image, cv2.COLOR_BGR2GRAY)

    # Detect edges
    light_edges = cv2.Canny(light_gray, 10, 50)
    dark_edges = cv2.Canny(dark_gray, 10, 50)

    # Extract edge coordinates
    light_coords = np.column_stack(np.where(light_edges > 0))
    dark_coords = np.column_stack(np.where(dark_edges > 0))

    if light_coords.size == 0 or dark_coords.size == 0:
        return {"skip_dark": True, "reason": "No edges detected"}

    # Nearest-neighbor matching
    light_tree = cKDTree(light_coords)
    dark_tree = cKDTree(dark_coords)

    distances_light, _ = dark_tree.query(light_coords)
    distances_dark, _ = light_tree.query(dark_coords)

    missing_light_coords = light_coords[distances_light > distance_threshold]
    missing_dark_coords = dark_coords[distances_dark > distance_threshold]

    # Create masks
    missing_light_mask = np.zeros_like(light_edges, dtype=np.uint8)
    missing_dark_mask = np.zeros_like(dark_edges, dtype=np.uint8)
    missing_light_mask[missing_light_coords[:, 0], missing_light_coords[:, 1]] = 255
    missing_dark_mask[missing_dark_coords[:, 0], missing_dark_coords[:, 1]] = 255

    count_light = np.count_nonzero(missing_light_mask)
    count_dark = np.count_nonzero(missing_dark_mask)

    return {
        "light_edge_missing": count_light > edge_count_threshold,
        "dark_edge_missing": count_dark > edge_count_threshold,
        "light_edge_count": count_light,
        "dark_edge_count": count_dark,
        "skip_dark": (count_light > edge_count_threshold or count_dark > edge_count_threshold),
        "reason": "Edge mismatch"
    }
