import os
import sqlite3
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.environ.get(
    "SCRAPER_DB_PATH",
    os.path.join(ROOT_DIR, "DB", "properties.db"),
)
SCHEMA_PATH = os.path.join(ROOT_DIR, "schema.sql")

LISTING_FIELDS = (
    "detail_path",
    "asset_sequence",
    "case_number",
    "asset_type",
    "rai",
    "ngan",
    "sqwah",
    "appraisal_officer",
    "tambon",
    "amphoe",
    "province",
)

DETAIL_FIELDS = (
    "deed_number",
    "court",
    "office",
    "phone",
    "venue",
    "case_officer",
    "plaintiff",
    "defendant",
    "land_area",
    "owner_name",
    "sale_condition",
    "deposit_amount",
    "appraisal_expert",
    "appraisal_officer",
    "appraisal_dept",
    "appraisal_committee",
    "published_date",
    "remarks",
    "auction_date_1",
    "auction_status_1",
    "auction_date_2",
    "auction_status_2",
    "auction_date_3",
    "auction_status_3",
    "auction_date_4",
    "auction_status_4",
    "auction_date_5",
    "auction_status_5",
    "auction_date_6",
    "auction_status_6",
    "auction_date_7",
    "auction_status_7",
    "auction_date_8",
    "auction_status_8",
    "image_1",
    "image_2",
    "image_3",
)


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _load_schema():
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema.sql not found at: {SCHEMA_PATH}")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _table_sql(conn, table_name):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row[0] if row else None


def _needs_properties_migration(conn):
    table_sql = _table_sql(conn, "properties")
    if not table_sql:
        return False

    normalized = "".join(table_sql.upper().split())
    return "DETAIL_PATH" not in normalized or "UNIQUE(DETAIL_PATH)" not in normalized


def _migrate_properties_table(conn, schema_sql):
    conn.execute("ALTER TABLE properties RENAME TO properties_old")
    conn.executescript(schema_sql)

    new_columns = [row[1] for row in conn.execute("PRAGMA table_info(properties)")]
    old_columns = {row[1] for row in conn.execute("PRAGMA table_info(properties_old)")}
    common_columns = [column for column in new_columns if column in old_columns]

    columns_sql = ", ".join(common_columns)
    conn.execute(
        f"INSERT OR IGNORE INTO properties ({columns_sql}) "
        f"SELECT {columns_sql} FROM properties_old"
    )
    conn.execute("DROP TABLE properties_old")


def _ensure_columns(conn):
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(properties)")}
    for column_name in ("phone", "venue", "case_officer"):
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE properties ADD COLUMN {column_name} TEXT")


def init_db():
    schema_sql = _load_schema()
    conn = get_conn()
    try:
        if _needs_properties_migration(conn):
            _migrate_properties_table(conn, schema_sql)
        else:
            conn.executescript(schema_sql)

        _ensure_columns(conn)
        conn.commit()
    finally:
        conn.close()


def insert_stub(row: dict) -> tuple[int, bool]:
    detail_path = row.get("detail_path", "").strip()
    case_number = row.get("case_number", "").strip()
    asset_sequence = row.get("asset_sequence", "").strip()

    if not detail_path:
        raise ValueError("detail_path is required")

    data = {field: row.get(field, "") for field in LISTING_FIELDS}
    data["detail_path"] = detail_path
    data["case_number"] = case_number
    data["asset_sequence"] = asset_sequence
    data["scraped_at"] = datetime.now().isoformat()

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM properties WHERE detail_path = ?",
            (detail_path,),
        ).fetchone()

        if existing:
            row_id = existing[0]
            updates = {
                key: value for key, value in data.items() if key != "detail_path"
            }
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE properties SET {set_clause} WHERE id = ?",
                [*updates.values(), row_id],
            )
            conn.commit()
            return row_id, False

        columns_sql = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        cur = conn.execute(
            f"INSERT INTO properties ({columns_sql}) VALUES ({placeholders})",
            list(data.values()),
        )
        conn.commit()
        return cur.lastrowid, True
    finally:
        conn.close()


def update_full(row_id: int, data: dict) -> None:
    updates = {field: data.get(field, "") for field in DETAIL_FIELDS}
    updates["scraped_at"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{key} = ?" for key in updates)
    sql = f"UPDATE properties SET {set_clause} WHERE id = ?"

    conn = get_conn()
    try:
        conn.execute(sql, [*updates.values(), row_id])
        conn.commit()
    finally:
        conn.close()
