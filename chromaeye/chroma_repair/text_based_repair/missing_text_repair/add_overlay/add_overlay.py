'''
chromaeye: add overlay in darkmode
'''

from selenium import webdriver
import json
import time
from PIL import Image
import io
import base64


def load_json(json_file):
    """
    Load the JSON file containing missing text information.
    """
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data


def capture_screenshot(driver, bounding_box):
    """
    Capture screenshot of a specific area defined by the bounding box and return the image.
    """
    # Take a full-page screenshot
    screenshot = driver.get_screenshot_as_base64()
    screenshot = Image.open(io.BytesIO(base64.b64decode(screenshot)))

    # Extract bounding box coordinates
    x1, y1, x2, y2 = bounding_box

    # Crop the screenshot to the bounding box area
    cropped_image = screenshot.crop((x1, y1, x2, y2))
    return cropped_image


def save_image(image, file_name):
    """
    Save the image to a file.
    """
    image.save(file_name)


def add_overlay(driver, base64_image):
    """
    Add the cropped image as an overlay on the page using <div> elements.
    """
    overlay_script = f"""
    var overlayDiv = document.createElement('div');
    overlayDiv.style.position = 'fixed';
    overlayDiv.style.top = '0';
    overlayDiv.style.left = '0';
    overlayDiv.style.width = '100%';
    overlayDiv.style.height = '100%';
    overlayDiv.style.zIndex = '1000';
    overlayDiv.style.backgroundImage = 'url(data:image/png;base64,{base64_image})';
    overlayDiv.style.backgroundRepeat = 'no-repeat';
    overlayDiv.style.backgroundPosition = 'center';
    document.body.appendChild(overlayDiv);
    """
    driver.execute_script(overlay_script)


def scroll_to_position(driver, scroll_percentage):
    """
    Scroll the page to a specific percentage position.
    """
    scroll_script = f"window.scrollTo(0, document.body.scrollHeight * {scroll_percentage / 100});"
    driver.execute_script(scroll_script)
    time.sleep(2)  # Wait for the page to adjust


def main(json_file, light_mode=True):
    # Load the JSON file
    data = load_json(json_file)
    missing_text_data = data['text_inconsistency']['missing_text']['pages'][0]
    url = missing_text_data['url']
    scroll_percentage = missing_text_data['missing_text'][0]['scroll_percentage']
    bounding_box = missing_text_data['missing_text'][0]['bounding_box']


    # Setup Selenium driver for light or dark mode
    options = webdriver.ChromeOptions()
    options.add_experimental_option("mobileEmulation", {"deviceName": "iPhone 12 Pro"})
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(5)  # Allow the page to load fully

    # Scroll to the required position
    scroll_to_position(driver, scroll_percentage)
    time.sleep(2)

    if light_mode:
        # Capture screenshot of the bounding box in light mode
        cropped_image = capture_screenshot(driver, bounding_box)

        # Save the cropped image
        save_image(cropped_image, f"{scroll_percentage}_light.png")

        # Convert the cropped image to base64 for overlaying later
        buffered = io.BytesIO()
        cropped_image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

        driver.quit()

        # Return the base64 encoded image
        return base64_image

    else:
        # Return None if we are capturing in dark mode
        return None


def process_dark_mode(json_file, base64_image):
    # Load the JSON file
    data = load_json(json_file)
    missing_text_data = data['text_inconsistency']['missing_text']['pages'][0]
    url = missing_text_data['url']
    scroll_percentage = missing_text_data['missing_text'][0]['scroll_percentage']

    # Setup Selenium driver for dark mode
    options = webdriver.ChromeOptions()
    options.add_experimental_option("mobileEmulation", {"deviceName": "iPhone 12 Pro"})
    driver = webdriver.Chrome(options=options)
    time.sleep(5)
    print('please set the application in the dark mode')
    driver.get(url)
    time.sleep(5)  # Allow the page to load fully

    # Scroll to the same position in dark mode
    scroll_to_position(driver, scroll_percentage)
    time.sleep(2)

    # Overlay the previously captured image
    if base64_image:
        add_overlay(driver, base64_image)

        # Capture the screenshot of the comparison
        driver.get_screenshot_as_file(f"{scroll_percentage}_comparison.png")

    time.sleep(10)
    # Close the driver
    driver.quit()


# Example usage
json_file = '/chromaeye/example_dataset/text_based/missing_text/es/output/inconsistency.json'
base64_image = main(json_file, light_mode=True)
time.sleep(2)
process_dark_mode(json_file, base64_image)