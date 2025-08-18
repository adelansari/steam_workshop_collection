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
    added_summary = {}   # tag -> items actually added (sum over its collections)
    added_by_collection = {}  # tag -> {collection_id: added_count}
    verbose = os.getenv("BOT_VERBOSE", "0") not in ("0", "false", "False")
    try:
        all_tags = list(config.COLLECTION_IDS.items())
        total_tags = len(all_tags)
        for idx, (tag, collections) in enumerate(all_tags, start=1):
            print(f"\n[{idx}/{total_tags}] {tag} -> {len(collections)} collection(s)")
            prev_items = get_existing_items_for_tag(cache, tag)
            try:
                # Gather current items for each collection and total
                current_items_map = {}
                total_current = set()
                for col_id in collections:
                    items = get_collection_items(driver, col_id)
                    current_items_map[col_id] = set(items)
                    total_current.update(items)
                    if verbose:
                        print(f"  {col_id}: {len(items)} items (remain {config.MAX_COLLECTION_ITEMS - len(items)})")
                # Scrape new workshop items based on cache
                workshop_items = get_workshop_items(driver, tag, prev_items)
                # Determine items missing across all collections
                missing_items = [i for i in workshop_items if i not in total_current]
                if verbose:
                    print(f"  Missing (not yet in any collection): {len(missing_items)}")
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
                        if verbose:
                            print(f"  All collections full (limit {config.MAX_COLLECTION_ITEMS})")
                        break
                    before = len(current_items_map[target_col])
                    add_to_collection(driver, item, target_col)
                    current_items_map[target_col].add(item)
                    after = len(current_items_map[target_col])
                    added_counter += 1 if after > before else 0
                    if verbose:
                        print(f"    + {item} -> {target_col} ({after})")
                    added_by_collection.setdefault(tag, {}).setdefault(target_col, 0)
                    if after > before:
                        added_by_collection[tag][target_col] += 1
                    # Near limit revalidation (silent unless verbose)
                    remaining_slots = config.MAX_COLLECTION_ITEMS - len(current_items_map[target_col])
                    if 0 < remaining_slots <= 25:
                        refreshed = get_collection_items(driver, target_col)
                        current_items_map[target_col] = set(refreshed)
                        if len(refreshed) >= config.MAX_COLLECTION_ITEMS and verbose:
                            print(f"    {target_col} reached cap after refresh ({len(refreshed)})")
                # Persist per-collection cache if additions occurred
                any_added = False
                for col_id, items_set in current_items_map.items():
                    cache.setdefault(tag, {})
                    prev_cached = cache[tag].get(col_id, set())
                    before = len(prev_cached) if isinstance(prev_cached, set) else 0
                    # Safeguard: avoid overwriting with empty scrape if we previously had data (likely transient failure)
                    if len(items_set) == 0 and before > 0:
                        if verbose:
                            print(f"  WARN skip empty overwrite {col_id} (had {before})")
                        items_set = prev_cached
                    cache[tag][col_id] = items_set
                    if len(items_set) > before:
                        any_added = True
                if any_added:
                    cache_changed = True
                added_summary[tag] = added_counter
                # Compact non-verbose summary line (only show tag additions); verbose shows collection sizes
                if verbose:
                    col_states = ",".join(f"{cid}={len(current_items_map[cid])}" for cid in collections)
                    print(f"  {tag}: +{added_counter} | {col_states}")
                else:
                    print(f"  {tag}: +{added_counter}")
            except Exception as e:
                print(f"Error processing tag '{tag}': {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting early.")
        sys.exit(1)
    finally:
        driver.quit()
        # Only save and commit if cache was updated
        total_added = sum(added_summary.values())
        if cache_changed and total_added > 0:
            save_cache(cache)
            # Commit and push any changes to GitHub
            try:
                subprocess.run(["git", "add", "-A"], check=True)
                # Build commit message summarizing per-collection additions
                per_collection_parts = []
                for tag, col_map in added_by_collection.items():
                    for cid, cnt in col_map.items():
                        if cnt > 0:
                            per_collection_parts.append(f"{tag}:{cid}+{cnt}")
                if not per_collection_parts:
                    print("No per-collection additions detected; skipping commit.")
                    return
                header = "update: " + " ".join(per_collection_parts)
                commit_cmd = ["git", "commit", "-m", header]
                subprocess.run(commit_cmd, check=True)
                subprocess.run(["git", "push"], check=True)
                print("Git: Changes committed and pushed to GitHub.")
            except subprocess.CalledProcessError as e:
                print(f"Git operation failed: {e}")
        else:
            if total_added == 0:
                print("No additions; skipped commit.")
            else:
                print("Changes detected but commit skipped (unexpected state).")

if __name__ == "__main__":
    main()
