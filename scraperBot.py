"""
scraper.py
Full scraper for asset.led.go.th with CLI controls.
"""

import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

try:
    from tqdm import tqdm
except ImportError:
    class _TqdmFallback:
        def __init__(self, iterable=None, total=None, desc=None, leave=True):
            self.iterable = iterable

        def __iter__(self):
            return iter(self.iterable) if self.iterable is not None else iter(())

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, n=1):
            return None

        @staticmethod
        def write(message):
            print(message)

    def tqdm(iterable=None, total=None, desc=None, leave=True):
        return _TqdmFallback(iterable=iterable, total=total, desc=desc, leave=leave)

from bots.parse_detail import parse_detail
from bots.db import init_db, insert_stub, update_full

BASE_URL = "https://asset.led.go.th/newbid-old"
LIST_URL = f"{BASE_URL}/asset_search_province.asp?search_asset_type_id=&search_tumbol=&search_ampur=&search_province=%A1%C3%D8%A7%E0%B7%BE&search_sub_province=&search_price_begin=&search_price_end=&search_bid_date=&page="
IMAGE_DIR = "/mnt/0CDCB75BDCB73E30/scraperBots/images"
DELAY = 1.0


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.content.decode("cp874")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(DELAY * 2)
            else:
                raise e


def fetch_binary(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.content
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(DELAY * 2)
            else:
                raise e


def encode_thai(path):
    return quote(path.encode("cp874"), safe="/:?=&.-_")


def get_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    pages = set()
    for a in soup.find_all("a", href=True):
        if "page=" in a["href"]:
            try:
                pages.add(int(a["href"].split("page=")[-1]))
            except ValueError:
                pass
    return max(pages) if pages else 1


def parse_list_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for tr in soup.find_all("tr", onclick=True):
        onclick = tr["onclick"]
        start = onclick.find("'") + 1
        end = onclick.find("'", start)
        detail_path = onclick[start:end]

        if not detail_path:
            continue

        tds = tr.find_all("td")

        def td(i):
            return tds[i].get_text(strip=True) if i < len(tds) else ""

        rows.append(
            {
                "detail_path": detail_path,
                "asset_sequence": td(0),
                "case_number": td(1),
                "asset_type": td(2),
                "rai": td(3),
                "ngan": td(4),
                "sqwah": td(5),
                "appraisal_officer": td(6),
                "tambon": td(7),
                "amphoe": td(8),
                "province": td(9),
            }
        )

    return rows


def download_image(image_path, deed_number):
    folder = os.path.join(IMAGE_DIR, deed_number or "unknown")
    os.makedirs(folder, exist_ok=True)

    filename = image_path.split("/")[-1]
    save_path = os.path.join(folder, filename)

    if os.path.exists(save_path):
        return save_path

    encoded = encode_thai(image_path)
    img_url = f"{BASE_URL}/{encoded}"

    try:
        data = fetch_binary(img_url)
        with open(save_path, "wb") as f:
            f.write(data)
        return save_path
    except Exception as e:
        tqdm.write(f"[IMG FAIL] {img_url}: {e}")
        return None


def scrape(start_page, end_page, dry_run, prefetched_first_html=None):
    if not dry_run:
        init_db()

    os.makedirs(IMAGE_DIR, exist_ok=True)

    if prefetched_first_html is None:
        first_html = fetch(LIST_URL + "1")
        time.sleep(DELAY)
    else:
        first_html = prefetched_first_html

    total_pages = get_total_pages(first_html)

    if end_page is None:
        end_page = total_pages

    stats = {"scraped": 0, "created": 0, "updated": 0, "errors": 0}

    with tqdm(total=end_page - start_page + 1, desc="Pages") as page_bar:
        for page in range(start_page, end_page + 1):

            try:
                html = first_html if page == 1 else fetch(LIST_URL + str(page))
                time.sleep(DELAY)
            except Exception as e:
                tqdm.write(f"[PAGE FAIL] {page}: {e}")
                page_bar.update(1)
                continue

            rows = parse_list_rows(html)

            with tqdm(total=len(rows), desc=f"Page {page}", leave=False) as row_bar:
                for row in rows:
                    stats["scraped"] += 1
                    detail_path = row["detail_path"]

                    try:
                        if not dry_run:
                            row_id, created = insert_stub(row)

                        detail_html = fetch(f"{BASE_URL}/{encode_thai(detail_path)}")
                        time.sleep(DELAY)

                        data = {**row, **parse_detail(detail_html)}

                        if not dry_run:
                            images = data.get("images", [])
                            if images:
                                local = download_image(images[0], data.get("deed_number"))
                                if local:
                                    data["image_1"] = local
                                for idx, image_path in enumerate(images[1:3], start=2):
                                    data[f"image_{idx}"] = image_path

                            update_full(row_id, data)
                            if created:
                                stats["created"] += 1
                            else:
                                stats["updated"] += 1
                        else:
                            tqdm.write(f"[DRY] {row.get('case_number')}")

                    except Exception as e:
                        tqdm.write(f"[ROW FAIL] {detail_path}: {e}")
                        stats["errors"] += 1

                    row_bar.update(1)

            page_bar.update(1)

    print("\nDone")
    print(stats)


if __name__ == "__main__":
    print("Connecting...")

    first_html = fetch(LIST_URL + "1")
    total_pages = get_total_pages(first_html)

    print(f"Pages: {total_pages}")

    start_input = input("Start page (default 1): ").strip()
    start = int(start_input) if start_input else 1

    end_input = input("End page (default all): ").strip().lower()

    if end_input in ("", "all"):
        end = None
    elif end_input.isdigit():
        end = int(end_input)
    else:
        raise ValueError("Use number or all")

    dry = False

    scrape(start, end, dry, first_html)
