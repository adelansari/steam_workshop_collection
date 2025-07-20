import os
import sys
import time
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
        for tag, collection_id in config.COLLECTION_IDS.items():
            print(f"\nProcessing collection '{tag}' (ID: {collection_id})...")
            prev_items = set(cache.get(tag, []))
            try:
                current_items = get_collection_items(driver, collection_id)
                workshop_items = get_workshop_items(driver, tag, prev_items)
                missing_items = list(workshop_items - current_items)
                print(f"Missing {len(missing_items)} item(s) to add for '{tag}'.")
                for item in missing_items:
                    add_to_collection(driver, item, collection_id)
                # Update cache after processing this collection
                cache[tag] = list(prev_items.union(workshop_items))
                save_cache(cache)
            except Exception as e:
                print(f"Error processing collection '{tag}': {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting early.")
        sys.exit(1)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
