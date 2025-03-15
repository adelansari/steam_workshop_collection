# Steam Collection Auto-Add

A Python automation script that collects Steam Workshop items matching specific criteria and adds them to a designated collection.

## Description

This script automates the process of browsing through Steam Workshop pages, collecting items with specific tags, and adding them to your Steam collection. It uses Selenium with Microsoft Edge WebDriver to interact with the Steam website.

## Features

- Automatically scrapes Steam Workshop pages for items with specific tags.
- Extracts unique item IDs from the workshop listings.
- **Optimized collection update:** Scrapes the current collection to only add missing items.
- Handles pagination to collect items from multiple pages.
- Uses your existing Steam login session from an Edge browser profile.
- Improved speed by reducing unnecessary delays and optimizing element waits.

## Prerequisites

- Python 3.x
- Microsoft Edge browser
- Microsoft Edge WebDriver (matching your Edge version)
- Steam account with an existing collection

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/adelansari/steam_workshop_collection.git
   cd steam_workshop_collection
   ```

2. Install required dependencies:
   ```
   pip install selenium
   ```

3. Download [Microsoft Edge WebDriver](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/) that matches your Edge browser version

## Configuration

Edit the following variables in `steam_collection_bot.py`:

```python
# Configuration
COLLECTION_ID = "3444831495"  # Your Steam collection ID
EDGE_PROFILE_PATH = r"C:\Users\yourusername\AppData\Local\Microsoft\Edge\User Data\Default"
EDGE_DRIVER_PATH = r"C:\path\to\msedgedriver.exe"  # Path to Edge WebDriver
```

To change which items are collected, modify the base URL in the `get_workshop_items` function:

```python
base_url = "https://steamcommunity.com/workshop/browse/?appid=2269950&requiredtags[]=Vehicles&p="
```

## Usage

1. Make sure you're logged into Steam in your Edge browser.
2. Run the script:
   ```
   python steam_collection_bot.py
   ```

3. The script will:
   - Open Edge browser using your profile.
   - Navigate through Steam Workshop pages and scrape item IDs.
   - Scrape the existing collection to determine which items are missing.
   - Visit only the missing item pages and add them to your collection.
   - Close the browser when finished.

## How it Works

1. **Configure WebDriver**: Sets up Microsoft Edge with your browser profile and necessary options.
2. **Collect Workshop Items**: Navigates through workshop pages, scrapes item links, and extracts IDs.
3. **Scrape Existing Collection**: Loads your collection page, scrapes and identifies items already added.
4. **Efficient Update**: Only the missing workshop items are visited and added to the collection, reducing unnecessary page loads.
5. **Optimizations**: Uses dynamic waits with WebDriverWait and minimizes delays to significantly improve performance.