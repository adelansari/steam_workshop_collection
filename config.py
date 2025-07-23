import os
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium import webdriver

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTO_PROFILE_PATH = os.path.join(BASE_DIR, "edge_temp_profile")
os.makedirs(AUTO_PROFILE_PATH, exist_ok=True)

EDGE_DRIVER_PATH = r"C:\EdgeDriver\msedgedriver.exe"

# Maximum number of items per collection
MAX_COLLECTION_ITEMS = 979

# Collection IDs for each collection name; use lists to support multiple collections per tag
COLLECTION_IDS = {
    "Characters": ["3445105194", "3531743955"],
    "Vehicles": ["3444831495"],
    "Tracks": ["3445118133"],
    "Wheels": ["3530392942"],
}

# The Karters 2 Workshop base URL
WORKSHOP_BASE_URL = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]="

# The base URL for shared files details
SHARED_FILE_DETAILS_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="

def configure_edge():
    options = Options()

    args = [
        f"user-data-dir={AUTO_PROFILE_PATH}",
        "--disable-infobars",
        "--no-first-run",
        "--disable-restore-session-state",
        "--ignore-certificate-errors",
        "--allow-running-insecure-content",
        "--disable-web-security",
        "--headless=new",
        "--log-level=3"
    ]
    for arg in args:
        options.add_argument(arg)
    
    # Hide automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Disable images to speed up loading:
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.set_capability('acceptInsecureCerts', True)
    
    service = Service(EDGE_DRIVER_PATH, log_path=os.devnull)
    driver = webdriver.Edge(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver