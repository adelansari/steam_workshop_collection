import os
import sys
import time
import subprocess
from selenium.common.exceptions import TimeoutException
# Change working directory to script folder so cache file path is consistent
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
import config
from steam_collection_bot import (
    load_cache,
    save_cache,
    get_collection_items,
    get_workshop_items,
    add_to_collection,
    get_existing_items_for_tag
)

def main():
    """
    Automatically iterate through all collections defined in config.COLLECTION_IDS,
    add any missing workshop items, and update the cache.
    """
    cache = load_cache()
    cache_changed = False
    driver = config.configure_edge()
    try:
        for tag, collections in config.COLLECTION_IDS.items():
            print(f"\nProcessing tag '{tag}' (collections: {collections})...")
            prev_items = get_existing_items_for_tag(cache, tag)
            try:
                # Gather current items for each collection and total
                current_items_map = {}
                total_current = set()
                for col_id in collections:
                    items = get_collection_items(driver, col_id)
                    current_items_map[col_id] = set(items)
                    total_current.update(items)
                # Scrape new workshop items based on cache
                workshop_items = get_workshop_items(driver, tag, prev_items)
                # Determine items missing across all collections
                missing_items = [i for i in workshop_items if i not in total_current]
                print(f"Total missing {len(missing_items)} item(s) for '{tag}'. Distributing across {len(collections)} collections.")
                # Helper: select collection with most remaining capacity
                def select_best_collection(cmap, limit):
                    best_id = None
                    best_remaining = -1
                    for cid, items in cmap.items():
                        remaining = limit - len(items)
                        if remaining > best_remaining and remaining > 0:
                            best_remaining = remaining
                            best_id = cid
                    return best_id
                for item in missing_items:
                    target_col = select_best_collection(current_items_map, config.MAX_COLLECTION_ITEMS)
                    if not target_col:
                        print(f"All collections for '{tag}' are at or over limit ({config.MAX_COLLECTION_ITEMS}). Stopping addition.")
                        break
                    add_to_collection(driver, item, target_col)
                    current_items_map[target_col].add(item)
                    if len(current_items_map[target_col]) >= config.MAX_COLLECTION_ITEMS:
                        print(f"Collection {target_col} reached max capacity ({config.MAX_COLLECTION_ITEMS}).")
                    else:
                        remaining = config.MAX_COLLECTION_ITEMS - len(current_items_map[target_col])
                        if remaining <= 25:  # Near limit: re-fetch to correct any lazy-load drift
                            refreshed = get_collection_items(driver, target_col)
                            current_items_map[target_col] = set(refreshed)
                            if len(refreshed) >= config.MAX_COLLECTION_ITEMS:
                                print(f"Collection {target_col} reached/ exceeded max after refresh ({len(refreshed)}). Will not add more to this collection.")
                # Persist per-collection cache if additions occurred
                any_added = False
                for col_id, items_set in current_items_map.items():
                    cache.setdefault(tag, {})
                    before = len(cache[tag].get(col_id, set())) if isinstance(cache[tag].get(col_id), set) else 0
                    cache[tag][col_id] = items_set
                    if len(items_set) > before:
                        any_added = True
                if any_added:
                    cache_changed = True
            except Exception as e:
                print(f"Error processing tag '{tag}': {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting early.")
        sys.exit(1)
    finally:
        driver.quit()
        # Only save and commit if cache was updated
        if cache_changed:
            save_cache(cache)
            # Commit and push any changes to GitHub
            try:
                subprocess.run(["git", "add", "-A"], check=True)
                subprocess.run(["git", "commit", "-m", "updated collection with new items"], check=True)
                subprocess.run(["git", "push"], check=True)
                print("Git: Changes committed and pushed to GitHub.")
            except subprocess.CalledProcessError as e:
                print(f"Git operation failed: {e}")
        else:
            print("No new items added; skipping cache save and git commit.")

if __name__ == "__main__":
    main()
