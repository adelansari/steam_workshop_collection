import os
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use a new profile directory to avoid conflicts with old Selenium profile
AUTO_PROFILE_PATH = os.path.join(BASE_DIR, "playwright_profile")
os.makedirs(AUTO_PROFILE_PATH, exist_ok=True)

# Directory to store per-tag cache files
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Maximum number of items per collection (Steam limit is ~979, use 950 for safety)
MAX_COLLECTION_ITEMS = 950

# Collection IDs for each collection name; use lists to support multiple collections per tag
COLLECTION_IDS = {
    "Characters": ["3445105194", "3531743955", "3573789008"],
    "Vehicles": ["3444831495"],
    "Tracks": ["3445118133"],
    "Wheels": ["3530392942"],
}

# The Karters 2 Workshop base URL
WORKSHOP_BASE_URL = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]="

# The base URL for shared files details
SHARED_FILE_DETAILS_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="


def configure_browser(headless=True, prompt_login=False):
    """
    Configure and launch a Playwright browser instance with persistent context.
    
    Args:
        headless (bool): Run browser in headless mode (no UI). Default True.
        prompt_login (bool): If True and not logged in, show browser for manual login.
    
    Returns:
        tuple: (playwright_instance, context, page, is_logged_in) - caller should call context.close() 
               and playwright.stop() when done
    """
    playwright = sync_playwright().start()
    
    # Launch browser with persistent context for session storage
    # Using Chromium (Edge/Chrome) for compatibility with Steam
    # Launch browser with persistent context for session storage
    # Note: If profile is corrupted, delete the playwright_profile folder and retry
    try:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=AUTO_PROFILE_PATH,
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--disable-restore-session-state",
                "--ignore-certificate-errors",
                "--allow-running-insecure-content",
            ],
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
        )
    except Exception as e:
        print(f"\n⚠️  Failed to launch browser: {e}")
        print("The browser profile may be corrupted.")
        response = input("Delete the profile and try again? (y/n): ").strip().lower()
        if response == 'y':
            import shutil
            shutil.rmtree(AUTO_PROFILE_PATH, ignore_errors=True)
            os.makedirs(AUTO_PROFILE_PATH, exist_ok=True)
            # Retry
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=AUTO_PROFILE_PATH,
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-first-run",
                ],
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True,
            )
        else:
            raise
    
    # Hide automation flags via extra HTTP headers and script injection
    page = context.new_page()
    
    # Inject script to hide webdriver property
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)
    
    # Check if logged in
    is_logged_in = check_login_status(page)
    
    # If not logged in and prompt_login requested, show browser for manual login
    if not is_logged_in and prompt_login:
        print("\n⚠️  Not logged into Steam.")
        print("=" * 50)
        print("IMPORTANT: A browser window should have opened.")
        print("1. Login to Steam in the browser window")
        print("2. DO NOT close the browser window")
        print("3. Come back here and press Enter when done")
        print("=" * 50)
        
        # Check if context is still valid
        try:
            # Try a simple operation to verify browser is still open
            _ = context.pages
        except Exception:
            print("\n❌ Browser was closed. Restarting with fresh context...")
            context.close()
            # Relaunch with same settings
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=AUTO_PROFILE_PATH,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-first-run",
                ],
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True,
            )
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)
        
        print("\nPress Enter when you've logged in...", end="")
        input()
        
        # Check again after user says they've logged in
        try:
            is_logged_in = check_login_status(page)
            if is_logged_in:
                print("✅ Login confirmed!")
            else:
                print("❌ Still not logged in. Continuing anyway (adding items will fail)...")
        except Exception as e:
            print(f"❌ Error checking login status: {e}")
            print("   The browser may have been closed. Continuing anyway...")
            is_logged_in = False
    
    return playwright, context, page, is_logged_in


def check_login_status(page):
    """
    Check if user is logged into Steam by looking for user avatar or account menu.
    Returns True if logged in, False otherwise.
    """
    try:
        page.goto("https://steamcommunity.com/", timeout=30000, wait_until="domcontentloaded")
        # Multiple ways to detect logged-in state on Steam
        # 1. User avatar in global header
        # 2. Account pulldown menu  
        # 3. "Logout" link
        # 4. Absence of "Login" button
        user_avatar = page.query_selector(".global_header .user_avatar")
        account_pulldown = page.query_selector("#account_pulldown")
        logout_link = page.query_selector("a[href*='Logout']")
        login_button = page.query_selector("a[href*='login'], .global_header #global_actions .header_installsteam_btn")
        
        # Log what we found for debugging
        print(f"    Login check: avatar={user_avatar is not None}, pulldown={account_pulldown is not None}, "
              f"logout={logout_link is not None}, login_btn={login_button is not None}")
        
        # If we see logout link or user avatar, we're logged in
        # If we only see login button, we're not logged in
        if logout_link or user_avatar or account_pulldown:
            return True
        if login_button:
            return False
        # Ambiguous case - assume not logged in to be safe
        return False
    except Exception as e:
        print(f"    Error checking login status: {e}")
        return False
