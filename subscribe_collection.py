import os
import sys
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import config

def subscribe_to_collection(collection_id="3445118133"):
    """
    Subscribe to all items in a Steam workshop collection.
    
    Args:
        collection_id (str): The ID of the collection to subscribe to
    """
    driver = config.configure_edge()
    
    try:
        print(f"Navigating to collection {collection_id}...")
        driver.get(f"{config.SHARED_FILE_DETAILS_URL}{collection_id}")
        
        # Wait for the page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # Count unsubscribed items in the collection
        items_to_subscribe = driver.find_elements(By.CSS_SELECTOR, "a.general_btn.subscribe:not(.toggled)")
        missing_count = len(items_to_subscribe)
        print(f"Found {missing_count} unsubscribed item(s) in this collection.")
        if missing_count == 0:
            print("All items already subscribed; nothing to do.")
            return 0
        print("Looking for 'Subscribe to all' button...")
        # Wait for and click the "Subscribe to all" button
        try:
            subscribe_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.general_btn.subscribe[onclick*='SubscribeCollection']"))
            )
            print("Found 'Subscribe to all' button, clicking...")
            subscribe_button.click()
        except TimeoutException:
            print("Could not find 'Subscribe to all' button. The page layout may have changed.")
            return None
        
        try:
            add_only_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'newmodal')]//div[contains(@class,'btn_green_steamui') and contains(@class,'btn_medium')]//span[text()='Add Only']"))
            )
            print("Found 'Add Only' button, clicking...")
            add_only_button.click()
            time.sleep(3)
            print(f"Successfully subscribed to {missing_count} item(s) with 'Add Only' option!")
            return missing_count
        except TimeoutException:
            print("Failed to find or click 'Add Only' button in modal.")
            return None
        
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    
    finally:
        print("Closing browser...")
        driver.quit()

def main():
    """Main function to run the subscription process."""
    print("Steam Workshop Collection Subscriber")
    print("=" * 40)
    
    # Prompt user for which tag to subscribe
    print("Available tags:")
    tags = list(config.COLLECTION_IDS.keys())
    for i, tag in enumerate(tags, start=1):
        print(f"  {i}. {tag}")
    print("  0. Enter custom collection ID")
    print(f"  {len(tags)+1}. Skip subscription (exit)")
    choice = input(f"Select a tag (1-{len(tags)}) or 0 for custom, {len(tags)+1} to skip: ").strip()
    if choice == str(len(tags)+1):
        print("Skipping subscription as requested.")
        sys.exit(0)
    elif choice == '0':
        col_ids = [input("Enter custom collection ID: ").strip()]
        tag = None
    else:
        try:
            idx = int(choice)
            if 1 <= idx <= len(tags):
                tag = tags[idx-1]
                col_ids = config.COLLECTION_IDS[tag]
            else:
                print("Invalid selection. Exiting.")
                sys.exit(1)
        except ValueError:
            print("Invalid input. Exiting.")
            sys.exit(1)
    # Subscribe to each collection ID
    for col_id in col_ids:
        success = subscribe_to_collection(col_id)
        # Provide feedback for each
        if success:
            print(f"✅ Subscribed to collection ID {col_id} successfully.")
        else:
            print(f"❌ Subscription failed for collection ID {col_id}.")
    
    # Subscription script completed; exiting without user prompt

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
