"""
Steam Collection Bot - Simplified and Robust

Key principles:
1. Once a collection is marked FULL, never add to it again (persisted in locked_collections.json)
2. Cache only grows - never overwrite with smaller data
3. add_to_collection returns True/False so we know if it actually worked
4. Fill collections in order: first one until full, then next, etc.
"""

import os
import sys
import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import config

CACHE_DIR = config.CACHE_DIR
LOCKED_FILE = os.path.join(config.BASE_DIR, "locked_collections.json")


# ---------------------- Locked Collections ---------------------- #

def load_locked_collections():
    """Load set of collection IDs that are permanently full."""
    if os.path.exists(LOCKED_FILE):
        try:
            with open(LOCKED_FILE, 'r') as f:
                data = json.load(f)
                return set(str(i) for i in data) if isinstance(data, list) else set()
        except Exception:
            pass
    return set()


def save_locked_collections(locked):
    """Persist locked collection IDs."""
    with open(LOCKED_FILE, 'w') as f:
        json.dump(sorted(locked), f, indent=2)


def lock_collection(col_id):
    """Mark a collection as permanently full."""
    locked = load_locked_collections()
    if str(col_id) not in locked:
        locked.add(str(col_id))
        save_locked_collections(locked)
        print(f"  🔒 LOCKED collection {col_id} - will never add to it again")


def is_collection_locked(col_id):
    """Check if a collection is locked."""
    return str(col_id) in load_locked_collections()


# ---------------------- Cache Handling ---------------------- #

def load_cache():
    """Load cache: { tag: { collection_id: set(item_ids) } }"""
    cache = {}
    try:
        for tag in os.listdir(CACHE_DIR):
            tag_dir = os.path.join(CACHE_DIR, tag)
            if not os.path.isdir(tag_dir):
                continue
            for fname in os.listdir(tag_dir):
                if not fname.endswith('.json'):
                    continue
                cid = fname[:-5]
                fpath = os.path.join(tag_dir, fname)
                try:
                    with open(fpath, 'r') as f:
                        items = json.load(f)
                    if isinstance(items, list):
                        cache.setdefault(tag, {})[cid] = set(str(i) for i in items)
                except Exception:
                    pass
    except Exception:
        pass
    return cache


def save_cache(cache):
    """Save cache to disk."""
    for tag, collections in cache.items():
        tag_dir = os.path.join(CACHE_DIR, tag)
        os.makedirs(tag_dir, exist_ok=True)
        for cid, items in collections.items():
            fpath = os.path.join(tag_dir, f"{cid}.json")
            with open(fpath, 'w') as f:
                json.dump(sorted(items), f, indent=2)


def get_all_cached_items_for_tag(cache, tag):
    """Get union of all cached items across all collections for a tag."""
    if tag not in cache:
        return set()
    result = set()
    for items in cache[tag].values():
        result.update(items)
    return result


# ---------------------- Steam Scraping ---------------------- #

def get_collection_items(driver, col_id):
    """
    Scrape all item IDs from a Steam collection.
    Returns a set of item IDs (strings), or None on failure.
    """
    driver.get(f"{config.SHARED_FILE_DETAILS_URL}{col_id}")
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collectionChildren"))
        )
    except TimeoutException:
        print(f"  Failed to load collection {col_id}")
        return None  # Return None to indicate failure, not empty set

    # Scroll to load all items (Steam lazy-loads)
    last_count = -1
    stable = 0
    start = time.time()
    while time.time() - start < 60 and stable < 3:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
        count = len(elements)
        if count == last_count:
            stable += 1
        else:
            stable = 0
        last_count = count

    elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
    items = set()
    for e in elements:
        href = e.get_attribute("href")
        if href and "id=" in href:
            item_id = href.split("id=")[1].split("&")[0]
            items.add(item_id)

    return items


def get_workshop_items(driver, tag, known_items):
    """
    Scrape workshop for new items (sorted by most recent).
    Continues through ALL pages until hitting empty page or max pages.
    Returns list of new item IDs in order (most recent first).
    """
    new_items = []
    page = 1
    consecutive_empty = 0  # Track consecutive pages with no new items
    max_consecutive_empty = 3  # Stop after this many consecutive pages with no new items
    max_pages = 100  # Safety limit
    base_url = f"{config.WORKSHOP_BASE_URL}{tag}&browsesort=mostrecent&p="

    while page <= max_pages:
        driver.get(f"{base_url}{page}")
        
        # Check for empty page (no items at all on Steam)
        if driver.find_elements(By.CSS_SELECTOR, "#no_items"):
            print(f"  Page {page}: empty page (end of workshop)")
            break

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.item_link"))
            )
        except TimeoutException:
            print(f"  Page {page}: timeout loading, stopping")
            break

        elements = driver.find_elements(By.CSS_SELECTOR, "a.item_link")
        page_ids = []
        for e in elements:
            href = e.get_attribute("href")
            if href and "id=" in href:
                page_ids.append(href.split("id=")[1].split("&")[0])

        # Find new items on this page
        new_on_page = [i for i in page_ids if i not in known_items]
        
        if not new_on_page:
            consecutive_empty += 1
            print(f"  Page {page}: no new items ({consecutive_empty}/{max_consecutive_empty} consecutive)")
            if consecutive_empty >= max_consecutive_empty:
                print(f"  Stopping after {max_consecutive_empty} consecutive pages with no new items")
                break
        else:
            consecutive_empty = 0  # Reset counter when we find new items
            new_items.extend(new_on_page)
            print(f"  Page {page}: {len(new_on_page)} new items")
        
        page += 1

    print(f"  Total new items found: {len(new_items)}")
    return new_items


def add_to_collection(driver, item_id, col_id, retries=3):
    """
    Add an item to a collection.
    Returns True if successful, False otherwise.
    """
    wait_timeout = 12
    
    for attempt in range(1, retries + 1):
        try:
            driver.get(f"{config.SHARED_FILE_DETAILS_URL}{item_id}")
            time.sleep(1)
            
            wait = WebDriverWait(driver, wait_timeout)
            
            # Click "Add to Collection" button
            wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".general_btn[onclick*='AddToCollection']"))
            ).click()
            
            # Wait for dialog
            wait.until(
                EC.visibility_of_element_located((By.ID, "AddToCollectionDialog"))
            )
            
            # Find and click the collection checkbox
            checkbox = wait.until(
                EC.presence_of_element_located((By.ID, col_id))
            )
            
            if not checkbox.is_selected():
                checkbox.click()
            
            # Click OK/Save button
            wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_green_steamui.btn_medium span"))
            ).click()
            
            time.sleep(0.5)  # Brief pause for Steam to process
            return True
            
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"    Failed to add {item_id}: {type(e).__name__}")
                return False
    
    return False
