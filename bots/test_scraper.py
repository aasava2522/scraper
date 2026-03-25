"""
test_scraper.py
Fetches first row only from pages 1 and 2. Prints result, does NOT save to DB.
"""

import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

from bots.parse_detail import parse_detail

BASE_URL = "https://asset.led.go.th/newbid-old"
LIST_URL = f"{BASE_URL}/asset_search_province.asp?search_asset_type_id=&search_tumbol=&search_ampur=&search_province=%A1%C3%D8%A7%E0%B7%BE&search_sub_province=&search_price_begin=&search_price_end=&search_bid_date=&page="
DELAY = 1.0


def fetch(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.content.decode("cp874")


def encode_thai(path):
    return quote(path.encode("cp874"), safe="/:?=&.-_")


def get_first_row(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr", onclick=True)
    if not rows:
        return None
    onclick = rows[0]["onclick"]
    url_start = onclick.find("'") + 1
    url_end = onclick.find("'", url_start)
    return onclick[url_start:url_end]


for page_num in [1, 2]:
    print(f"\n{'='*60}")
    print(f"PAGE {page_num}")
    print(f"{'='*60}")

    list_html = fetch(LIST_URL + str(page_num))
    time.sleep(DELAY)

    detail_path = get_first_row(list_html)
    if not detail_path:
        print("  No rows found.")
        continue

    encoded = encode_thai(detail_path)
    detail_url = f"{BASE_URL}/{encoded}"
    print(f"Detail URL: {detail_url}")

    detail_html = fetch(detail_url)
    time.sleep(DELAY)

    data = parse_detail(detail_html)
    for k, v in data.items():
        print(f"  {k}: {v!r}")
