'''
chroma_eye repair the invisible text inconsistency

to run the script:
prerequisite
## 1. Please make sure that you have passed the absolute path to the following:
        1. add_blocker_path
        2. webdriver_path
        3.base_path
## 2.make sure your application is in dark mode.

'''
import os
import shutil
import time
import json

from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from chromaeye.chroma_repair.repair_suggestion.chroma_repair_suggestion import inconsistency_repair_suggestion
from chromaeye.chroma_repair.text_based_repair.invisible_text_repair.invisible_text_repair import \
    repair_text_inconsistency

USRPROFILE = '~/Library/Application Support/Google/Chrome/'

#---------- Extract URLs from JSON Report ----------
def extract_urls(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    url_data = []
    if "text_inconsistency" in report and "invisible_text" in report["text_inconsistency"]:
        for page in report["text_inconsistency"]["invisible_text"]["pages"]:
            url_data.append({
                "url": page["url"],
                "scroll_positions": [entry["scroll_percentage"] for entry in page["failed_text"]]
            })
    return url_data


# ---------- Initialize WebDriver ----------
def initialize_driver():
    add_blocker_path = "/chromaeye/data_collection/extension/AdBlock — block ads across the web - Chrome Web Store 6.11.1.0.crx"
    webdriver_path = "chromaeye/data_collection/chromedriver"

    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_extension(add_blocker_path)
    options.add_argument("--window-size=1920,1080")

    # Mobile emulation (optional)
    mobile_emulation = {"deviceName": "iPhone 12 Pro"}
    options.add_experimental_option('mobileEmulation', mobile_emulation)

    service = Service(webdriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    return driver

def create_folder(folder_name):
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)
    return folder_name

def get_application_name(app_url):
    parsed_url = urlparse(app_url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain.replace("www.", "", 1)
    app_name = domain.split('.')[0]
    return app_name

def repair_text_and_button_inconsistency(json_path, text_repair_output, repair_screenshot):
    try:
        if USRPROFILE == '':
            raise Exception('Please fill Google Chrome\'s user profile location')
    except:
        raise Exception('Please fill Google Chrome\'s user profile location in USRPROFILE global variable')
    urls = extract_urls(json_path)

    if not urls:
        print("No URLs found in JSON report.")
        return
    app_url = urls[0]['url']


    app_name = get_application_name(app_url)

    main_folder = create_folder(app_name)
    light_mode_folder = create_folder(os.path.join(main_folder, 'light'))
    dark_mode_folder = create_folder(os.path.join(main_folder, 'dark'))


    for index, url_entry in enumerate(urls):
        step = index + 1
        try:
            print(f"Processing {index + 1}/{len(urls)}: {url_entry['url']}")

            driver = initialize_driver()

            # Load the webpage once
            driver.get("chrome://newtab/")
            time.sleep(2)
            driver.get(url_entry["url"])
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            print("Please make sure that you are in dark mode setting.................")
            time.sleep(30)

            # Run text repair first
            invisible_text_result = repair_text_inconsistency(driver, url_entry['url'], step, app_name, light_mode_folder, dark_mode_folder, repair_screenshot)

            # Close browser after processing the URL
            print("repair processing complete...")
            driver.quit()
            time.sleep(2)
        except Exception as e:
            print(f"Skipping URL due to error: {e}")
    # Save results to JSON for text
    with open(text_repair_output, "w") as f:
        json.dump(invisible_text_result, f, indent=4)

    print("Processing completed for all URLs.")


# chroma repair
def chroma_repair(input_json_path, repair_suggestion_report, text_repair_output, repair_screenshot):
    """
    Reads the JSON file, checks for inconsistencies, and generates a repair suggestion.
    """
    try:

        # Get the repair suggestions
        inconsistency_repair_suggestion(input_json_path, repair_suggestion_report)
        repair_text_and_button_inconsistency(input_json_path, text_repair_output, repair_screenshot)
    except Exception as e:
        print(f"Error processing the file: {e}")


def main():
    base_path = "/chromaeye/example_dataset/text_based/invisible_text/developer_chrome"

    # Define paths for input and output
    input_file = os.path.join(base_path, "output/inconsistency.json")
    repair_folder = os.path.join(base_path, "repair")  # Ensure repair folder exists
    create_folder(repair_folder)  # Create repair folder if missing

    repair_suggestion_report = os.path.join(repair_folder, "repair_suggestion.json")
    text_repair_output = os.path.join(repair_folder, "text_repair.json")
    repair_screenshot = create_folder(os.path.join(repair_folder, 'repair_screenshot'))

    chroma_repair(input_file, repair_suggestion_report, text_repair_output, repair_screenshot)


if __name__ == "__main__":
    main()





