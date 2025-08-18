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
    added_summary = {}  # tag -> count added this run
    try:
        processed_tags = set()
        all_tags = list(config.COLLECTION_IDS.items())
        total_tags = len(all_tags)
        for idx, (tag, collections) in enumerate(all_tags, start=1):
            if tag in processed_tags:
                print(f"[SKIP] Tag '{tag}' already processed this run.")
                continue
            processed_tags.add(tag)
            print(f"\n[{idx}/{total_tags}] Processing tag '{tag}' (collections: {collections})")
            prev_items = get_existing_items_for_tag(cache, tag)
            try:
                # Gather current items for each collection and total
                current_items_map = {}
                total_current = set()
                for col_id in collections:
                    items = get_collection_items(driver, col_id)
                    current_items_map[col_id] = set(items)
                    total_current.update(items)
                    print(f"  Collection {col_id}: {len(items)} items (remaining {config.MAX_COLLECTION_ITEMS - len(items)})")
                # Scrape new workshop items based on cache
                workshop_items = get_workshop_items(driver, tag, prev_items)
                # Determine items missing across all collections
                missing_items = [i for i in workshop_items if i not in total_current]
                print(f"  Missing {len(missing_items)} new item(s) for '{tag}' across {len(collections)} collection(s)")
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
                added_counter = 0
                for item in missing_items:
                    # Defensive: skip if somehow already added earlier in loop
                    if any(item in s for s in current_items_map.values()):
                        continue
                    target_col = select_best_collection(current_items_map, config.MAX_COLLECTION_ITEMS)
                    if not target_col:
                        print(f"  All collections for '{tag}' are at/over limit ({config.MAX_COLLECTION_ITEMS}). Stopping additions.")
                        break
                    before = len(current_items_map[target_col])
                    add_to_collection(driver, item, target_col)
                    current_items_map[target_col].add(item)
                    after = len(current_items_map[target_col])
                    added_counter += 1 if after > before else 0
                    print(f"    Added {item} -> {target_col} ({after}/{config.MAX_COLLECTION_ITEMS})")
                    if len(current_items_map[target_col]) >= config.MAX_COLLECTION_ITEMS:
                        print(f"    Collection {target_col} reached capacity {config.MAX_COLLECTION_ITEMS}.")
                    else:
                        remaining = config.MAX_COLLECTION_ITEMS - len(current_items_map[target_col])
                        if remaining <= 25:  # Near limit: re-fetch to correct any lazy-load drift
                            refreshed = get_collection_items(driver, target_col)
                            current_items_map[target_col] = set(refreshed)
                            if len(refreshed) >= config.MAX_COLLECTION_ITEMS:
                                print(f"    Collection {target_col} reached/exceeded max after refresh ({len(refreshed)}). Further adds blocked.")
                # Persist per-collection cache if additions occurred
                any_added = False
                for col_id, items_set in current_items_map.items():
                    cache.setdefault(tag, {})
                    prev_cached = cache[tag].get(col_id, set())
                    before = len(prev_cached) if isinstance(prev_cached, set) else 0
                    # Safeguard: avoid overwriting with empty scrape if we previously had data (likely transient failure)
                    if len(items_set) == 0 and before > 0:
                        print(f"  WARN: Skipping cache overwrite for {col_id}; scraped 0 but cache has {before} (transient load?)")
                        items_set = prev_cached
                    cache[tag][col_id] = items_set
                    if len(items_set) > before:
                        any_added = True
                if any_added:
                    cache_changed = True
                summary_states = " | ".join(f"{cid}:{len(current_items_map[cid])}" for cid in collections)
                print(f"  Tag '{tag}' summary: added {added_counter} item(s). Collection states: {summary_states}")
                added_summary[tag] = added_counter
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
                # Build dynamic commit message summarizing additions
                non_zero = {t: c for t, c in added_summary.items() if c > 0}
                if non_zero:
                    # Header line
                    header_parts = []
                    for tag, count in non_zero.items():
                        header_parts.append(f"{tag}+{count}")
                    header = "update: added " + ", ".join(header_parts)
                else:
                    header = "chore: update cache (no net new items)"
                # Only header commit (no per-collection size details)
                commit_cmd = ["git", "commit", "-m", header]
                subprocess.run(commit_cmd, check=True)
                subprocess.run(["git", "push"], check=True)
                print("Git: Changes committed and pushed to GitHub.")
            except subprocess.CalledProcessError as e:
                print(f"Git operation failed: {e}")
        else:
            print("No new items added; skipping cache save and git commit.")

if __name__ == "__main__":
    main()
