from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import re
import os

CHROME_PROFILE = "/home/aasava/.config/google-chrome/Profile 2"
OUTPUT_DIR = "/mnt/0CDCB75BDCB73E30/scraperBots/html"

URL = input("URL: ").strip()

slug = re.sub(r"[^a-zA-Z0-9]", "_", urlparse(URL).path.strip("/"))
OUTPUT = os.path.join(OUTPUT_DIR, f"{slug or 'page'}.html")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE, channel="chrome", headless=True
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto(URL)
    page.wait_for_timeout(3000)

    html = page.content()
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved to {OUTPUT}")
    browser.close()
