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
        
        print("Looking for 'Subscribe to all' button...")
        
        # Wait for and click the "Subscribe to all" button
        try:
            subscribe_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.general_btn.subscribe[onclick*='SubscribeCollection']"))
            )
            print("Found 'Subscribe to all' button, clicking...")
            subscribe_button.click()
        except TimeoutException:
            print("Could not find 'Subscribe to all' button. The collection might already be subscribed to, or the page layout has changed.")
            return False
        
        # Wait for the modal dialog to appear
        print("Waiting for subscription modal to appear...")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".newmodal"))
            )
            print("Modal appeared, looking for 'Add Only' button...")
        except TimeoutException:
            print("Modal did not appear. Checking if subscription was successful...")
            time.sleep(2)
            return True
        
        # Click the "Add Only" button in the modal
        try:
            add_only_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'btn_green_steamui') and contains(@class, 'btn_medium')]//span[text()='Add Only']"))
            )
            print("Found 'Add Only' button, clicking...")
            add_only_button.click()
            
            # Wait a moment for the action to complete
            time.sleep(3)
            print("Successfully subscribed to collection with 'Add Only' option!")
            return True
            
        except TimeoutException:
            print("Could not find 'Add Only' button in the modal. Trying alternative selector...")
            
            # Try alternative selector
            try:
                add_only_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div.btn_green_steamui.btn_medium"))
                )
                print("Found 'Add Only' button with alternative selector, clicking...")
                add_only_button.click()
                time.sleep(3)
                print("Successfully subscribed to collection with 'Add Only' option!")
                return True
            except TimeoutException:
                print("Could not find 'Add Only' button with any selector.")
                return False
        
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
    
    # Use the Tracks collection ID from config
    collection_id = config.COLLECTION_IDS.get("Tracks", "3445118133")
    
    print(f"Starting subscription process for collection: {collection_id}")
    print("This will subscribe to all items in the collection using 'Add Only' mode.")
    print("This means Steam will automatically check for downloads when you start the game.")
    print()
    
    success = subscribe_to_collection(collection_id)
    
    if success:
        print("\n✅ Collection subscription completed successfully!")
        print("Steam will now automatically check for and download new items from this collection when you start the game.")
    else:
        print("\n❌ Collection subscription failed or was incomplete.")
        print("You may need to manually subscribe to the collection or check your Steam login status.")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Press Enter to exit...")
        input()
        sys.exit(1)
