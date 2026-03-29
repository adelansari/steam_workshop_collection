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
import argparse

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
    parser = argparse.ArgumentParser(description="Steam Collection Auto-Updater")
    parser.add_argument("--login", action="store_true", help="Show browser for manual login if not logged in")
    parser.add_argument("--headful", action="store_true", help="Run browser with visible UI (non-headless)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for troubleshooting")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Steam Collection Auto-Updater")
    print("=" * 60)
    
    # Show usage hint
    if not args.login and not args.headful:
        print("\n💡 Tip: Use --login flag for first run or if not logged in:")
        print("   python auto_update_all.py --login\n")
    
    cache = load_cache()
    
    # Determine headless mode: --headful flag or --login implies non-headless
    headless = not (args.headful or args.login)
    
    if args.login:
        print("🔓 Opening browser in visible mode for login...")
    elif args.headful:
        print("👁️  Running in visible mode...")
    else:
        print("👻 Running in headless mode...")
    
    playwright, context, page, is_logged_in = config.configure_browser(
        headless=headless, 
        prompt_login=args.login
    )
    
    if not is_logged_in:
        print("\n⚠️  WARNING: Not logged into Steam. Adding items to collections will fail.")
        print("   Run with --login flag to login manually:")
        print("   python auto_update_all.py --login")
        if headless:
            print("\n   Or run with --headful to see the browser:")
            print("   python auto_update_all.py --headful")
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("Exiting...")
            context.close()
            playwright.stop()
            sys.exit(0)
    
    total_added = 0
    unsaved_count = 0  # Track adds since last save
    added_by_collection = {}  # For commit message
    
    try:
        for tag, collections in config.COLLECTION_IDS.items():
            # Track live counts from Steam (more accurate than cache)
            live_counts = {}
            # Track items actually in collections (from live scrape, NOT cache)
            # This is what we use to determine what's "known" - only real items in real collections
            items_actually_in_collections = set()
            
            print(f"\n{'='*40}")
            print(f"Processing: {tag}")
            print(f"Collections: {collections}")
            print(f"{'='*40}")
            
            # Scrape ALL collections (including locked) to know what's actually in them
            # This is critical - cache may have items that were manually removed
            for col_id in collections:
                live_items = get_collection_items(page, col_id)
                
                if live_items is None:
                    # Scrape failed - fall back to cache for this collection only
                    print(f"  Collection {col_id}: scrape failed, using cache as fallback")
                    cached_items = cache.get(tag, {}).get(col_id, set())
                    items_actually_in_collections.update(cached_items)
                    if not is_collection_locked(col_id):
                        live_counts[col_id] = len(cached_items)
                    continue
                
                print(f"  Collection {col_id}: {len(live_items)} items on Steam", end="")
                if is_collection_locked(col_id):
                    print(" (LOCKED)")
                else:
                    print("")
                    live_counts[col_id] = len(live_items)
                
                # Track what's ACTUALLY in this collection
                items_actually_in_collections.update(live_items)
                
                # Update cache to match reality (REPLACE, don't just merge)
                # This fixes the issue where cache has items that were manually removed
                cache.setdefault(tag, {})[col_id] = live_items.copy()
                
                # Check if collection is at/over limit - LOCK IT
                if len(live_items) >= config.MAX_COLLECTION_ITEMS and not is_collection_locked(col_id):
                    lock_collection(col_id)
            
            print(f"  Total items in all {tag} collections: {len(items_actually_in_collections)}")
            
            # Scrape workshop for items NOT in any collection (use live data, not cache!)
            print(f"\n  Scraping workshop for new {tag}...")
            new_items = get_workshop_items(page, tag, items_actually_in_collections)
            
            # Reverse to add oldest first (so newest end up at top of collection)
            new_items = list(reversed(new_items))
            
            if not new_items:
                print(f"  No new items to add for {tag}")
                continue
            
            print(f"  Found {len(new_items)} items to add (oldest first)")
            
            # Find first unlocked collection with capacity
            # Use live_counts for accurate capacity check
            target_col = find_next_available_collection(tag, collections, cache, live_counts)
            
            if not target_col:
                print(f"  ⚠️ All collections for {tag} are locked/full!")
                continue
            
            print(f"\n  Adding {len(new_items)} items to collection {target_col}...")
            
            # Add items one by one
            added_count = 0
            failed_items = []  # Track items that fail to add
            
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
                success = add_to_collection(page, item_id, target_col, debug=args.debug)
                
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
                    failed_items.append(item_id)
            
            # Retry failed items once more at the end
            if failed_items:
                print(f"\n  Retrying {len(failed_items)} failed items...")
                still_failed = []
                for item_id in failed_items:
                    print(f"  [Retry] Adding {item_id}...", end=" ")
                    # Small delay before retry
                    time.sleep(1)
                    success = add_to_collection(page, item_id, target_col, debug=args.debug)
                    if success:
                        cache.setdefault(tag, {}).setdefault(target_col, set())
                        cache[tag][target_col].add(item_id)
                        added_count += 1
                        total_added += 1
                        unsaved_count += 1
                        live_counts[target_col] = live_counts.get(target_col, len(cache[tag][target_col]) - 1) + 1
                        print(f"✓")
                        key = f"{tag}:{target_col}"
                        added_by_collection[key] = added_by_collection.get(key, 0) + 1
                    else:
                        print(f"✗ Failed again")
                        still_failed.append(item_id)
                
                # Save persistently failed items for manual review
                if still_failed:
                    failed_file = os.path.join(config.BASE_DIR, "failed_items.json")
                    failed_data = {}
                    if os.path.exists(failed_file):
                        try:
                            with open(failed_file, 'r') as f:
                                failed_data = json.load(f)
                        except:
                            pass
                    failed_data.setdefault(tag, []).extend(still_failed)
                    # Remove duplicates while preserving order
                    failed_data[tag] = list(dict.fromkeys(failed_data[tag]))
                    with open(failed_file, 'w') as f:
                        json.dump(failed_data, f, indent=2)
                    print(f"\n  ⚠️  {len(still_failed)} items persistently failed, saved to failed_items.json")
                    print(f"      Manual review needed for: {', '.join(still_failed[:3])}{'...' if len(still_failed) > 3 else ''}")
            
            print(f"  {tag}: added {added_count} items")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        context.close()
        playwright.stop()
        
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
