from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.common.exceptions import TimeoutException
import time
import os

# Configuration
COLLECTION_ID = "3444831495"
EDGE_PROFILE_PATH = r"C:\Users\adela\AppData\Local\Microsoft\Edge\User Data\Default"
EDGE_DRIVER_PATH = r"C:\EdgeDriver\msedgedriver.exe"

os.environ['WDM_LOCAL'] = '1'
os.environ['WDM_SSL_VERIFY'] = '0'

def configure_edge():
    options = Options()
    options.add_argument(f"user-data-dir={EDGE_PROFILE_PATH}")
    options.add_argument("profile-directory=Default")
    options.add_argument("--disable-infobars")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-restore-session-state")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument("--headless=new")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    # Security bypass (temporary)
    options.set_capability('acceptInsecureCerts', True)
    
    service = Service(EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver

def get_collection_items(driver):
    # Load the collection page
    collection_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={COLLECTION_ID}"
    driver.get(collection_url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".collectionChildren"))
        )
    except TimeoutException:
        print("Failed to load collection items")
        return set()
    
    # Scrape item IDs from collection
    collection_elements = driver.find_elements(By.CSS_SELECTOR, ".collectionItem a[href*='filedetails/?id=']")
    collection_ids = set()
    for elem in collection_elements:
        href = elem.get_attribute("href")
        if href and "id=" in href:
            item_id = href.split("id=")[1].split("&")[0]
            collection_ids.add(item_id)
    print(f"Found {len(collection_ids)} items in the collection")
    return collection_ids

def get_workshop_items(driver):
    base_url = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]=Vehicles&p="
    workshop_ids = set()
    page = 1
    
    while True:
        print(f"Scraping workshop page {page}...")
        driver.get(f"{base_url}{page}")
        # wait briefly for the items to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a.item_link'))
            )
        except TimeoutException:
            # if no items found after waiting, break out of the loop
            if "No items matching your search criteria were found." in driver.page_source:
                print("No more items found.")
            else:
                print(f"Timeout waiting on page {page}")
            break
        
        items = driver.find_elements(By.CSS_SELECTOR, 'a.item_link')
        if not items:
            print("No items returned; breaking loop")
            break
        
        print(f"Found {len(items)} items on page {page}")
        for item in items:
            href = item.get_attribute("href")
            if href and "id=" in href:
                item_id = href.split("id=")[1].split("&")[0]
                workshop_ids.add(item_id)
        page += 1
    print(f"Total workshop items scraped: {len(workshop_ids)}")
    return workshop_ids

def add_to_collection(driver, item_ids):
    # Process each missing workshop item
    for item_id in item_ids:
        try:
            print(f"Adding item {item_id} to collection...")
            driver.get(f"https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}")
            
            # Wait for the Add button
            add_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".general_btn[onclick*='AddToCollection']"))
            )
            add_button.click()
            
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "AddToCollectionDialog"))
            )
            
            collection_checkbox = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, COLLECTION_ID))
            )
            if not collection_checkbox.is_selected():
                collection_checkbox.click()
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_green_steamui.btn_medium span"))
            ).click()
            
            print(f"Successfully added item {item_id} to collection")
            # brief pause to ensure processing before next addition
            time.sleep(1)
        except Exception as e:
            print(f"Failed to add {item_id}: {str(e)}")

if __name__ == "__main__":
    driver = configure_edge()
    try:
        collection_ids = get_collection_items(driver)
        workshop_ids = get_workshop_items(driver)
        # Only add items not already in collection
        missing_ids = list(workshop_ids - collection_ids)
        print(f"Missing {len(missing_ids)} items to add")
        if missing_ids:
            add_to_collection(driver, missing_ids)
        else:
            print("No missing items to add. Collection is up-to-date.")
    finally:
        driver.quit()