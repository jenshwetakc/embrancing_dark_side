'''
chromarepair, missing text repair
'''
mport cv2
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
import os
import time


def highlight_problematic_images(driver):
    """
    Highlights images with 'black' in their filename by adding a red border.
    """
    image_elements = driver.find_elements(By.TAG_NAME, "img")  # Find all images
    problematic_images = []  # Store problematic images for later changes

    for image in image_elements:

        image_url = image.get_attribute("src")  # Get the image URL
        if image_url:
            image_name = os.path.basename(image_url)  # Extract filename

            # Check if "black" is in the name
            if "black" in image_name:
                # Scroll to the image to ensure visibility
                driver.execute_script("arguments[0].scrollIntoView();", image)
                time.sleep(1)  # Small delay for visibility

                # Apply a red border using JavaScript
                driver.execute_script("""
                    arguments[0].style.border = '3px solid red';
                    arguments[0].style.padding = '5px';
                """, image)

                problematic_images.append((image, image_url, image_name))  # Store for renaming

    return problematic_images  # Return list of problematic images for renaming

def capture_element_screenshot(driver, elem):
    """Scroll to element, highlight it, and capture a screenshot, returning the image array instead of saving."""
    try:
        # Scroll the element into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
        time.sleep(1)  # Allow the scroll to settle

        # Capture the screenshot as an image array
        screenshot = driver.get_screenshot_as_png()
        screenshot_array = np.frombuffer(screenshot, dtype=np.uint8)
        img = cv2.imdecode(screenshot_array, cv2.IMREAD_COLOR)

        return img  # Return the image instead of saving

    except Exception as e:
        print(f"Error capturing screenshot for element: {e}")
        return None



def save_side_by_side(before_img, after_img, output_path):
    """Save before and after images side by side as a single image."""

    # Check if images are valid
    if before_img is None or after_img is None:
        print(f"Error: One of the images is missing for {output_path}")
        return

    # Resize images to match the height
    if before_img.shape[0] != after_img.shape[0]:
        height = min(before_img.shape[0], after_img.shape[0])
        before_img = cv2.resize(before_img, (before_img.shape[1], height))
        after_img = cv2.resize(after_img, (after_img.shape[1], height))

    # Concatenate images horizontally
    combined_img = np.hstack((before_img, after_img))

    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save the combined image
    cv2.imwrite(output_path, combined_img)
    print(f"Side-by-side image saved: {output_path}")


def remove_highlight(driver):
    """Remove all highlights from the repaired elements."""
    try:
        driver.execute_script("""
            let elements = document.querySelectorAll('*');
            for (let el of elements) {
                el.style.border = 'none';
                el.style.fontWeight = 'normal';
            }
        """)
        print("All highlights removed.")
    except Exception as e:
        print(f"Error removing highlights: {e}")



def scroll_page(driver, folder, step):
    """Scroll through the page and take screenshots at different positions."""
    normalize_styles(driver)  # Ensure styles are reset before scrolling
    print(f"Capturing screenshots in folder: {folder}")

    scroll_intervals = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    total_height = driver.execute_script("return document.body.scrollHeight")

    for scroll_percentage in scroll_intervals:
        scroll_position = (total_height * scroll_percentage) / 100
        driver.execute_script(f"window.scrollTo(0, {scroll_position});")
        time.sleep(2)

        file_name = f'page_{scroll_percentage}'
        take_screenshot(driver, folder, file_name, step)


def take_screenshot(driver, folder, file, step):
    """Take a screenshot and save it with the naming convention: app_name_index_dark.png."""
    if not os.path.exists(folder):
        os.makedirs(folder)  # Create folder if it doesn't exist

    theme = folder.split("/")[-1]
    file_name = f"{step}_{file}_{theme}.png"
    file_path = os.path.join(folder, file_name)

    driver.save_screenshot(file_path)
    print(f"Screenshot saved: {file_path}")


def normalize_styles(driver):
    """
    Normalize styles for consistent rendering across themes.
    """
    driver.execute_script("""
        document.body.style.margin = '0';
        document.body.style.padding = '0';
        document.body.style.boxSizing = 'border-box';
        document.documentElement.style.margin = '0';
        document.documentElement.style.padding = '0';
        document.documentElement.style.boxSizing = 'border-box';
    """)
    print("Styles normalized for consistent scrolling.")

result = []
def change_image_name(driver, page_url, problematic_images, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot):
    """
    Changes the 'src' attribute of highlighted images from 'black' to 'white'.
    """
    time.sleep(3)  # Wait for a few seconds to let user see highlighted images
    page_results = {
        "page_url": page_url,
        "missing_text": [],
        "repaired_text": []
    }

    for image, image_url, image_name in problematic_images:

        side_by_side_filename = os.path.join(repair_screenshot, f"{step}_side_by_side_{app_name}.png")

        before_img = capture_element_screenshot(driver, image)
        new_image_name = image_name.replace("black", "white")  # Replace 'black' with 'white'
        new_image_url = image_url.replace(image_name, new_image_name)  # Create new URL

        print(f"Changing image: {image_name} → {new_image_name}")

        # Update the image source dynamically
        driver.execute_script("arguments[0].setAttribute('src', arguments[1])", image, new_image_url)

        time.sleep(2)
        # Remove highlight if fixed
        driver.execute_script(""" arguments[0].style.border = 'none';
                                arguments[0].style.fontWeight = 'normal';
                                              """, image)
        after_img = capture_element_screenshot(driver, image)

        time.sleep(5)

        save_side_by_side(before_img, after_img, side_by_side_filename)

        # Store problematic and repaired image names
        page_results["missing_text"].append(image_name)
        page_results["repaired_text"].append(new_image_name)

        print(page_results)

    # to collect the pairs of screenshots after repair
    # remove_highlight(driver)
    # driver.execute_script("window.scrollTo(0, 0);")
    # scroll_page(driver, dark_mode_folder, step)
    # time.sleep(2)
    # driver.refresh()
    # print('switch mode back to light')
    # time.sleep(7)
    # scroll_page(driver, light_mode_folder, step)
    # print(light_mode_folder)
    #
    # print("Image names updated successfully!")
    return page_results


def repair_missing_text_inconsistency(driver, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot):
    result = []
    problematic_images = highlight_problematic_images(driver)  # Step 1: Highlight images
    result = change_image_name(driver, page_url, problematic_images, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot)
    return result
