import os
import sys
import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import config

os.environ['WDM_LOCAL'] = '1'
os.environ['WDM_SSL_VERIFY'] = '0'
# Ensure cache is stored next to this script, not in working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "workshop_cache.json")

def load_cache():
    """Load workshop items cache from JSON file."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    """Save workshop items cache to JSON file."""
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)

def choose_collection():
    print("Select which collection tag to update:")
    options = list(config.COLLECTION_IDS.keys())
    for idx, option in enumerate(options, start=1):
        print(f"{idx}. {option}")
    try:
        choice = int(input(f"Enter your choice (1-{len(options)}): ").strip())
        selected = options[choice - 1]
    except (ValueError, IndexError):
        selected = options[0]
        print("Invalid choice. Defaulting to the first option.")
    print(f"Updating collections for '{selected}'...")
    return selected

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

def get_workshop_items(driver, tag, existing_items=None):
    """Scrape workshop items sorted by most recent, stopping when encountering only cached items."""
    if existing_items is None:
        existing_items = set()
    workshop_ids = set()
    page = 1
    # sort by most recent
    base_url = f"{config.WORKSHOP_BASE_URL}{tag}&browsesort=mostrecent&p="
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
        page_ids = {e.get_attribute("href").split("id=")[1].split("&")[0] for e in elements if e.get_attribute("href")}
        # stop if no new items on this page
        new_ids = page_ids - existing_items
        if not new_ids:
            print(f"No new items on page {page}, stopping early.")
            break
        workshop_ids.update(new_ids)
        print(f"Scraped page {page} ({len(elements)} items)")
        page += 1
    print(f"Total new workshop items scraped: {len(workshop_ids)}")
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
        tag = choose_collection()
        cache = load_cache()
        prev_items = set(cache.get(tag, []))
        driver = config.configure_edge()
        try:
            # Gather current items for each collection of this tag
            collections = config.COLLECTION_IDS.get(tag, [])
            current_items_map = {}
            total_current = set()
            for col_id in collections:
                items = get_collection_items(driver, col_id)
                current_items_map[col_id] = items
                total_current.update(items)
            # Scrape new workshop items
            workshop_items = get_workshop_items(driver, tag, prev_items)
            # Determine missing items across all collections
            missing_items = [i for i in workshop_items if i not in total_current]
            print(f"Total missing {len(missing_items)} item(s) for '{tag}'. Distributing across {len(collections)} collections.")
        except Exception as e:
            print(f"Error during setup: {e}")
            missing_items = []
            collections = []
            current_items_map = {}
        # Add missing items, filling collections up to the max
        for item in missing_items:
            placed = False
            for col_id in collections:
                if len(current_items_map.get(col_id, [])) < config.MAX_COLLECTION_ITEMS:
                    add_to_collection(driver, item, col_id)
                    current_items_map[col_id].add(item)
                    placed = True
                    break
            if not placed:
                print(f"All collections for '{tag}' are full (limit {config.MAX_COLLECTION_ITEMS}). Stopping addition.")
                break
        # Update cache and quit
        cache[tag] = list(prev_items.union(workshop_items))
        save_cache(cache)
        driver.quit()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)