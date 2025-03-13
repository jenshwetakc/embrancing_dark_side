'''
upstage ocr detection, to detect the text and bounding box area in the application screenshots
prerequisite
1. please enter your upstage api key
2. please pass the pairs of screenshots and output folder
'''

import requests
import json
import cv2
import numpy as np
import os

# Set your Upstage API key
api_key = "please enter your apli key"

# please pass the screenshot to detect the text using upstage ocr
image_folder = "/chromaeye/example_dataset/edge_based/flashscore/input/image/org_size"
output_folder = "/chromaeye/example_dataset/edge_based/flashscore/input/ocr"

# Make sure the output folder exists
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Upstage OCR API endpoint
url = "https://api.upstage.ai/v1/document-ai/ocr"
headers = {"Authorization": f"Bearer {api_key}"}

# Get the list of image files in the folder
image_files = [f for f in os.listdir(image_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]

# Loop through each image file
for filename in image_files:
    image_path = os.path.join(image_folder, filename)

    base_filename = os.path.splitext(filename)[0]
    # Send each image to the OCR API
    with open(image_path, "rb") as image_file:
        files = {"document": image_file}
        response = requests.post(url, headers=headers, files=files)

        # Check if the response was successful
        if response.status_code == 200:
            # Parse the JSON response
            ocr_result = response.json()

            # Save the OCR result to a JSON file
            json_output_path = os.path.join(output_folder, f"{base_filename}.json")
            with open(json_output_path, "w") as json_file:
                json.dump(ocr_result, json_file, indent=4)

            print(f"OCR results for {base_filename} saved to {json_output_path}")

            # Load the original image
            image = cv2.imread(image_path)

            # Loop through each page and word to get bounding box information
            for page in ocr_result['pages']:
                for word in page['words']:
                    # Get the vertices of the bounding box
                    vertices = word['boundingBox']['vertices']

                    # Extract the coordinates (x, y) from each vertex
                    pts = [(v['x'], v['y']) for v in vertices]

                    # Convert list of points to NumPy array
                    pts = np.array(pts, np.int32)
                    pts = pts.reshape((-1, 1, 2))

                    # Draw the bounding box (polygon) on the image
                    cv2.polylines(image, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

            # Save the image with bounding boxes
            output_image_path = os.path.join(output_folder, f"{base_filename}_with_boxes.png")
            cv2.imwrite(output_image_path, image)

            print(f"Image with bounding boxes saved as {output_image_path}")
        else:
            print(f"Error processing {filename}: {response.status_code} - {response.text}")






