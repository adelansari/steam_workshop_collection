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

def get_workshop_items(driver):
    base_url = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]=Vehicles&p="
    item_ids = []
    page = 1
    
    while True:
        print(f"Navigating to page {page}...")
        driver.get(f"{base_url}{page}")
        time.sleep(3)  # Give page time to load
        
        if "No items matching your search criteria were found." in driver.page_source:
            print("No more items found, breaking loop")
            break
        
        try:
            items = WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.item_link'))
            )
            
            print(f"Found {len(items)} items on page {page}")
            for item in items:
                href = item.get_attribute("href")
                if href and "id=" in href:
                    item_id = href.split("id=")[1].split("&")[0]
                    item_ids.append(item_id)
                    print(f"Added item ID: {item_id}")
        except TimeoutException:
            print(f"Timeout while waiting for items on page {page}")
            break
        except Exception as e:
            print(f"Error on page {page}: {str(e)}")
            break
        
        page += 1
    
    return list(set(item_ids))

def add_to_collection(driver, item_ids):
    for item_id in item_ids:
        try:
            print(f"Adding item {item_id} to collection...")
            driver.get(f"https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}")
            
            # Wait for the page to fully load
            time.sleep(5)
            
            add_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".general_btn[onclick*='AddToCollection']"))
            )
            add_button.click()
            
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.ID, "AddToCollectionDialog"))
            )
            
            collection_checkbox = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, COLLECTION_ID))
            )
            
            if not collection_checkbox.is_selected():
                collection_checkbox.click()
            
            # Click the OK button
            WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_green_steamui.btn_medium span"))
            ).click()
            
            print(f"Successfully added item {item_id} to collection")
            time.sleep(3)
            
        except Exception as e:
            print(f"Failed to add {item_id}: {str(e)}")

if __name__ == "__main__":
    driver = configure_edge()
    try:
        items = get_workshop_items(driver)
        print(f"Found {len(items)} vehicles to add")
        add_to_collection(driver, items)
    finally:
        driver.quit()