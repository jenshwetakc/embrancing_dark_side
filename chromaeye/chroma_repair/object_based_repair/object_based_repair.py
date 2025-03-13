'''
chromaeye repair the object based inconsistency

'''
import os

import cv2
from selenium.webdriver.common.by import By
import time
import hsluv
import numpy as np


# Function to convert "rgb(x, y, z)" to (R, G, B)
def parse_rgb(css_rgb):
    rgb_values = css_rgb.replace("rgba(", "").replace("rgb(", "").replace(")", "").split(",")[:3]
    return tuple(map(int, rgb_values))


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

def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])

failed_elements = []

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

def adjust_background_lightness_to_wcag(button_rgb, bg_rgb):
    """Adjusts background lightness downward until it meets WCAG contrast ratio."""

    h, s, original_l = hsluv.rgb_to_hsluv([c / 255.0 for c in bg_rgb])
    print(f"Original Lightness: {original_l}")

    if original_l <= 50:
        return bg_rgb  # No adjustment needed

    # Start reducing lightness until it reaches 55
    l = original_l
    min_wcag_contrast = 3
    new_bg_rgb = tuple(bg_rgb)

    while l >= 55:  # Decrease lightness step by step
        print(f"Current Lightness: {l}")
        new_bg_rgb = hsluv.hsluv_to_rgb((h, s, l))
        new_bg_rgb = tuple(int(c * 255) for c in new_bg_rgb)

        contrast = contrast_ratio(button_rgb, new_bg_rgb)

        if contrast >= min_wcag_contrast:
            return new_bg_rgb

        l -= 1  # Reduce lightness step by step

    return new_bg_rgb

results = []

def detect_button_inconsistency(driver):
    button_elements = driver.find_elements(By.XPATH, "//button | //a[contains(@class, 'btn') or contains(@role, 'button')]")
    failed_elements = []

    for elem in button_elements:
        try:
            # Ensure the element has visible text
            if elem.text.strip():
                button_color = elem.value_of_css_property("color")

                bg_color = get_computed_background_color(elem, driver)
                # Convert to (R, G, B) format
                fg_color = parse_rgb(button_color)
                bg_color = parse_rgb(bg_color)

                # Calculate contrast ratio
                ratio = contrast_ratio(fg_color, bg_color)
                # Only store elements with text that fail contrast
                if ratio < 3:
                    failed_elements.append((elem, fg_color, bg_color))

        except Exception as e:
            print(f"Skipping an element due to error: {e}")
    return failed_elements



def detect_img_inconsistency(driver):
    icon_elements = driver.find_elements(By.XPATH,
                                         "//img | //*[contains(@class, 'icon') or contains(@class, 'fa') or contains(@class, 'material-icons')]")
    failed_elements = []

    for elem in icon_elements:
        try:
            # Ensure the element has visible text
            if elem.text.strip():
                button_color = elem.value_of_css_property("color")

                bg_color = get_computed_background_color(elem, driver)

                # Convert to (R, G, B) format
                fg_color = parse_rgb(button_color)
                bg_color = parse_rgb(bg_color)

                # Calculate contrast ratio
                ratio = contrast_ratio(fg_color, bg_color)

                # Only store elements with text that fail contrast
                if ratio < 3:
                    failed_elements.append((elem, fg_color, bg_color))

        except Exception as e:
            print(f"Skipping an element due to error: {e}")
    return failed_elements


def detect_link_inconsistency(driver):
    failed_svg_elements = []

    # link
    link_elements = driver.find_elements(By.TAG_NAME, "a")

    for link in link_elements:
        try:
            # Get computed fill and stroke color
            fg_color_rgba = link.value_of_css_property("color")

            fg_color = parse_rgb(fg_color_rgba)

            bg_color = get_computed_background_color(link, driver)

            # Calculate contrast ratio
            ratio = contrast_ratio(fg_color, bg_color)

            if ratio < 3:
                failed_svg_elements.append((link, fg_color, bg_color))

        except Exception as e:
            print(f"Skipping an element due to error: {e}")
    return failed_svg_elements


def detect_svg_inconsistency(driver):
    failed_svg_elements = []

    # SVG ICONS CHECK
    # either
    # svg_elements = driver.find_elements(By.TAG_NAME, "svg")
    #or
    svg_elements = driver.find_elements(By.TAG_NAME, "a")

    for svg in svg_elements:
        try:
            # Get computed fill and stroke color
            fill_color = driver.execute_script("return window.getComputedStyle(arguments[0]).getPropertyValue('fill');",
                                               svg)
            stroke_color = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).getPropertyValue('stroke');", svg)
            inherited_color = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).getPropertyValue('color');", svg)

            # Resolve `currentColor` by using the inherited color
            if fill_color == "currentColor":
                fill_color = inherited_color
            if stroke_color == "currentColor":
                stroke_color = inherited_color

            # Prefer fill over stroke
            icon_color = fill_color if fill_color not in ["none", "", "transparent"] else stroke_color
            if icon_color in ["none", "", "transparent"]:
                continue  # Skip if no valid color is found

            # Get background color
            bg_color = get_computed_background_color(svg, driver)
            # Convert to RGB
            fg_color = parse_rgb(icon_color)
            bg_color = parse_rgb(bg_color)

            # Calculate contrast ratio
            ratio = contrast_ratio(fg_color, bg_color)

            if ratio < 3:
                failed_svg_elements.append((svg, fg_color, bg_color))

        except Exception as e:
            print(f"Skipping an element due to error: {e}")
    return failed_svg_elements


def highlight_inconsistency(driver, failed_elements):
    # Inject JavaScript to highlight failed elements
    for elem, _, _ in failed_elements:
        driver.execute_script("""
            arguments[0].style.border = '2px solid red';
            arguments[0].style.fontWeight = 'bold';
        """, elem)

    time.sleep(10)

def perform_repair(driver, failed_elements, page_url):

    for (elem, fg_color, bg_color) in failed_elements:
        fg_hex = rgb_to_hex(fg_color)
        bg_hex = rgb_to_hex(bg_color)
        page_results = {
            "page_url": page_url,
            "repaired_color": [],
            "unfixed_color": []
        }
        try:
            # Convert background color to HSLuv
            h_bg, s_bg, l_bg = hsluv.rgb_to_hsluv([c / 255.0 for c in bg_color])
            print(f"Original Background Lightness: {l_bg}")

            # Check foreground color is in the white range (200, 200, 200) to (255, 255, 255)
            is_foreground_white = all(200 <= c <= 255 for c in fg_color)


            if 50 < l_bg < 80 and is_foreground_white:
                    print("Contrast fails. Foreground is white. Background is too light. Adjusting...")

                    new_bg_color = adjust_background_lightness_to_wcag(fg_color, bg_color)
                    new_bg_hex = rgb_to_hex(new_bg_color)

                    new_ratio = contrast_ratio(fg_color, new_bg_color)
                    if new_ratio >= 3:
                        new_color_css = f"rgb({new_bg_color[0]}, {new_bg_color[1]}, {new_bg_color[2]})"
                        driver.execute_script(f"arguments[0].style.backgroundColor = '{new_color_css}';", elem)

                        # Remove highlight if fixed
                        driver.execute_script("""
                                arguments[0].style.border = 'none';
                                arguments[0].style.fontWeight = 'normal';
                            """, elem)

                        page_results["repaired_color"].append({
                            "problematic_color": bg_hex,
                            "repaired_text_color": new_bg_hex,
                        })
                    else:
                        print("Could not repair background color, keeping highlight.")
                        page_results["unfixed_button"].append({
                            "unfixed_color": fg_hex,
            })
            else:
                    print("Conditions not met for adjustment. Skipping...")

        except Exception as e:
            print(f"Error processing element: {e}")

    print("Background color adjustments completed.")

    return results

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
def adjust_svg_lightness(fg_rgb, bg_rgb):
    """Adjusts text color by increasing lightness until it meets WCAG contrast ratio."""
    h, s, l = hsluv.rgb_to_hsluv([c / 255.0 for c in fg_rgb])
    l = max(70.0, l)
    min_wcag_contrast = 3
    new_rgb = tuple(fg_rgb)

    while l <= 80:
        new_rgb = hsluv.hsluv_to_rgb((h, s, l))
        new_rgb = tuple(int(c * 255) for c in new_rgb)

        contrast = contrast_ratio(new_rgb, bg_rgb)

        if contrast >= min_wcag_contrast:
            return new_rgb

        l += 1  # Increase lightness step by step

    return new_rgb

# def perform_svg_repair(driver, failed_elements, page_url):
def perform_svg_repair(driver,failed_svg_elements, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot):
    """Repair text inconsistency and store only from the second failed/repaired occurrence."""

    global results
    page_results = {
        "page_url": page_url,
        "repaired_svg_color": [],
        "unfixed_svg_color": []
    }
    # print('sappname', step)
    for index, (elem, fg_color, bg_color) in enumerate(failed_svg_elements):

        # Generate unique filename for the side-by-side comparison image
        side_by_side_filename = os.path.join(repair_screenshot, f"{step}_side_by_side_{app_name}_{index}.png")

        original_hex = rgb_to_hex(fg_color)
        bg_hex = rgb_to_hex(bg_color)


        try:
            # Check if background is dark
            bg_luminance = luminance(bg_color)

            if bg_luminance < 0.50:
                new_fg_color = adjust_svg_lightness(fg_color, bg_color)
                new_fg_hex = rgb_to_hex(new_fg_color)
                new_ratio = contrast_ratio(new_fg_color, bg_color)

                # Capture the before screenshot (in memory, not saving)
                before_img = capture_element_screenshot(driver, elem)

                if new_ratio >= 3:
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

                    page_results["repaired_svg_color"].append({
                            # "text": text_content,
                            "original_svg_color": original_hex,
                            "repaired_svg_color": new_fg_hex,
                            "background_color": bg_hex
                    })
                else:
                    print("Could not repair color, keeping highlight.")

                    # Store unfixed texts from the second occurrence
                    # if index > 0:
                    page_results["unfixed_svg_color"].append({
                            # "text": text_content,
                            "original_color": original_hex,
                            "background_color": bg_hex
                    })

        except Exception as e:
            print(f"Error processing element: {e}")

    results.append(page_results)

    # to take the screenshot after the repair
    # print("repair completed")
    # # remove_highlight(driver)
    # driver.execute_script("window.scrollTo(0, 0);")
    # scroll_page(driver, dark_mode_folder, step)
    # time.sleep(2)
    # driver.refresh()
    # print('switch mode back to light')
    # time.sleep(7)
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
    print(f"Capturing screenshots in folder: {folder}")

    scroll_intervals = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    total_height = driver.execute_script("return document.body.scrollHeight")

    for scroll_percentage in scroll_intervals:
        scroll_position = (total_height * scroll_percentage) / 100
        driver.execute_script(f"window.scrollTo(0, {scroll_position});")
        time.sleep(2)

        file_name = f'page_{scroll_percentage}'
        take_screenshot(driver, folder, file_name, step)


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


def take_screenshot(driver, folder, file, step):
    """Take a screenshot and save it with the naming convention: app_name_index_dark.png."""
    if not os.path.exists(folder):
        os.makedirs(folder)  # Create folder if it doesn't exist

    theme = folder.split("/")[-1]
    file_name = f"{step}_{file}_{theme}.png"
    file_path = os.path.join(folder, file_name)

    driver.save_screenshot(file_path)
    print(f"Screenshot saved: {file_path}")

# def repair_object_inconsistency(driver, page_url, output_json):
def repair_object_inconsistency(driver, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot):
    print(f"Running button repair on {page_url}...")

    # # # # Detect button issues
    # failed_button_elements = detect_button_inconsistency(driver)
    # highlight_inconsistency(driver, failed_elements)
    #
    # failed_btn_result = []
    #
    # # Repair the button inconsistencies
    # if failed_elements:
    #     failed_btn_result = perform_repair(driver, failed_button_elements, page_url)
    #
    # failed_img_result = []
    # failed_img_elements = detect_img_inconsistency(driver)
    # highlight_inconsistency(driver, failed_img_elements)
    #
    # if failed_img_elements:
    #     # perform_repair(driver, failed_elements, page_url)
    #     failed_img_result = perform_repair(driver,failed_img_elements, page_url)

    failed_svg_elements = detect_svg_inconsistency(driver)
    highlight_inconsistency(driver, failed_svg_elements)
    if failed_svg_elements:
        results = perform_svg_repair(driver,failed_svg_elements, page_url, step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot)
    # results = failed_btn_result+ failed_img_result + failed_svg_result

    return results



