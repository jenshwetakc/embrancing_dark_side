## Embracing the Dark Side: Detecting and Repairing Inconsistencies between Light and Dark Modes of Web Applications
(chromaeye)

chromaeye detects GUI inconsistency between light and dark mode in web applications. Inconsistency refers to GUI elements that are not properly converted into dark mode, such as invisible icons and text.

Our approach detects four types of inconsistency:
1. Edge-based: check whether the edge of the button border and divider are equally visible in both light and dark modes.
2. Object-based: check whether the GUI elements like icon buttons are visible in both light and dark modes.
3. Text-based (invisible text, missing text): check whether the text is properly converted in dark mode.
4. Partial conversion: check whether the application supports dark mode throughout the application.


## Our environment:
- macos arm64 

- IDE- Pycharm

- Python version: 3.12 

- Chromedriver version: 139.0.7258.66 


## Quick overview of the directory

- chroma_detection - detect the inconsistency between light and dark mode screenshot pairs

- chroma_repair	- repair the inconsistency and suggest the repair approach

- data_collection- collect the dataset 

- example_dataset- sample dataset to run the quick detection


## How to replicate our work

1. Quick Run 
 - Inconsistency Detection 
   - Run chroma_eye.py
   
   - To run the file, please make sure to pass the input absolute path 
   
   - For more details: chromaeye/chroma_detection/description
   
 2. Repair 
   - Choose the inconsistency you want to repair

   - Run chroma_repair.py

   - For more description: /chromaeye/chroma_repair/description

## To replicate the work from scratch 

1. Collect the dataset

   - To collect the dataset with extension: data_with_extension.py
   
   - To collect the dataset with native application light and dark mode: native_app_datacollection.py
   
   - For more details: chromaeye/data_collection/description
   
2. Preprocessing(chromaeye/chroma_detection/pre_processing)

  -  Verify the identical pairs of screenshots: check_paris_sc.py

  -  Text detection run the upstage OCR: upstage_ocr.py

  - Detect GUI element using UIED detection - link(https://github.com/MulongXie/UIED)

  - Run: resize_image.py 

  - Run: combine_uied_ld_detection.py

3. Once you have collected the dataset and performed the preprocessing, 
   - The detection process and repair are the same as quick run

## Our experiment dataset is available at https://zenodo.org/records/15050486

