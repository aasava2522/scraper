import requests
from bs4 import BeautifulSoup
import csv

BASE_URL = "https://asset.led.go.th/newbid-old/asset_search_province.asp"
PARAMS = {
    "search_asset_type_id": "",
    "search_tumbol": "",
    "search_ampur": "",
    "search_province": "%A1%C3%D8%A7%E0%B7%BE",
    "search_sub_province": "",
    "search_price_begin": "",
    "search_price_end": "",
    "search_bid_date": "",
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_page(page_num):
    params = {**PARAMS, "page": str(page_num)}
    url = BASE_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    response = requests.get(url, headers=headers)
    response.encoding = "tis-620"
    return response.text


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    rows_data = []
    for table in tables:
        for row in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if cols:
                rows_data.append(cols)
    return rows_data


# --- Step 1: Inspect page 212 first ---
print("=== INSPECTING PAGE 212 ===")
html = fetch_page(212)
soup = BeautifulSoup(html, "html.parser")
print("Title:", soup.title.string if soup.title else "None")
print("\nText preview:\n", soup.get_text()[:2000])

tables = soup.find_all("table")
print(f"\n{len(tables)} table(s) found")
for i, table in enumerate(tables):
    rows = table.find_all("tr")
    print(f"\n-- Table {i+1}: {len(rows)} rows --")
    for j, row in enumerate(rows[:5]):
        cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        print(f"  Row {j+1}: {cols}")

# --- Step 2: Once structure confirmed, scrape all pages ---
# Uncomment below after reviewing output above

# all_rows = []
# page = 1
# while True:
#     print(f"Scraping page {page}...")
#     html = fetch_page(page)
#     rows = parse_page(html)
#     if not rows:
#         break
#     all_rows.extend(rows)
#     page += 1
#
# with open("led_assets_all.csv", "w", newline="", encoding="utf-8-sig") as f:
#     writer = csv.writer(f)
#     writer.writerows(all_rows)
# print(f"Done. {len(all_rows)} rows saved to led_assets_all.csv")
