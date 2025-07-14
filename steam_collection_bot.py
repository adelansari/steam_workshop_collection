import os
import sys
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import config

os.environ['WDM_LOCAL'] = '1'
os.environ['WDM_SSL_VERIFY'] = '0'

def choose_collection():
    print("Select which collection to update:")
    options = list(config.COLLECTION_IDS.keys())
    for idx, option in enumerate(options, start=1):
        print(f"{idx}. {option}")
    try:
        choice = int(input(f"Enter your choice (1-{len(options)}): ").strip())
        selected = options[choice - 1]
    except (ValueError, IndexError):
        selected = options[0]
        print("Invalid choice. Defaulting to the first option.")
    col_id = config.COLLECTION_IDS[selected]
    print(f"Updating {selected} collection (ID: {col_id})...")
    return col_id, selected

def get_collection_items(driver, col_id):
    driver.get(f"{config.SHARED_FILE_DETAILS_URL}{col_id}")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collectionChildren"))
        )
    except TimeoutException:
        print("Failed to load collection items")
        return set()
    elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
    items = {e.get_attribute("href").split("id=")[1].split("&")[0] for e in elements if e.get_attribute("href")}
    print(f"Found {len(items)} items in the collection")
    return items

def get_workshop_items(driver, tag):
    workshop_ids = set()
    page = 1
    base_url = f"{config.WORKSHOP_BASE_URL}{tag}&p="
    while True:
        driver.get(f"{base_url}{page}")
        if driver.find_elements(By.CSS_SELECTOR, "#no_items"):
            print(f"No more items found on page {page}.")
            break
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.item_link"))
            )
        except TimeoutException:
            print(f"Timeout waiting on page {page}")
            break
        elements = driver.find_elements(By.CSS_SELECTOR, "a.item_link")
        if not elements:
            break
        for e in elements:
            href = e.get_attribute("href")
            if href and "id=" in href:
                workshop_ids.add(href.split("id=")[1].split("&")[0])
        print(f"Scraped page {page} ({len(elements)} items)")
        page += 1
    print(f"Total workshop items scraped: {len(workshop_ids)}")
    return workshop_ids

def add_to_collection(driver, item_id, col_id, retries=3):
    for attempt in range(1, retries + 1):
        try:
            print(f"Adding item {item_id} (attempt {attempt})...")
            driver.get(f"{config.SHARED_FILE_DETAILS_URL}{item_id}")
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".general_btn[onclick*='AddToCollection']"))
            ).click()
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.ID, "AddToCollectionDialog"))
            )
            checkbox = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, col_id))
            )
            if not checkbox.is_selected():
                checkbox.click()
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_green_steamui.btn_medium span"))
            ).click()
            print(f"Successfully added item {item_id}")
            return
        except Exception as e:
            print(f"Error processing item {item_id} attempt {attempt}: {e}")
            time.sleep(2)
    print(f"Failed to process item {item_id} after {retries} attempts.")

if __name__ == "__main__":
    try:
        collection_id, tag = choose_collection()
        driver = config.configure_edge()
        try:
            current_items = get_collection_items(driver, collection_id)
            workshop_items = get_workshop_items(driver, tag)
            missing_items = list(workshop_items - current_items)
            print(f"Missing {len(missing_items)} items to add.")
        except Exception as e:
            print(f"Error during setup: {e}")
        for item in missing_items:
            add_to_collection(driver, item, collection_id)
        driver.quit()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)