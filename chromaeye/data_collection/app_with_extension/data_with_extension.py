'''
chromaeye: collect the dataset with application in light mode and use extension to convert the application in dark mode

In few scenario extension doesnot apply the dark mode automatically in that case you have to toggle button in the extension which will appear at the top of the chrome
browser. Example of the extension that will not toggle automatically is (dark mode for web).

Note:
    please pass the path to
    1. add blocker extention
    2. you target extension file
    3. path to "metafile" to save the information of visited url

'''
import json
import logging
import os
import shutil
import time
import random
import re
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



USRPROFILE = '~/Library/Application Support/Google/Chrome/'


# applications
# url = "https://www.healthline.com/"
url = "https://www.zoho.com/"

#extension
webdriver_path = "/chroma_eye/data_collection/chromedriver"
base_path = "/chroma_eye/data_collection/extension"

extension_path = os.path.join(base_path, "Dark Theme - Dark Reader for Chrome - Chrome Web Store 1.0.9.0.crx")
add_blocker_path = os.path.join(base_path, "AdBlock — block ads across the web - Chrome Web Store 6.11.1.0.crx")




def setup_driver(extension_path=None):
    option = Options()
    option.add_argument('--ignore-certificate-errors')
    option.add_argument("--disable-notifications")

    # mobile emulator
    mobile_emulation = {
        "deviceName": "iPhone 12 Pro"  # Corrected device name
    }
    option.add_experimental_option('mobileEmulation', mobile_emulation)


    service = Service(webdriver_path)
    option.add_extension(add_blocker_path)

    if extension_path:
        option.add_extension(extension_path)
    driver = webdriver.Chrome(service=service, options=option)

    return driver

def start_web_application(driver):
    """Launches the web application."""
    driver.get(url)
    time.sleep(2)

# screenshots

def create_folder(folder_name):
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)
    return folder_name

def take_screenshot(driver, folder_name, scroll_per, step):
    page_title = driver.title
    application_name = get_application_name(driver)
    page_name = page_title[:12]
    clean_title = re.sub(r'[^\w\s-]', '', page_name).strip().replace(' ', '')

    theme = 'light' if 'light' in folder_name.lower() else 'dark'
    id = f"{step}-{clean_title}"
    file_name = f"{id}_{scroll_per}_{theme}.png"

    file_path = os.path.join(folder_name, file_name)
    screenshot_binary = driver.get_screenshot_as_png()

    # Save the binary data to an image file
    with open(file_path, 'wb') as file:
        file.write(screenshot_binary)
    print(f'Screenshot taken: {file_path}')

    # save the information of the page title, visited url
    save_screenshot_metadata(id, page_title, driver.current_url, application_name)

def save_screenshot_metadata(screenshot_id, page_title, page_url, application_name):
    # path to save the explored url
    metadata_file = f'/chroma_eye/data_collection/meta_data/{application_name}.json'

    # Initialize metadata structure
    metadata = {"applications": [], "screenshots": {}}

    # Load existing metadata if available
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r', encoding="utf-8") as file:
            try:
                metadata = json.load(file)
            except json.JSONDecodeError:
                metadata = {"applications": {}, "screenshots": {}}

    # Add application name at the higher level (only if it's not already in the list)
    if application_name not in metadata["applications"]:
        metadata["applications"].append(application_name)

    # Save screenshot metadata under the "screenshots" key
    metadata["screenshots"][screenshot_id] = {
        "id": screenshot_id,
        "page_title": page_title,
        "url": page_url,
    }

    # Save updated metadata back to the file
    with open(metadata_file, 'w', encoding="utf-8") as file:
        json.dump(metadata, file, indent=4)

# MENU BAR

def get_menubar_element(driver):
    try:
        nav_elements = driver.find_elements(By.TAG_NAME, 'nav')
        print('len of nav tag ',len(nav_elements))
        visible_nav = None

        for nav in nav_elements:
            if nav.is_displayed():
                visible_nav = nav
                break

        if not visible_nav:
            header_element = driver.find_elements(By.TAG_NAME, 'header')
            for header in header_element:
                if header.is_displayed():
                    visible_nav = header
                    break

        if not visible_nav:
            logging.error('No visible element found')
            return

        logging.info('found visible element')

        nav_items = visible_nav.find_elements(By.XPATH, './/span | .//a | .//button | .//li')
        time.sleep(2)
        print('nav item length',len(nav_items))

        visible_nav_items = [item for item in nav_items if item.is_displayed()]
        print('visible_nav_items length', len(visible_nav_items))
        return visible_nav_items

    except Exception as e:
        print(e)

def get_selected_element(load_from_list, visible_nav_items):
    global selected_element_positions
    if load_from_list and selected_element_positions:
        selected_elements = [visible_nav_items[pos] for pos in selected_element_positions]
    else:
        selected_element = random.sample(range(len(visible_nav_items)), 3)
        selected_element_positions = selected_element
        selected_elements = [visible_nav_items[pos] for pos in selected_element_positions]
    return selected_elements


def hover_over_nav_elements(driver, folder, load_from_list=False):
    wait = WebDriverWait(driver, 10)
    global selected_element_positions

    try:


        visible_nav_items = get_menubar_element(driver)


        selected_elements = get_selected_element(load_from_list, visible_nav_items)

        actions = ActionChains(driver)
        for index, item in enumerate(selected_elements):
            step = 'nav'
            try:
                wait.until(EC.visibility_of(item))
                wait.until(EC.element_to_be_clickable(item))
                scroll_to_button(driver, item)
                actions.move_to_element(item).perform()
                print(f"Hovered over item {index + 1}/{len(selected_elements)}: {item.text or item.get_attribute('href')}")
                take_screenshot(driver, folder, f'hover{index + 1}', step)
                time.sleep(2)
            except Exception as e:
                print(f"Failed to interact with item {index + 1}/{len(selected_elements)}: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")



# BUTTON
def scroll_to_button(driver, button):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)


def get_button(driver):
    try:
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        print('len of button tag', len(buttons))
        visible_buttons = [button for button in buttons if button.is_displayed()]
        print('len of visible button', len(visible_buttons))
        return visible_buttons

    except Exception as e:
        print('get button function exception:',e)

def selected_button(load_from_list, visible_buttons):
    global selected_button_index

    if load_from_list and selected_button_index:
        selected_buttons = [visible_buttons[btn] for btn in selected_button_index]
    else:
        selected_buttons = random.sample(range(len(visible_buttons)), 1)
        selected_button_index = selected_buttons
        selected_buttons = [visible_buttons[btn] for btn in selected_button_index]
    return selected_buttons

def check_redirect(driver, wait, current_url, new_url):
    if current_url != new_url:
        print(f'Redirected to the new URL {new_url}')
        driver.back()
        wait.until(EC.url_to_be(current_url))
        time.sleep(2)
        return True
    else:
        print('Same page')

def button_click(driver, folder_name, button_list=False):
    wait = WebDriverWait(driver, 10)

    try:

        visible_buttons = get_button(driver)


        selected_buttons = selected_button(button_list, visible_buttons)


        for index, button in enumerate(selected_buttons):
            try:
                step = 'btn'
                current_url = driver.current_url
                wait.until(EC.visibility_of(button))
                wait.until(EC.element_to_be_clickable(button))
                scroll_to_button(driver, button)
                button.click()
                time.sleep(2)
                print(f'{button.text} has been clicked')
                take_screenshot(driver, folder_name, f'btn{index+1}',step)

                new_url = driver.current_url

                check_redirect(driver, wait, current_url, new_url)

                check_popup(driver)
                time.sleep(2)
            except Exception as e:
                print(f"Failed to interact with button {index + 1}/{len(selected_buttons)}: {e}")
    except Exception as e:
        print(e)

def check_popup(driver):
    popups = driver.find_elements(By.CSS_SELECTOR, '.model, .popup,  .dialog, [role="dialog"], [role="alertdialog"], [aria-modal="true"]')
    if popups:
        close_popup(driver)

def close_popup(driver):
    close_selectors = [
        'button.close',
        'button[aria-label="Close"]',
        '.modal .close',
        '.modal-footer button.btn-secondary'
        #added
        'button[aria-label="close"]'
    ]

    for selector in close_selectors:
        close_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
        for button in close_buttons:
            button.click()
            time.sleep(1)
            return

    actions = ActionChains(driver)
    actions.send_keys(Keys.ESCAPE).perform()
    time.sleep(1)




#NAVIGATE THE PAGES

def get_internal_links(driver, domain):
    links = driver.find_elements(By.TAG_NAME, 'a')
    internal_links = []
    for link in links:
        href = link.get_attribute('href')
        if href and (urlparse(href).netloc == domain or urlparse(href).netloc == ''):
            internal_links.append(href)
    print('len of internal link', len(internal_links))
    return internal_links

def save_visited_urls(visited_urls, file_path):
    """Save the visited URLs to a file."""
    with open(file_path, 'w') as f:
        for url in visited_urls:
            f.write(f"{url}\n")


def crawl_browser(driver, steps, folder,  previously_visited_urls=None):
    """Crawl through pages and capture screenshots."""
    visited_urls = []
    domain = urlparse(url).netloc
    driver.get(url)
    # file_path = '/visited_urls.txt'

    try:
        for step in range(1, steps + 1):
            if previously_visited_urls and step - 1 < len(previously_visited_urls):
                link = previously_visited_urls[step - 1]
            else:
                time.sleep(random.uniform(1, 3))
                internal_links = get_internal_links(driver, domain)
                if not internal_links:
                    logging.info("No internal links found, skipping this step.")
                    continue
                link = random.choice(internal_links)

            driver.get(link)
            visited_urls.append(link)
            print(f"Visiting: {link}")
            scroll_page(driver, folder, step)
            # save_visited_urls(visited_urls, file_path)
        return visited_urls

    except Exception as e:
        logging.error(f"An error occurred in crawl_browser: {e}")

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
def scroll_page(driver, folder, step):
    normalize_styles(driver)
    print(folder)
    scroll_intervals = [0, 10,  20, 30, 40, 50, 60, 70, 80, 90, 100]
    total_height = driver.execute_script("return document.body.scrollHeight")
    for scroll_percentage in scroll_intervals:
        scroll_position = (total_height * scroll_percentage) / 100
        driver.execute_script(f"window.scrollTo(0, {scroll_position});")
        time.sleep(2)
        file_name = (f'scroll_{scroll_percentage}')
        take_screenshot(driver, folder, file_name, step)


## to debug
def perform_action(driver, action_name):
    try:
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
        time.sleep(1)
        screenshot_path = f'{action_name}_screenshot'
        driver.save_screenshot(screenshot_path)

        print(f'Screenshot saved to {screenshot_path}')
    except Exception as e:
        print(f"An error occurred while performing the action: {str(e)}")



# to get the application name
def get_application_name(driver):
    app_url = driver.current_url
    parsed_url = urlparse(app_url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain.replace("www.", "", 1)
    app_name = domain.split('.')[0]
    return app_name

def theme_checker(extension_path = None):
    try:
        if USRPROFILE == '':
            raise Exception('Please fill Google Chrome\'s user profile location')
    except:
        raise Exception('Please fill Google Chrome\'s user profile location in USRPROFILE global variable')


    step = 1


    driver = setup_driver()
    start_web_application(driver)

    application_name = get_application_name(driver)
    main_folder = create_folder(application_name)
    light_mode_folder = create_folder(os.path.join(main_folder, 'light'))
    dark_mode_folder = create_folder(os.path.join(main_folder, 'dark'))

    # to ge the hover over and button click
    # hover_over_nav_elements(driver, light_mode_folder)
    # button_click(driver, light_mode_folder)

    # to visit the pages nad crawl the pages
    previously_visited_urls = crawl_browser(driver, folder=light_mode_folder, steps=step)

    # apply the extension
    print('applying the dark mode extension...')
    print('applying the dark mode extension...')
    print('applying the dark mode extension...')
    time.sleep(15)
    driver_ex = setup_driver(extension_path)
    start_web_application(driver_ex)

    # to hover and button click
    # hover_over_nav_elements(driver_ex, dark_mode_folder, load_from_list=True)
    # button_click(driver_ex, dark_mode_folder, button_list=True)

    # to crawl the browser
    crawl_browser(driver_ex, folder=dark_mode_folder, steps=step, previously_visited_urls=previously_visited_urls)


if __name__ == '__main__':
    theme_checker(extension_path)