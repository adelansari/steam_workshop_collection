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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
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

def get_collection_items(page, col_id):
    """
    Scrape all item IDs from a Steam collection.
    Returns a set of item IDs (strings), or None on failure.
    """
    try:
        page.goto(f"{config.SHARED_FILE_DETAILS_URL}{col_id}", timeout=60000, wait_until="domcontentloaded")
    except PlaywrightTimeoutError:
        print(f"  Timeout loading collection {col_id}")
        return None
    
    try:
        page.wait_for_selector(".collectionChildren", timeout=20000)
    except PlaywrightTimeoutError:
        print(f"  Failed to load collection {col_id}")
        return None  # Return None to indicate failure, not empty set

    # Scroll to load all items (Steam lazy-loads)
    last_count = -1
    stable = 0
    start = time.time()
    while time.time() - start < 60 and stable < 3:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        elements = page.query_selector_all(".collectionItem a[href*='filedetails/?id=']")
        count = len(elements)
        if count == last_count:
            stable += 1
        else:
            stable = 0
        last_count = count

    elements = page.query_selector_all(".collectionItem a[href*='filedetails/?id=']")
    items = set()
    for e in elements:
        href = e.get_attribute("href")
        if href and "id=" in href:
            item_id = href.split("id=")[1].split("&")[0]
            items.add(item_id)

    return items


def get_workshop_items(page, tag, known_items):
    """
    Scrape workshop for new items (sorted by most recent).
    Continues through ALL pages until hitting empty page or max pages.
    Returns list of new item IDs in order (most recent first).
    """
    new_items = []
    page_num = 1
    consecutive_empty = 0  # Track consecutive pages with no new items
    max_consecutive_empty = 3  # Stop after this many consecutive pages with no new items
    max_pages = 100  # Safety limit
    base_url = f"{config.WORKSHOP_BASE_URL}{tag}&browsesort=mostrecent&p="

    while page_num <= max_pages:
        try:
            page.goto(f"{base_url}{page_num}", timeout=60000, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            print(f"  Page {page_num}: timeout loading, stopping")
            break
        
        # Check for empty page (no items at all on Steam)
        if page.query_selector("#no_items"):
            print(f"  Page {page_num}: empty page (end of workshop)")
            break

        try:
            page.wait_for_selector("a.item_link", timeout=10000)
        except PlaywrightTimeoutError:
            print(f"  Page {page_num}: timeout loading, stopping")
            break

        elements = page.query_selector_all("a.item_link")
        page_ids = []
        for e in elements:
            href = e.get_attribute("href")
            if href and "id=" in href:
                page_ids.append(href.split("id=")[1].split("&")[0])

        # Find new items on this page
        new_on_page = [i for i in page_ids if i not in known_items]
        
        if not new_on_page:
            consecutive_empty += 1
            print(f"  Page {page_num}: no new items ({consecutive_empty}/{max_consecutive_empty} consecutive)")
            if consecutive_empty >= max_consecutive_empty:
                print(f"  Stopping after {max_consecutive_empty} consecutive pages with no new items")
                break
        else:
            consecutive_empty = 0  # Reset counter when we find new items
            new_items.extend(new_on_page)
            print(f"  Page {page_num}: {len(new_on_page)} new items")
        
        page_num += 1

    print(f"  Total new items found: {len(new_items)}")
    return new_items


def add_to_collection(page, item_id, col_id, retries=3, debug=False):
    """
    Add an item to a collection.
    Returns True if successful, False otherwise.
    """
    wait_timeout = 12000  # milliseconds
    
    for attempt in range(1, retries + 1):
        try:
            try:
                page.goto(f"{config.SHARED_FILE_DETAILS_URL}{item_id}", timeout=60000, wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                print(f"    Timeout loading item {item_id}")
                if attempt < retries:
                    time.sleep(2)
                    continue
                else:
                    return False
            time.sleep(1)
            
            # Debug: Check if add button exists
            add_btn = page.query_selector(".general_btn[onclick*='AddToCollection']")
            if not add_btn:
                if debug:
                    print(f"    DEBUG: Add button not found")
                # Check if already in collection
                remove_btn = page.query_selector(".general_btn[onclick*='RemoveFromCollection']")
                if remove_btn:
                    print(f"    Already in a collection")
                    return False
                raise Exception("Add to Collection button not found")
            
            # Click "Add to Collection" button
            add_btn.click()
            
            # Wait for dialog
            dialog = page.wait_for_selector("#AddToCollectionDialog", timeout=wait_timeout, state="visible")
            if not dialog:
                raise Exception("AddToCollectionDialog not found")
            
            # Find the collection checkbox (use attribute selector since IDs may start with digit)
            checkbox = page.wait_for_selector(f'[id="{col_id}"]', timeout=wait_timeout)
            if not checkbox:
                raise Exception(f"Checkbox for collection {col_id} not found")
            
            is_checked = checkbox.is_checked()
            if not is_checked:
                checkbox.click()
            else:
                if debug:
                    print(f"    Already checked")
            
            # Click OK/Save button - try different selectors
            ok_btn = page.query_selector(".btn_green_steamui.btn_medium")
            if not ok_btn:
                ok_btn = page.query_selector("#AddToCollectionDialog .btn_green_steamui")
            if not ok_btn:
                ok_btn = page.query_selector("button:has-text('OK')")
            
            if ok_btn:
                ok_btn.click()
            else:
                raise Exception("OK button not found")
            
            # Wait for dialog to close
            try:
                page.wait_for_selector("#AddToCollectionDialog", timeout=5000, state="hidden")
            except:
                pass  # Dialog might close differently
            
            time.sleep(0.5)
            return True
            
        except Exception as e:
            error_msg = str(e)
            if attempt < retries:
                if debug:
                    print(f"    Attempt {attempt} failed: {error_msg}, retrying...")
                time.sleep(2)
            else:
                # Truncate long error messages
                if len(error_msg) > 60:
                    error_msg = error_msg[:57] + "..."
                print(f"    Failed: {error_msg}")
                return False
    
    return False
