from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.common.exceptions import TimeoutException
import time
import os
import concurrent.futures
import sys

COLLECTION_ID = "3445105194"  # default for Characters
EDGE_PROFILE_PATH = r"C:\Users\adela\AppData\Local\Microsoft\Edge\User Data\Default"
EDGE_DRIVER_PATH = r"C:\EdgeDriver\msedgedriver.exe"

os.environ['WDM_LOCAL'] = '1'
os.environ['WDM_SSL_VERIFY'] = '0'

def choose_collection():
    print("Select which collection to update:")
    print("1. Characters")
    print("2. Vehicles")
    choice = input("Enter your choice (1 or 2): ").strip()
    if choice == "1":
        col_id, tag = "3445105194", "Characters"
    else:
        if choice != "2":
            print("Invalid choice. Defaulting to Vehicles.")
        col_id, tag = "3444831495", "Vehicles"
    print(f"Updating {tag} collection (ID: {col_id})...")
    return col_id, tag

def configure_edge():
    options = Options()
    options.add_argument(f"user-data-dir={EDGE_PROFILE_PATH}")
    options.add_argument("profile-directory=Default")
    options.add_argument("--disable-infobars")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-restore-session-state")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument("--headless=new")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    # Security bypass (temporary)
    options.set_capability('acceptInsecureCerts', True)
    
    service = Service(EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver

def get_collection_items(driver):
    collection_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={COLLECTION_ID}"
    driver.get(collection_url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collectionChildren"))
        )
    except TimeoutException:
        print("Failed to load collection items")
        return set()
    
    elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
    collection_ids = { elem.get_attribute("href").split("id=")[1].split("&")[0]
                       for elem in elements if elem.get_attribute("href") and "id=" in elem.get_attribute("href") }
    print(f"Found {len(collection_ids)} items in the collection")
    return collection_ids

def get_workshop_items(driver, tag):
    base_url = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]=" + tag + "&p="
    workshop_ids = set()
    page = 1
    while True:
        print(f"Scraping workshop page {page} for {tag}...")
        driver.get(f"{base_url}{page}")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a.item_link'))
            )
        except TimeoutException:
            if "No items matching your search criteria were found." in driver.page_source:
                print("No more items found.")
            else:
                print(f"Timeout waiting on page {page}")
            break
        
        items = driver.find_elements(By.CSS_SELECTOR, 'a.item_link')
        if not items:
            print("No items returned; breaking loop")
            break
        
        for item in items:
            href = item.get_attribute("href")
            if href and "id=" in href:
                item_id = href.split("id=")[1].split("&")[0]
                workshop_ids.add(item_id)
        print(f"Found {len(items)} items on page {page}")
        page += 1
    print(f"Total workshop items scraped: {len(workshop_ids)}")
    return workshop_ids

def process_item(item_id):
    driver = configure_edge()
    try:
        print(f"Adding item {item_id}...")
        driver.get(f"https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}")
        add_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".general_btn[onclick*='AddToCollection']"))
        )
        add_button.click()
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.ID, "AddToCollectionDialog"))
        )
        collection_checkbox = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, COLLECTION_ID))
        )
        if not collection_checkbox.is_selected():
            collection_checkbox.click()
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_green_steamui.btn_medium span"))
        ).click()
        print(f"Successfully added item {item_id}")
    except Exception as e:
        print(f"Failed to add {item_id}: {str(e)}")
    finally:
        driver.quit()

def add_to_collection_concurrent(missing_ids, max_workers=3):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_item, item_id) for item_id in missing_ids]
        concurrent.futures.wait(futures)

if __name__ == "__main__":
    try:
        COLLECTION_ID, tag = choose_collection()
        main_driver = configure_edge()
        try:
            collection_ids = get_collection_items(main_driver)
            workshop_ids = get_workshop_items(main_driver, tag)
            missing_ids = list(workshop_ids - collection_ids)
            print(f"Missing {len(missing_ids)} items to add")
        finally:
            main_driver.quit()
        
        if missing_ids:
            add_to_collection_concurrent(missing_ids, max_workers=8)
        else:
            print("No missing items to add. Collection is up-to-date.")
    except KeyboardInterrupt:
        print("\nProcess terminated by user. Exiting safely.")
        sys.exit(0)