"""
Auto-update all Steam collections.

Logic:
1. For each tag (Characters, Vehicles, etc.):
   - Load cache (known items per collection)
   - Skip any LOCKED collections (permanently full)
   - Scrape workshop for new items not in any collection's cache
   - Add new items to the FIRST non-locked collection with capacity
   - When a collection reaches MAX_COLLECTION_ITEMS, LOCK it permanently
   - Update cache only with successfully added items
2. Commit and push changes to git
"""

import os
import sys
import time
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

import config
from steam_collection_bot import (
    load_cache,
    save_cache,
    get_all_cached_items_for_tag,
    get_collection_items,
    get_workshop_items,
    add_to_collection,
    load_locked_collections,
    lock_collection,
    is_collection_locked,
)

# How often to save cache (every N successful adds)
SAVE_INTERVAL = 5


def find_next_available_collection(tag, collections, cache, live_counts):
    """Find first unlocked collection with remaining capacity.
    
    Uses live_counts (from Steam scrape) when available, falls back to cache.
    This prevents overfilling when Steam has more items than our cache.
    """
    for col_id in collections:
        if is_collection_locked(col_id):
            continue
        # Use live count if available (more accurate), otherwise use cache
        actual_count = live_counts.get(col_id) if col_id in live_counts else len(cache.get(tag, {}).get(col_id, set()))
        if actual_count < config.MAX_COLLECTION_ITEMS:
            return col_id
    return None


def main():
    print("=" * 60)
    print("Steam Collection Auto-Updater")
    print("=" * 60)
    
    cache = load_cache()
    driver = config.configure_edge()
    
    total_added = 0
    unsaved_count = 0  # Track adds since last save
    added_by_collection = {}  # For commit message
    
    try:
        for tag, collections in config.COLLECTION_IDS.items():
            # Track live counts from Steam (more accurate than cache)
            live_counts = {}
            print(f"\n{'='*40}")
            print(f"Processing: {tag}")
            print(f"Collections: {collections}")
            print(f"{'='*40}")
            
            # Get all known items for this tag from cache
            all_known_items = get_all_cached_items_for_tag(cache, tag)
            print(f"  Cached items for {tag}: {len(all_known_items)}")
            
            # Also scrape each collection to update cache and detect full ones
            # But ONLY for unlocked collections
            for col_id in collections:
                if is_collection_locked(col_id):
                    print(f"  Collection {col_id}: LOCKED (skipping scrape)")
                    continue
                    
                live_items = get_collection_items(driver, col_id)
                
                if live_items is None:
                    # Scrape failed - keep using cache, don't wipe it
                    print(f"  Collection {col_id}: scrape failed, using cache")
                    continue
                
                print(f"  Collection {col_id}: {len(live_items)} items on Steam")
                
                # Track the ACTUAL live count from Steam (this is the real capacity usage)
                live_counts[col_id] = len(live_items)
                
                # Warn if live count differs significantly from cache
                cached_count = len(cache.get(tag, {}).get(col_id, set()))
                if live_items and abs(len(live_items) - cached_count) > 5:
                    print(f"    ⚠️ Live count ({len(live_items)}) differs from cache ({cached_count})")
                
                # Merge into cache (cache only grows, never shrinks)
                cache.setdefault(tag, {}).setdefault(col_id, set())
                cache[tag][col_id].update(live_items)
                all_known_items.update(live_items)
                
                # Check if collection is at/over limit - LOCK IT
                if len(live_items) >= config.MAX_COLLECTION_ITEMS:
                    lock_collection(col_id)
            
            # Scrape workshop for new items
            print(f"\n  Scraping workshop for new {tag}...")
            new_items = get_workshop_items(driver, tag, all_known_items)
            
            if not new_items:
                print(f"  No new items to add for {tag}")
                continue
            
            # Find first unlocked collection with capacity
            # Use live_counts for accurate capacity check
            target_col = find_next_available_collection(tag, collections, cache, live_counts)
            
            if not target_col:
                print(f"  ⚠️ All collections for {tag} are locked/full!")
                continue
            
            print(f"\n  Adding {len(new_items)} items to collection {target_col}...")
            
            # Add items one by one
            added_count = 0
            for idx, item_id in enumerate(new_items, 1):
                # Check if current target is full, switch if needed
                # Use live_counts if available, updated as we add items
                current_count = live_counts.get(target_col, len(cache.get(tag, {}).get(target_col, set())))
                if current_count >= config.MAX_COLLECTION_ITEMS:
                    # This collection is now full, lock it and find next
                    lock_collection(target_col)
                    target_col = find_next_available_collection(tag, collections, cache, live_counts)
                    
                    if not target_col:
                        print(f"  ⚠️ All collections full for {tag}, stopping")
                        break
                    
                    print(f"  Switching to collection {target_col}")
                
                # Try to add the item
                print(f"  [{idx}/{len(new_items)}] Adding {item_id}...", end=" ")
                success = add_to_collection(driver, item_id, target_col)
                
                if success:
                    # Update cache immediately
                    cache.setdefault(tag, {}).setdefault(target_col, set())
                    cache[tag][target_col].add(item_id)
                    added_count += 1
                    total_added += 1
                    unsaved_count += 1
                    
                    # Update live_counts to track actual capacity (increment by 1)
                    live_counts[target_col] = live_counts.get(target_col, len(cache[tag][target_col]) - 1) + 1
                    
                    actual_count = live_counts[target_col]
                    remaining = config.MAX_COLLECTION_ITEMS - actual_count
                    print(f"✓ ({actual_count}/{config.MAX_COLLECTION_ITEMS}, {remaining} left)")
                    
                    # Track for commit message
                    key = f"{tag}:{target_col}"
                    added_by_collection[key] = added_by_collection.get(key, 0) + 1
                    
                    # Check if we just filled it - lock and switch immediately
                    if actual_count >= config.MAX_COLLECTION_ITEMS:
                        lock_collection(target_col)
                        target_col = find_next_available_collection(tag, collections, cache, live_counts)
                        if target_col:
                            print(f"  Switching to collection {target_col}")
                    
                    # Periodic save to protect against crashes
                    if unsaved_count >= SAVE_INTERVAL:
                        save_cache(cache)
                        unsaved_count = 0
                        print(f"  [Cache saved]")
                    
                    # Small delay to avoid hammering Steam
                    time.sleep(0.3)
                else:
                    print(f"✗ Failed")
            
            print(f"  {tag}: added {added_count} items")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        driver.quit()
        
        # Always save cache if anything was added (even on interrupt/error)
        if total_added > 0 or unsaved_count > 0:
            print(f"\nSaving cache...")
            save_cache(cache)
            
            # Git commit and push
            try:
                subprocess.run(["git", "add", "-A"], check=True)
                
                parts = [f"{k}+{v}" for k, v in added_by_collection.items() if v > 0]
                if parts:
                    msg = "update: " + " ".join(parts)
                    subprocess.run(["git", "commit", "-m", msg], check=True)
                    subprocess.run(["git", "push"], check=True)
                    print(f"Git: committed and pushed ({msg})")
            except subprocess.CalledProcessError as e:
                print(f"Git error: {e}")
        else:
            print("\nNo changes to save")
    
    print(f"\n{'='*60}")
    print(f"Done! Total added: {total_added}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
