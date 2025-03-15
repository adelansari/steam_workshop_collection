import os
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium import webdriver

EDGE_PROFILE_PATH = r"C:\Users\adela\AppData\Local\Microsoft\Edge\User Data\Default"
EDGE_DRIVER_PATH = r"C:\EdgeDriver\msedgedriver.exe"

# Collection IDs for each collection name
COLLECTION_IDS = {
    "Characters": "3445105194",
    "Vehicles": "3444831495",
    "Tracks": "3445118133"
}

# The Karters 2 Workshop base URL
WORKSHOP_BASE_URL = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]="


def configure_edge():
    options = Options()
    options.add_argument(f"user-data-dir={EDGE_PROFILE_PATH}")
    options.add_argument("profile-directory=Default")
    options.add_argument("--disable-infobars")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-restore-session-state")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    # options.add_argument("--headless=new")
    options.add_argument("--log-level=3")
    # Disable images to speed up loading:
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.set_capability('acceptInsecureCerts', True)
    
    service = Service(EDGE_DRIVER_PATH, log_path=os.devnull)
    driver = webdriver.Edge(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver