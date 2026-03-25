import sqlite3
from datetime import datetime

DB_PATH = "/mnt/0CDCB75BDCB73E30/scraperBots/properties.db"
SCHEMA_PATH = "/mnt/0CDCB75BDCB73E30/scraperBots/schema.sql"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open(SCHEMA_PATH, "r") as f:
        sql = f.read()
    conn = get_conn()
    conn.executescript(sql)
    conn.commit()
    conn.close()


def insert_stub(list_row: dict) -> int:
    """Insert list-level data immediately. Returns the new row id."""
    row = {
        "asset_sequence": list_row.get("asset_sequence"),
        "case_number": list_row.get("case_number"),
        "asset_type": list_row.get("asset_type"),
        "rai": list_row.get("rai"),
        "ngan": list_row.get("ngan"),
        "sqwah": list_row.get("sqwah"),
        "appraisal_officer": list_row.get("appraisal_officer"),
        "tambon": list_row.get("tambon"),
        "amphoe": list_row.get("amphoe"),
        "province": list_row.get("province"),
        "scraped_at": datetime.now().isoformat(),
    }
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    sql = f"INSERT INTO properties ({cols}) VALUES ({placeholders})"
    conn = get_conn()
    cur = conn.execute(sql, list(row.values()))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_full(row_id: int, data: dict):
    """Update a stub row with full detail page data."""
    row = {
        "asset_sequence": data.get("asset_sequence"),
        "deed_number": data.get("deed_number"),
        "case_number": data.get("case_number"),
        "court": data.get("court"),
        "office": data.get("office"),
        "plaintiff": data.get("plaintiff"),
        "defendant": data.get("defendant"),
        "asset_type": data.get("asset_type"),
        "tambon": data.get("tambon"),
        "amphoe": data.get("amphoe"),
        "province": data.get("province"),
        "land_area": data.get("land_area"),
        "rai": data.get("rai"),
        "ngan": data.get("ngan"),
        "sqwah": data.get("sqwah"),
        "owner_name": data.get("owner_name"),
        "sale_condition": data.get("sale_condition"),
        "deposit_amount": data.get("deposit_amount"),
        "appraisal_expert": data.get("appraisal_expert"),
        "appraisal_officer": data.get("appraisal_officer"),
        "appraisal_dept": data.get("appraisal_dept"),
        "appraisal_committee": data.get("appraisal_committee"),
        "published_date": data.get("published_date"),
        "remarks": data.get("remarks"),
        "scraped_at": datetime.now().isoformat(),
    }

    # Auction dates
    for entry in data.get("auction_dates", []):
        r = entry["round"]
        if 1 <= r <= 8:
            row[f"auction_date_{r}"] = entry["date"]
            row[f"auction_status_{r}"] = entry["status"]

    # Images
    images = data.get("images", [])
    for i in range(1, 4):
        row[f"image_{i}"] = images[i - 1] if i <= len(images) else None

    set_clause = ", ".join(f"{k} = ?" for k in row)
    sql = f"UPDATE properties SET {set_clause} WHERE id = ?"
    conn = get_conn()
    conn.execute(sql, list(row.values()) + [row_id])
    conn.commit()
    conn.close()


def upsert(data: dict):
    """Legacy upsert — kept for compatibility."""
    from datetime import datetime

    row = {
        "asset_sequence": data.get("asset_sequence"),
        "deed_number": data.get("deed_number"),
        "case_number": data.get("case_number"),
        "court": data.get("court"),
        "office": data.get("office"),
        "plaintiff": data.get("plaintiff"),
        "defendant": data.get("defendant"),
        "asset_type": data.get("asset_type"),
        "tambon": data.get("tambon"),
        "amphoe": data.get("amphoe"),
        "province": data.get("province"),
        "land_area": data.get("land_area"),
        "rai": data.get("rai"),
        "ngan": data.get("ngan"),
        "sqwah": data.get("sqwah"),
        "owner_name": data.get("owner_name"),
        "sale_condition": data.get("sale_condition"),
        "deposit_amount": data.get("deposit_amount"),
        "appraisal_expert": data.get("appraisal_expert"),
        "appraisal_officer": data.get("appraisal_officer"),
        "appraisal_dept": data.get("appraisal_dept"),
        "appraisal_committee": data.get("appraisal_committee"),
        "published_date": data.get("published_date"),
        "remarks": data.get("remarks"),
        "scraped_at": datetime.now().isoformat(),
    }
    for entry in data.get("auction_dates", []):
        r = entry["round"]
        if 1 <= r <= 8:
            row[f"auction_date_{r}"] = entry["date"]
            row[f"auction_status_{r}"] = entry["status"]
    images = data.get("images", [])
    for i in range(1, 4):
        row[f"image_{i}"] = images[i - 1] if i <= len(images) else None

    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    sql = f"INSERT OR REPLACE INTO properties ({cols}) VALUES ({placeholders})"
    conn = get_conn()
    conn.execute(sql, list(row.values()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("DB initialized.")
