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
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    # Security bypass (temporary)
    options.set_capability('acceptInsecureCerts', True)
    
    service = Service(EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
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
            # Using the correct selector based on your HTML
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