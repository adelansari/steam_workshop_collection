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

# The base URL for shared files details
SHARED_FILE_DETAILS_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="

def configure_edge():
    options = Options()
    args = [
        f"user-data-dir={EDGE_PROFILE_PATH}",
        "profile-directory=Default",
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

    # Disable images to speed up loading:
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.set_capability('acceptInsecureCerts', True)

    service = Service(EDGE_DRIVER_PATH, log_path=os.devnull)
    driver = webdriver.Edge(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver