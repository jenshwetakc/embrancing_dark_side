'''
preprocessing,
check_sc_pairs.py - to check sure that we don't have any dynamic light and dark screenshots

note:
please pass the absolute path of the dataset you have collected "image_dir"
and output directory to verify the pairs of screenshots "output_dir"

'''
import shutil
import json
import os
from typing import List, Dict, Any

from chromaeye.chroma_detection.edge_based_detection.edge_based import edge_inconsistency


def create_folder(folder_name):
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)
    return folder_name


def load_json(json_path: str) -> Dict[str, Any]:
    """Load JSON file."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found at path: {json_path}")
    with open(json_path, 'r') as f:
        return json.load(f)


def check_sc_pairs(image_dir, output_dir):
    #1 Edge Inconsistency
    edge_inconsistency_output_folder = create_folder(os.path.join(output_dir, 'check_identical_pairs'))
    edge_inconsistency_detection = []

    files = sorted(
        [f for f in os.listdir(image_dir) if f.endswith('light.png')],
        key=lambda x: int(x.split('light')[0]) if x.split('light')[0].isdigit() else x
    )

    for filename in files:
        try:
            # Define base filename
            base_filename = filename.replace('light.png', '')
            print(base_filename)
            id = base_filename.split("_")[0]
            # print(id)

            # Input files
            light_image_file = os.path.join(image_dir, filename)
            dark_image_file = os.path.join(image_dir, filename.replace('light', 'dark'))

            '''Output directory'''
            # 1.Edge Inconsistency
            edge_overlay = os.path.join(edge_inconsistency_output_folder, f"{base_filename}_overlay.png")
            problematic_edge = os.path.join(edge_inconsistency_output_folder, f"{base_filename}_problematic_area.png")


            '''Inconsistency detection'''

            #1. Edge Inconsistency
            edge_output = edge_inconsistency(
                light_image_file,
                dark_image_file,
                edge_overlay,
                problematic_edge
            )


            '''Add to respective summaries'''

            # get the scroll_percentage

            def scroll_percentage(basefilename:str) -> int:
                scroll_value = int(basefilename.split("_")[-2])
                return scroll_value

            #1. Edge Inconsistency

            if edge_output:
                edge_inconsistency_detection.append({
                    "id": id,
                    "file":base_filename,
                    "scroll_percentage": scroll_percentage(base_filename),
                    "image_directory": edge_output
                })

        except Exception as e:
            print(f"Error processing file {base_filename}: {e}")

    edge_inconsistency_detection.sort(key=lambda x: x['file'])


    edge_summary_path = os.path.join(edge_inconsistency_output_folder, 'edge_inconsistency.json')

    with open(edge_summary_path, 'w') as edges_file:
        json.dump(edge_inconsistency_detection, edges_file, indent=4)


def main():

    # image with normal size
    image_dir = ''
    output_dir = ''
    check_sc_pairs(image_dir, output_dir)

if __name__ == '__main__':
    main()