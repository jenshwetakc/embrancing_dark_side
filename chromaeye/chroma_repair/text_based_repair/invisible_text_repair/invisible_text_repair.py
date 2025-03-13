
'''
invisible text repair

'''

import os
import cv2
import numpy as np
import time
import re
import hsluv

from selenium.webdriver.common.by import By
from coloraide import Color



#either
# Function to convert "rgb(x, y, z)" to (R, G, B) (for normal rgb you can use this function)
# def parse_rgb(css_rgb):
#     rgb_values = css_rgb.replace("rgba(", "").replace("rgb(", "").replace(")", "").split(",")[:3]
#     return tuple(map(int, rgb_values))

 # to work with oklch use this function
#issues Skipping an element due to error: module 'hsluv' has no attribute 'oklch_to_rgb'

#or

def parse_rgb(css_color):
    if css_color.startswith("rgb"):
        # Parse RGB(A)
        rgb_values = css_color.replace("rgba(", "").replace("rgb(", "").replace(")", "").split(",")[:3]
        return tuple(map(int, rgb_values))

    elif css_color.startswith("oklch"):
        # Extract numbers from OKLCH format
        match = re.findall(r"[-+]?\d*\.\d+|\d+", css_color)
        if match and len(match) == 3:
            l, c, h = map(float, match)  # Convert to float
            # Convert OKLCH to RGB
            color = Color(f"oklch({l} {c} {h})")
            rgb = color.convert("srgb").coords()
            return tuple(int(c * 255) for c in rgb)  # Convert to 0-255 scale

    elif css_color.startswith("color(srgb"):
        # Extract SRGB values
        match = re.findall(r"[-+]?\d*\.\d+|\d+", css_color)
        if match and len(match) == 3:
            r, g, b = map(float, match)  # Convert to float
            return tuple(int(c * 255) for c in (r, g, b))  # Convert to 0-255 range

    raise ValueError(f"Unsupported color format: {css_color}")

# WCAG contrast ratio calculation
def luminance(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(fg, bg):
    lum1 = luminance(fg)
    lum2 = luminance(bg)
    return (max(lum1, lum2) + 0.05) / (min(lum1, lum2) + 0.05)

# Convert RGB to HSLuv
def rgb_to_hsluv(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    return hsluv.rgb_to_hsluv((r, g, b))

# Convert HSLuv to RGB
def hsluv_to_rgb(hsluv_color):
    return tuple(int(c * 255) for c in hsluv.hsluv_to_rgb(hsluv_color))

# Convert RGB to HEX
def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])

def get_computed_text_color(element, driver):

    while element:
        # Get computed background color using JavaScript
        fg_color = driver.execute_script("return window.getComputedStyle(arguments[0]).color;", element)

        # If background is not fully transparent, return it
        if fg_color and "rgba(0, 0, 0, 0)" not in fg_color:
            return fg_color

        # Move up to the parent element
        element = driver.execute_script("return arguments[0].parentElement;", element)

    # Default to page background color if no background color is found
    return driver.execute_script("return window.getComputedStyle(document.body).color;")
def get_computed_background_color(element, driver):
    """
    Get the first non-transparent background color by traversing up the DOM.
    """
    while element:
        # Get computed background color using JavaScript
        bg_color = driver.execute_script("return window.getComputedStyle(arguments[0]).backgroundColor;", element)

        # If background is not fully transparent, return it
        if bg_color and "rgba(0, 0, 0, 0)" not in bg_color:
            return bg_color

        # Move up to the parent element
        element = driver.execute_script("return arguments[0].parentElement;", element)

    # Default to page background color if no background color is found
    return driver.execute_script("return window.getComputedStyle(document.body).backgroundColor;")

def adjust_lightness_to_wcag(text_rgb, bg_rgb):
    """Adjusts text color by increasing lightness until it meets WCAG contrast ratio."""
    h, s, l = hsluv.rgb_to_hsluv([c / 255.0 for c in text_rgb])
    l = max(50.0, l)  # Ensure starting lightness is at least 50%

    min_wcag_contrast = 4.6
    new_rgb = tuple(text_rgb)

    while l <= 80:
        new_rgb = hsluv.hsluv_to_rgb((h, s, l))
        new_rgb = tuple(int(c * 255) for c in new_rgb)

        contrast = contrast_ratio(new_rgb, bg_rgb)

        if contrast >= min_wcag_contrast:
            return new_rgb

        l += 1  # Increase lightness step by step

    return new_rgb



def adjust_text_darker(text_rgb, bg_rgb):
    """Adjusts text color by increasing lightness until it meets WCAG contrast ratio."""
    h, s, l = hsluv.rgb_to_hsluv([c / 255.0 for c in text_rgb])
    # l = max(50.0, l)  # Ensure starting lightness is at least 50%

    min_wcag_contrast = 4.6
    new_rgb = tuple(text_rgb)

    while l >= 10:
        new_rgb = hsluv.hsluv_to_rgb((h, s, l))
        new_rgb = tuple(int(c * 255) for c in new_rgb)

        contrast = contrast_ratio(new_rgb, bg_rgb)

        if contrast >= min_wcag_contrast:
            return new_rgb

        l -= 1  # Increase lightness step by step

    return new_rgb

# def adjust_text_darker(text_rgb, bg_rgb):
#     """Adjusts background lightness downward until it meets WCAG contrast ratio."""
#
#     h, s, original_l = hsluv.rgb_to_hsluv([c / 255.0 for c in text_rgb])
#     print(f"Original Lightness: {original_l}")
#
#     if original_l <= 50:
#     #     return text_rgb  # No adjustment needed
#
#     # Start reducing lightness until it reaches 55
#     l = original_l
#     min_wcag_contrast = 4.5
#     new_txt_rgb = tuple(text_rgb)
#
#     while l >= 55:  # Decrease lightness step by step
#         print(f"Current Lightness: {l}")
#         new_txt_rgb = hsluv.hsluv_to_rgb((h, s, l))
#         new_txt_rgb = tuple(int(c * 255) for c in new_txt_rgb)
#
#         contrast = contrast_ratio(text_rgb, new_txt_rgb)
#
#         if contrast >= min_wcag_contrast:
#             return new_txt_rgb
#
#         l -= 1

def detect_text_inconsistency(driver):
    """Detects text elements with low contrast and returns a list of failed elements."""
    text_elements = driver.find_elements(By.XPATH, "//*[text()]")
    failed_elements = []

    for elem in text_elements:
        try:
            if elem.text.strip():
                text_content =elem.text.strip()

                # text_color = elem.value_of_css_property("color")
                text_color = get_computed_text_color(elem, driver)
                bg_color = get_computed_background_color(elem, driver)

                fg_color = parse_rgb(text_color)
                bg_color = parse_rgb(bg_color)
                ratio = contrast_ratio(fg_color, bg_color)

                if ratio < 4.5:
                    failed_elements.append((elem, text_content, fg_color, bg_color))

        except Exception as e:
            print(f"Skipping an element due to error: {e}")

    return failed_elements


def highlight_text_inconsistency(driver, failed_elements):
    """Highlights elements that fail contrast requirements."""
    for elem,_, _, _ in failed_elements:
        driver.execute_script("""
                arguments[0].style.border = '2px solid red';
            """, elem)

# store results in json


def is_dark_background(bg_color):
    """Determine if an RGB color is a dark background based on perceived brightness."""
    r, g, b = bg_color
    brightness = (0.299 * r) + (0.587 * g) + (0.114 * b)
    return brightness

def is_dark_color(rgb, threshold=50):
    """Check if an RGB color is dark based on a brightness threshold."""
    return all(channel <= threshold for channel in rgb)

def is_light_color(rgb, threshold=128):
    """
    Check if an RGB color is dark based on perceived brightness.
    """
    r, g, b = rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance


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

def is_white_color(color, threshold=200):
    """
    Checks if the given color is white based on RGB values.
    """
    r, g, b = color
    return r >= threshold and g >= threshold and b >= threshold


results = []

# def perform_repair(driver, failed_elements, page_url, step):
def perform_repair(driver, failed_elements, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot):
    """Repair text inconsistency and store only from the second failed/repaired occurrence."""

    global results
    page_results = {
        "page_url": page_url,
        "repaired_texts": [],
        "unfixed_texts": []
    }

    for index, (elem, text_content, fg_color, bg_color) in enumerate(failed_elements):

        # Generate unique filename for the side-by-side comparison image
        side_by_side_filename = os.path.join(repair_screenshot, f"{step}_side_by_side_{app_name}_{index}.png")

        original_hex = rgb_to_hex(fg_color)
        bg_hex = rgb_to_hex(bg_color)

        try:
            # Check if background is dark
            bg_luminance = luminance(bg_color)

            # if bg_luminance < 0.5 and is_dark_color(bg_color, threshold=57):
            if bg_luminance < 0.48 and is_dark_color(bg_color, threshold=57):


                new_fg_color = adjust_lightness_to_wcag(fg_color, bg_color)
                new_fg_hex = rgb_to_hex(new_fg_color)
                new_ratio = contrast_ratio(new_fg_color, bg_color)

                # Capture the before screenshot (in memory, not saving)
                before_img = capture_element_screenshot(driver, elem)

                if new_ratio >= 4.5:
                    new_color_css = f"rgb({new_fg_color[0]}, {new_fg_color[1]}, {new_fg_color[2]})"

                    # Apply the new color
                    driver.execute_script(f"arguments[0].style.color = '{new_color_css}';", elem)

                    # Remove highlight if fixed
                    driver.execute_script("""
                                           arguments[0].style.border = 'none';
                                           arguments[0].style.fontWeight = 'normal';
                                       """, elem)
                    time.sleep(2)

                    # Capture the after screenshot (in memory, not saving)
                    after_img = capture_element_screenshot(driver, elem)

                    # Save the side-by-side comparison image
                    save_side_by_side(before_img, after_img, side_by_side_filename)

                    # Store results
                    # if index > 0:
                    page_results["repaired_texts"].append({
                            "text": text_content,
                            "original_text_color": original_hex,
                            "repaired_text_color": new_fg_hex,
                            "background_color": bg_hex
                    })
                else:
                    print("Could not repair color, keeping highlight.")

                    # Store unfixed texts from the second occurrence
                    # if index > 0:
                    page_results["unfixed_texts"].append({
                            "text": text_content,
                            "original_color": original_hex,
                            "background_color": bg_hex
                    })

            # elif bg_luminance > 0.50 or not is_light_color(bg_color, threshold=75):
            # add the condition to check for the white text - may be we don't need this codition?
            # elif (bg_luminance > 0.70 or not is_light_color(bg_color, threshold=75)) and is_white_color(fg_color):
            #
            #
            #     new_fg_color = adjust_text_darker(fg_color, bg_color)
            #
            #     new_fg_hex = rgb_to_hex(new_fg_color)
            #     new_ratio = contrast_ratio(new_fg_color, bg_color)
            #
            #     # Capture the before screenshot (in memory, not saving)
            #     before_img = capture_element_screenshot(driver, elem)
            #
            #     if new_ratio >= 4.5:
            #         new_color_css = f"rgb({new_fg_color[0]}, {new_fg_color[1]}, {new_fg_color[2]})"
            #
            #         # Apply the new color
            #         driver.execute_script(f"arguments[0].style.color = '{new_color_css}';", elem)
            #
            #         # Remove highlight if fixed
            #         driver.execute_script("""
            #                                arguments[0].style.border = 'none';
            #                                arguments[0].style.fontWeight = 'normal';
            #                            """, elem)
            #         time.sleep(2)
            #
            #         # Capture the after screenshot (in memory, not saving)
            #         after_img = capture_element_screenshot(driver, elem)
            #
            #         # Save the side-by-side comparison image
            #         save_side_by_side(before_img, after_img, side_by_side_filename)
            #
            #         # Store results
            #         # if index > 0:
            #         page_results["repaired_texts"].append({
            #                 "text": text_content,
            #                 "original_text_color": original_hex,
            #                 "repaired_text_color": new_fg_hex,
            #                 "background_color": bg_hex
            #         })
            #
            #     else:
            #         print("Could not repair color, keeping highlight.")
            #
            #         # Store unfixed texts from the second occurrence
            #         # if index > 0:
            #         page_results["unfixed_texts"].append({
            #                 "text": text_content,
            #                 "original_color": original_hex,
            #                 "background_color": bg_hex
            #         })

        except Exception as e:
            print(f"Error processing element: {e}")

    results.append(page_results)

    ##---- to take the screenshot pair after the repair

    # print("text color repair completed")
    # remove_highlight(driver)
    # # driver.execute_script("window.scrollTo(0, 0);")
    # scroll_page(driver, dark_mode_folder, step)
    # time.sleep(2)
    # driver.refresh()
    # print('switch mode back to light')
    # time.sleep(10)
    # scroll_page(driver, light_mode_folder, step)
    # print(light_mode_folder)
    return results


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

def repair_text_inconsistency(driver, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot):
    print(f"Running text repair on {page_url}...")

    # Detect text issues
    failed_elements = detect_text_inconsistency(driver)
    highlight_text_inconsistency(driver, failed_elements)
    results = []
    if failed_elements:
        results = perform_repair(driver, failed_elements, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot)

    return results
