'''
uied detection result resize the image,
so to match the result we have to resize our pairs of screenshots

prerequisites
# please pass path to the pairs of screenshots
# output you will receive an resized image similar to the uied output
'''

import cv2
import os

# please pass the absolute path
input_folder = "/chromaeye/example_dataset/edge_based/flashscore/input/image/org_size"
output_folder = "/chromaeye/example_dataset/edge_based/flashscore/input/image/uied_size"  # Folder to save results

# Create output folder if it doesn't exist
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Loop through all files in the folder
for filename in os.listdir(input_folder):
    if filename.endswith('.jpg') or filename.endswith('.png'):  # Add more extensions if needed
        # Read the image
        image_path = os.path.join(input_folder, filename)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path:{image_path}")
        image = cv2.imread(image_path)

        resized_image = cv2.resize(image, (369, 800))

        # Save the resized image in the output folder
        output_path = os.path.join(output_folder, filename)
        cv2.imwrite(output_path, resized_image)

        print(f'Resized and saved: {output_path}')

print("Resizing complete.")

'''
note: 
uied size: 369, 800
'''