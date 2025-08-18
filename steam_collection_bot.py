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
# Cache directory for per-tag JSON files
CACHE_DIR = config.CACHE_DIR

def load_cache():
    """Load workshop items cache from per-tag JSON files in cache directory."""
    cache = {}
    try:
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith('.json'):
                tag = fname[:-5]
                path = os.path.join(CACHE_DIR, fname)
                try:
                    with open(path, 'r') as f:
                        cache[tag] = json.load(f)
                except Exception:
                    pass
    except Exception:
        pass
    return cache


def save_cache(cache):
    """Save workshop items cache to per-tag JSON files in cache directory."""
    for tag, items in cache.items():
        path = os.path.join(CACHE_DIR, f"{tag}.json")
        try:
            # Preserve list order; newly added items remain at the end
            with open(path, 'w') as f:
                json.dump(items, f, indent=2)
        except Exception:
            pass

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
    """Return full set of item IDs in a collection, attempting to lazy-load all items.

    Steam collection pages often lazy load items when scrolling. The previous implementation
    only counted the initially loaded DOM nodes which could significantly under-report the
    true count. That under-count let the script believe there was remaining capacity and
    push the collection beyond the intended MAX_COLLECTION_ITEMS.
    """
    driver.get(f"{config.SHARED_FILE_DETAILS_URL}{col_id}")
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collectionChildren"))
        )
    except TimeoutException:
        print("Failed to load collection items container for collection", col_id)
        return set()

    last_count = -1
    stable_iterations = 0
    max_stable_needed = 2
    start_time = time.time()
    timeout = 45
    while time.time() - start_time < timeout and stable_iterations < max_stable_needed:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.4)
        elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
        current_count = len(elements)
        if current_count == last_count:
            stable_iterations += 1
        else:
            stable_iterations = 0
        last_count = current_count
        if current_count >= config.MAX_COLLECTION_ITEMS + 5:
            break
    elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
    items = {e.get_attribute("href").split("id=")[1].split("&")[0] for e in elements if e.get_attribute("href")}
    print(f"Collection {col_id} reported {len(items)} fully-loaded item(s)")
    if len(items) > config.MAX_COLLECTION_ITEMS:
        print(f"WARNING: Collection {col_id} currently exceeds MAX_COLLECTION_ITEMS ({config.MAX_COLLECTION_ITEMS}). No further additions will be made to this collection.")
    return items

def select_best_collection(current_items_map, max_limit):
    """Return collection id with most remaining capacity (or None if all full)."""
    best_id = None
    best_remaining = -1
    for cid, items in current_items_map.items():
        remaining = max_limit - len(items)
        if remaining > best_remaining and remaining > 0:
            best_remaining = remaining
            best_id = cid
    return best_id

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
            # Quick defensive re-check: if target collection already at/over limit, abort early
            # (A parallel process or manual action might have filled it meanwhile)
            # We fetch a minimal indicator by opening the collection dialog later and counting selected entries is heavy;
            # instead rely on caller's map. This is just a placeholder for future enhancement.
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
            target_col = select_best_collection(current_items_map, config.MAX_COLLECTION_ITEMS)
            if not target_col:
                print(f"All collections for '{tag}' are at or over limit ({config.MAX_COLLECTION_ITEMS}). Stopping addition.")
                break
            if len(current_items_map[target_col]) >= config.MAX_COLLECTION_ITEMS:
                print(f"Target collection {target_col} unexpectedly full. Re-evaluating...")
                continue
            add_to_collection(driver, item, target_col)
            current_items_map[target_col].add(item)
            if len(current_items_map[target_col]) >= config.MAX_COLLECTION_ITEMS:
                print(f"Collection {target_col} reached max capacity ({config.MAX_COLLECTION_ITEMS}).")
            else:
                remaining = config.MAX_COLLECTION_ITEMS - len(current_items_map[target_col])
                if remaining <= 25:  # Near limit: refresh true count to avoid drift
                    refreshed = get_collection_items(driver, target_col)
                    current_items_map[target_col] = refreshed
                    if len(refreshed) >= config.MAX_COLLECTION_ITEMS:
                        print(f"Collection {target_col} reached/ exceeded max after refresh ({len(refreshed)}) - stopping additions to it.")
        # Update cache and quit
        cache[tag] = list(prev_items.union(workshop_items))
        save_cache(cache)
        driver.quit()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)