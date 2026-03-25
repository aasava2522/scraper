from playwright.sync_api import sync_playwright

CHROME_PROFILE = "/home/aasava/.config/google-chrome/Profile 2"
GROUP_URL = "https://www.facebook.com/groups/386316227145323/"

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE, channel="chrome", headless=False
    )
    page = browser.new_page()
    page.goto(GROUP_URL)
    page.wait_for_timeout(5000)
    print(page.title())
    input("Press Enter to close...")
    browser.close()
