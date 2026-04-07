from bs4 import BeautifulSoup
import re

FIELD_MAP = [
    ("ตามสำเนาโฉนดเลขที่", "deed_number"),
    ("โฉนดเลขที่", "deed_number"),
    ("แขวง/ตำบล", "tambon"),
    ("เขต/อำเภอ", "amphoe"),
    ("จังหวัด", "province"),
    ("เนื้อที่", "land_area"),
    ("มีชื่อ", "owner_name"),
    ("ประเภททรัพย์", "asset_type"),
    ("เลขที่", "unit_number"),
    ("ศาล", "court"),
    ("คดีหมายเลขแดงที่", "case_number"),
    ("เงื่อนไขผู้เข้าสู้ราคา", "deposit_amount"),
    ("จะทำการขายโดย", "sale_condition"),
    ("ราคาประเมินของผู้เชี่ยวชาญ", "appraisal_expert"),
    ("ราคาประเมินของเจ้าพนักงานบังคับคดี", "appraisal_officer"),
    ("ราคาประเมินของเจ้าพนักงานประเมิน", "appraisal_dept"),
    ("ราคาที่กำหนดโดยคณะกรรมการ", "appraisal_committee"),
    ("วันที่ประกาศขึ้นเว็บ", "published_date"),
    ("หมายเหตุ", "remarks"),
]

DATE_LABEL = "นัดที่"


def parse_land_size(td):
    children = list(td.children)
    if not children:
        return None
    first = next((c for c in children if str(c).strip()), None)
    if first is None:
        return None
    if not (
        hasattr(first, "name")
        and first.name == "font"
        and first.get("color") == "#FF0000"
    ):
        return None
    plain = "".join(
        str(c)
        for c in children
        if not (hasattr(c, "name") and c.name == "font" and c.get("color") == "#FF0000")
    )
    if "ไร่" not in plain or "งาน" not in plain:
        return None
    reds = [f.get_text(strip=True) for f in td.find_all("font", color="#FF0000")]
    if len(reds) < 3:
        return None
    return {"rai": reds[0], "ngan": reds[1], "sqwah": reds[2]}


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")

    def td_label_value(td):
        red = td.find("font", color="#FF0000")
        if not red:
            return None, None
        label = ""
        for node in td.children:
            if node == red:
                break
            if hasattr(node, "get_text"):
                label += node.get_text(" ", strip=True)
            else:
                label += str(node).strip()
        return label.strip(), red.get_text(" ", strip=True).strip()

    raw = {}
    auction_dates = {}
    land_size = None

    for td in soup.find_all("td"):
        size = parse_land_size(td)
        if size and land_size is None:
            land_size = size
            continue

        label, value = td_label_value(td)
        if not label or not value:
            continue

        # Auction date rows
        if (
            label.startswith(DATE_LABEL)
            and "\xa0" in label
            and label.count(DATE_LABEL) == 1
        ):
            m = re.search(r"นัดที่\s*(\d+)", label)
            if m:
                round_num = int(m.group(1))
                next_td = td.find_next_sibling("td")
                status = next_td.get_text(strip=True) if next_td else ""
                auction_dates[round_num] = {"date": value, "status": status}
            continue

        label = re.sub(r"\s+", " ", label).strip()
        if len(label) > 100:
            continue
        raw[label] = value

    result = {}

    # asset_sequence from blue font
    blue = soup.find("font", color="#0000FF")
    if blue:
        result["asset_sequence"] = blue.get_text(strip=True)

    # plaintiff and defendant
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if text in ("โจทก์", "จำเลย"):
            prev = td.find_previous_sibling("td")
            if prev:
                red = prev.find("font", color="#FF0000")
                if red:
                    key = "plaintiff" if text == "โจทก์" else "defendant"
                    result[key] = red.get_text(strip=True)

    # office and phone — in same td, split by โทร
    for td in soup.find_all("td"):
        text = td.get_text(" ", strip=True)
        if "(สำนักงานบังคับคดี" in text or "สำนักงานบังคับคดีจังหวัด" in text:
            reds = td.find_all("font", color="#FF0000")
            if len(reds) >= 1:
                result["office"] = reds[0].get_text(strip=True)
            if len(reds) >= 2:
                result["phone"] = reds[1].get_text(strip=True)
            break

    # venue — สถานที่จำหน่าย, text after <strong> tag
    for td in soup.find_all("td"):
        strong = td.find("strong")
        if strong and "สถานที่จำหน่าย" in strong.get_text():
            # get all text after the strong tag
            parts = []
            for node in td.children:
                if node == strong:
                    continue
                if hasattr(node, "get_text"):
                    parts.append(node.get_text(" ", strip=True))
                else:
                    parts.append(str(node).strip())
            venue = " ".join(p for p in parts if p).strip()
            if venue:
                result["venue"] = venue
            break

    # case_officer — เจ้าของสำนวน
    for td in soup.find_all("td"):
        text = td.get_text(" ", strip=True)
        if "เจ้าของสำนวน" in text:
            red = td.find("font", color="#FF0000")
            if red:
                result["case_officer"] = red.get_text(strip=True)
            break

    # map FIELD_MAP
    for thai_label, eng_key in FIELD_MAP:
        for raw_label, value in raw.items():
            if thai_label in raw_label:
                result[eng_key] = value
                break

    if land_size:
        result["rai"] = land_size["rai"]
        result["ngan"] = land_size["ngan"]
        result["sqwah"] = land_size["sqwah"]

    result["auction_dates"] = [
        {
            "round": k,
            "date": auction_dates[k]["date"],
            "status": auction_dates[k]["status"],
        }
        for k in sorted(auction_dates)
    ]

    # flatten auction dates into result
    for entry in result["auction_dates"]:
        r = entry["round"]
        if 1 <= r <= 8:
            result[f"auction_date_{r}"] = entry["date"]
            result[f"auction_status_{r}"] = entry["status"]

    return result


if __name__ == "__main__":
    import sys

    html = open(sys.argv[1], "r", encoding="utf-8").read()
    data = parse_detail(html)
    for k, v in data.items():
        print(f"  {k}: {v!r}")
