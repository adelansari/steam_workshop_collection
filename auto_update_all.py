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
    add_to_collection
)

def main():
    """
    Automatically iterate through all collections defined in config.COLLECTION_IDS,
    add any missing workshop items, and update the cache.
    """
    cache = load_cache()
    driver = config.configure_edge()
    try:
        for tag, collections in config.COLLECTION_IDS.items():
            print(f"\nProcessing tag '{tag}' (collections: {collections})...")
            prev_items = set(cache.get(tag, []))
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
                # Add items to collections up to max limit
                for item in missing_items:
                    placed = False
                    for col_id in collections:
                        if len(current_items_map[col_id]) < config.MAX_COLLECTION_ITEMS:
                            add_to_collection(driver, item, col_id)
                            current_items_map[col_id].add(item)
                            placed = True
                            break
                    if not placed:
                        print(f"All collections for '{tag}' are full (limit {config.MAX_COLLECTION_ITEMS}). Stopping addition.")
                        break
                # Update cache after processing this tag
                cache[tag] = list(prev_items.union(workshop_items))
                save_cache(cache)
            except Exception as e:
                print(f"Error processing tag '{tag}': {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting early.")
        sys.exit(1)
    finally:
        driver.quit()
        # Commit and push any changes to GitHub
        try:
            subprocess.run(["git", "add", "-A"], check=True)
            subprocess.run(["git", "commit", "-m", "updated collection with new items"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Git: Changes committed and pushed to GitHub.")
        except subprocess.CalledProcessError as e:
            print(f"Git operation failed: {e}")

if __name__ == "__main__":
    main()
