"""
Standalone Steam login script.
Run this once to establish a logged-in session, then use auto_update_all.py normally.
"""

import os
import sys
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(BASE_DIR, "playwright_profile")
os.makedirs(PROFILE_PATH, exist_ok=True)


def main():
    print("=" * 50)
    print("Steam Login - Manual Login Helper")
    print("=" * 50)
    print("\nThis will open a browser window.")
    print("1. Login to Steam")
    print("2. Keep the browser open")
    print("3. Press Enter in this window when done")
    print("\nStarting browser...")
    
    with sync_playwright() as p:
        # Launch browser with persistent context
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_PATH,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
            viewport={"width": 1920, "height": 1080},
        )
        
        page = context.new_page()
        
        # Navigate to Steam login page
        print("Opening Steam login page...")
        page.goto("https://steamcommunity.com/login/home/?goto=")
        
        print("\n" + "=" * 50)
        print("Browser is open. Please:")
        print("1. Login to Steam in the browser window")
        print("2. DO NOT close the browser")
        print("3. Press Enter here when logged in")
        print("=" * 50)
        input()
        
        # Check if logged in
        page.goto("https://steamcommunity.com/")
        logout_btn = page.query_selector("a[href*='Logout']")
        user_avatar = page.query_selector(".global_header .user_avatar")
        
        if logout_btn or user_avatar:
            print("\n✅ Login successful! Session saved.")
            print("You can now run: python auto_update_all.py")
        else:
            print("\n⚠️  Could not verify login. You may need to try again.")
        
        context.close()
        print("\nBrowser closed. Session saved to playwright_profile/")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
