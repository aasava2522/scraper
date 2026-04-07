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


def insert_listing(row: dict):
    data = {
        "case_number": row.get("case_number"),
        "asset_sequence": row.get("asset_sequence"),
        "asset_type": row.get("asset_type"),
        "rai": row.get("rai"),
        "ngan": row.get("ngan"),
        "sqwah": row.get("sqwah"),
        "appraisal_price": row.get("appraisal_price"),
        "tambon": row.get("tambon"),
        "amphoe": row.get("amphoe"),
        "province": row.get("province"),
        "scraped_at": datetime.now().isoformat(),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    sql = f"INSERT OR REPLACE INTO listings ({cols}) VALUES ({placeholders})"
    conn = get_conn()
    conn.execute(sql, list(data.values()))
    conn.commit()
    conn.close()


def upsert_detail(row: dict):
    data = {
        "case_number": row.get("case_number"),
        "unit_number": row.get("unit_number"),
        "deed_number": row.get("deed_number"),
        "tambon": row.get("tambon"),
        "amphoe": row.get("amphoe"),
        "province": row.get("province"),
        "rai": row.get("rai"),
        "ngan": row.get("ngan"),
        "sqwah": row.get("sqwah"),
        "owner_name": row.get("owner_name"),
        "asset_type": row.get("asset_type"),
        "court": row.get("court"),
        "plaintiff": row.get("plaintiff"),
        "defendant": row.get("defendant"),
        "office": row.get("office"),
        "phone": row.get("phone"),
        "venue": row.get("venue"),
        "case_officer": row.get("case_officer"),
        "deposit_amount": row.get("deposit_amount"),
        "sale_condition": row.get("sale_condition"),
        "appraisal_expert": row.get("appraisal_expert"),
        "appraisal_officer": row.get("appraisal_officer"),
        "appraisal_dept": row.get("appraisal_dept"),
        "appraisal_committee": row.get("appraisal_committee"),
        "published_date": row.get("published_date"),
        "remarks": row.get("remarks"),
        "scraped_at": datetime.now().isoformat(),
    }

    for i in range(1, 9):
        data[f"auction_date_{i}"] = row.get(f"auction_date_{i}")
        data[f"auction_status_{i}"] = row.get(f"auction_status_{i}")

    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    sql = f"INSERT OR REPLACE INTO details ({cols}) VALUES ({placeholders})"
    conn = get_conn()
    conn.execute(sql, list(data.values()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("DB initialized.")
