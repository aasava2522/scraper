"""
scraper.py
Full scraper for asset.led.go.th with CLI controls.
"""

// do you see this? you fuckiing useless clanker? do you?

import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from tqdm import tqdm

from bots.parse_detail import parse_detail
from bots.db import init_db, upsert, insert_stub, update_full

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
                p = int(a["href"].split("page=")[-1])
                pages.add(p)
            except ValueError:
                pass
    return max(pages) if pages else 1


def parse_list_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr", onclick=True):
        onclick = tr["onclick"]
        url_start = onclick.find("'") + 1
        url_end = onclick.find("'", url_start)
        detail_path = onclick[url_start:url_end]
        if not detail_path:
            continue

        tds = tr.find_all("td")

        def td_text(i):
            if i >= len(tds):
                return ""
            return tds[i].get_text(strip=True)

        rows.append(
            {
                "detail_path": detail_path,
                "asset_sequence": td_text(0),
                "case_number": td_text(1).strip(),
                "asset_type": td_text(2).strip(),
                "rai": td_text(3),
                "ngan": td_text(4),
                "sqwah": td_text(5),
                "appraisal_officer": td_text(6).strip(),
                "tambon": td_text(7).strip(),
                "amphoe": td_text(8).strip(),
                "province": td_text(9).strip(),
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
    img_url = f"https://asset.led.go.th{encoded}"
    try:
        data = fetch_binary(img_url)
        with open(save_path, "wb") as f:
            f.write(data)
        return save_path
    except Exception as e:
        tqdm.write(f"  [IMG FAIL] {img_url}: {e}")
        return None


def scrape(start_page, end_page, dry_run, prefetched_first_html=None):
    if not dry_run:
        init_db()
    os.makedirs(IMAGE_DIR, exist_ok=True)

    if prefetched_first_html is None:
        tqdm.write("Fetching page 1...")
        first_html = fetch(LIST_URL + "1")
        time.sleep(DELAY)
    else:
        first_html = prefetched_first_html

    total_pages = get_total_pages(first_html)

    if end_page is None:
        end_page = total_pages

    total_pages_to_scrape = end_page - start_page + 1
    tqdm.write(
        f"Scraping pages {start_page} to {end_page} ({total_pages_to_scrape} pages) {'[DRY RUN]' if dry_run else ''}\n"
    )

    stats = {"scraped": 0, "inserted": 0, "errors": 0}

    with tqdm(total=total_pages_to_scrape, desc="Pages", unit="page") as page_bar:
        for page_num in range(start_page, end_page + 1):
            try:
                if page_num == 1:
                    page_html = first_html
                else:
                    page_html = fetch(LIST_URL + str(page_num))
                    time.sleep(DELAY)
            except Exception as e:
                tqdm.write(f"[PAGE FAIL] page {page_num}: {e}")
                page_bar.update(1)
                continue

            list_rows = parse_list_rows(page_html)

            with tqdm(
                total=len(list_rows), desc=f"  Page {page_num}", unit="row", leave=False
            ) as row_bar:
                for list_row in list_rows:
                    stats["scraped"] += 1
                    detail_path = list_row.pop("detail_path")

                    try:
                        if not dry_run:
                            row_id = insert_stub(list_row)

                        encoded = encode_thai(detail_path)
                        detail_url = f"{BASE_URL}/{encoded}"
                        detail_html = fetch(detail_url)
                        time.sleep(DELAY)

                        data = parse_detail(detail_html)
                        data.update({k: v for k, v in list_row.items() if v})

                        if not dry_run:
                            images = data.get("images", [])
                            if images:
                                local_path = download_image(
                                    images[0], data.get("deed_number", "unknown")
                                )
                                data["images"] = [local_path] + images[1:]
                                time.sleep(DELAY)
                            update_full(row_id, data)
                            stats["inserted"] += 1
                        else:
                            tqdm.write(
                                f"  [DRY] case={list_row.get('case_number')} province={list_row.get('province')}"
                            )

                    except Exception as e:
                        tqdm.write(f"  [ROW FAIL] {detail_path}: {e}")
                        stats["errors"] += 1

                    row_bar.update(1)

            page_bar.update(1)

    print(f"\nDone.")
    print(f"  Scraped : {stats['scraped']}")
    if not dry_run:
        print(f"  Inserted: {stats['inserted']}")
    print(f"  Errors  : {stats['errors']}")


if __name__ == "__main__":
    print("Connecting to asset.led.go.th...")
    try:
        first_html = fetch(LIST_URL + "1")
    except Exception as e:
        print(f"Failed to connect: {e}")
        exit(1)

    total_pages = get_total_pages(first_html)
    print(f"Found {total_pages} pages available.\n")

    start_input = input(f"Start page [1-{total_pages}, default=1]: ").strip()
    start = int(start_input) if start_input else 1

    end_input = input(f"End page [{start}-{total_pages}, default=all]: ").strip()
    end = int(end_input) if end_input else None

    dry_input = input("Dry run? [y/N]: ").strip().lower()
    dry = dry_input == "y"

    scrape(start, end, dry, prefetched_first_html=first_html)
