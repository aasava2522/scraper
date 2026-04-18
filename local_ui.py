import argparse
import html
import mimetypes
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from math import ceil
from urllib.parse import parse_qs, quote_from_bytes, urlencode, urlparse

from bots.db import DB_PATH, init_db

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_URL = "https://asset.led.go.th/newbid-old"
REMOTE_HOST = "https://asset.led.go.th"
PAGE_SIZE = 25

LIST_COLUMNS = (
    "id",
    "asset_sequence",
    "case_number",
    "deed_number",
    "asset_type",
    "province",
    "amphoe",
    "tambon",
    "appraisal_officer",
    "auction_date_1",
    "image_1",
)

DETAIL_FIELDS = (
    ("ลำดับทรัพย์", "asset_sequence"),
    ("เลขที่คดี", "case_number"),
    ("โฉนดเลขที่", "deed_number"),
    ("ประเภททรัพย์", "asset_type"),
    ("ตำบล", "tambon"),
    ("อำเภอ", "amphoe"),
    ("จังหวัด", "province"),
    ("เนื้อที่", "land_area"),
    ("ไร่", "rai"),
    ("งาน", "ngan"),
    ("ตร.วา", "sqwah"),
    ("ผู้ถือกรรมสิทธิ์", "owner_name"),
    ("ศาล", "court"),
    ("สำนักงาน", "office"),
    ("โทรศัพท์", "phone"),
    ("สถานที่จำหน่าย", "venue"),
    ("เจ้าของสำนวน", "case_officer"),
    ("โจทก์", "plaintiff"),
    ("จำเลย", "defendant"),
    ("เงื่อนไขผู้เข้าสู้ราคา", "deposit_amount"),
    ("การขาย", "sale_condition"),
    ("ราคาประเมินเจ้าพนักงาน", "appraisal_officer"),
    ("ราคาประเมินผู้เชี่ยวชาญ", "appraisal_expert"),
    ("ราคาประเมินกรม", "appraisal_dept"),
    ("ราคาคณะกรรมการ", "appraisal_committee"),
    ("วันที่ประกาศขึ้นเว็บ", "published_date"),
    ("หมายเหตุ", "remarks"),
)


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def encode_led_path(path):
    try:
        return quote_from_bytes(path.encode("cp874"), safe="/:?=&.-_")
    except UnicodeEncodeError:
        return quote_from_bytes(path.encode("utf-8"), safe="/:?=&.-_")


def escape(value):
    return html.escape("" if value is None else str(value))


def row_text(row, key):
    return str(row[key]).strip() if row[key] is not None else ""


def image_src(value):
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if os.path.isabs(value):
        local_path = os.path.abspath(value)
        if local_path.startswith(ROOT_DIR) and os.path.exists(local_path):
            return f"/file?{urlencode({'path': local_path})}"
        return None
    if value.startswith("/"):
        return f"{REMOTE_HOST}{encode_led_path(value)}"
    return None


def source_url(detail_path):
    detail_path = (detail_path or "").strip()
    if not detail_path:
        return None
    return f"{BASE_URL}/{encode_led_path(detail_path)}"


def build_filters(params):
    clauses = []
    values = []

    q = params.get("q", "").strip()
    province = params.get("province", "").strip()
    asset_type = params.get("asset_type", "").strip()

    if q:
        like = f"%{q}%"
        clauses.append(
            "("
            "case_number LIKE ? OR deed_number LIKE ? OR owner_name LIKE ? OR "
            "tambon LIKE ? OR amphoe LIKE ? OR province LIKE ? OR asset_type LIKE ?"
            ")"
        )
        values.extend([like] * 7)

    if province:
        clauses.append("province = ?")
        values.append(province)

    if asset_type:
        clauses.append("asset_type = ?")
        values.append(asset_type)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, values


def fetch_filter_options(conn):
    provinces = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT province FROM properties "
            "WHERE province IS NOT NULL AND TRIM(province) <> '' ORDER BY province"
        )
    ]
    asset_types = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT asset_type FROM properties "
            "WHERE asset_type IS NOT NULL AND TRIM(asset_type) <> '' ORDER BY asset_type"
        )
    ]
    return provinces, asset_types


def list_properties(params):
    try:
        page = int(params.get("page", "1") or "1")
    except ValueError:
        page = 1
    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    where_sql, values = build_filters(params)

    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM properties {where_sql}",
            values,
        ).fetchone()[0]

        query = (
            f"SELECT {', '.join(LIST_COLUMNS)} FROM properties {where_sql} "
            "ORDER BY id DESC LIMIT ? OFFSET ?"
        )
        rows = conn.execute(query, [*values, PAGE_SIZE, offset]).fetchall()
        provinces, asset_types = fetch_filter_options(conn)
    finally:
        conn.close()

    return page, total, rows, provinces, asset_types


def get_property(property_id):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM properties WHERE id = ?",
            (property_id,),
        ).fetchone()
    finally:
        conn.close()
    return row


def ensure_indexes():
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_properties_case_number
            ON properties(case_number);
            CREATE INDEX IF NOT EXISTS idx_properties_deed_number
            ON properties(deed_number);
            CREATE INDEX IF NOT EXISTS idx_properties_province
            ON properties(province);
            CREATE INDEX IF NOT EXISTS idx_properties_asset_type
            ON properties(asset_type);
            CREATE INDEX IF NOT EXISTS idx_properties_published_date
            ON properties(published_date);
            """
        )
        conn.commit()
    finally:
        conn.close()


def option_html(values, selected_value):
    options = ['<option value="">ทั้งหมด</option>']
    for value in values:
        selected = " selected" if value == selected_value else ""
        options.append(
            f'<option value="{escape(value)}"{selected}>{escape(value)}</option>'
        )
    return "".join(options)


def build_query(params, **updates):
    merged = {k: v for k, v in params.items() if v}
    for key, value in updates.items():
        if value in (None, "", 0):
            merged.pop(key, None)
        else:
            merged[key] = str(value)
    query = urlencode(merged)
    return f"?{query}" if query else ""


def pagination_html(page, total, params):
    total_pages = max(1, ceil(total / PAGE_SIZE)) if total else 1
    if total_pages <= 1:
        return ""

    links = []
    if page > 1:
        links.append(f'<a href="/{build_query(params, page=page - 1)}">ก่อนหน้า</a>')

    start = max(1, page - 2)
    end = min(total_pages, page + 2)
    for num in range(start, end + 1):
        if num == page:
            links.append(f"<strong>{num}</strong>")
        else:
            links.append(f'<a href="/{build_query(params, page=num)}">{num}</a>')

    if page < total_pages:
        links.append(f'<a href="/{build_query(params, page=page + 1)}">ถัดไป</a>')

    return (
        '<div class="pager">'
        f'<span>หน้า {page}/{total_pages}</span>'
        + "".join(f"<span>{link}</span>" for link in links)
        + "</div>"
    )


def render_list_page(params):
    page, total, rows, provinces, asset_types = list_properties(params)
    back_param = "/" + build_query(params, page=page)

    table_rows = []
    for row in rows:
        location = " / ".join(
            escape(part)
            for part in (row["tambon"], row["amphoe"], row["province"])
            if part
        )
        summary = " ".join(
            part
            for part in [row["asset_type"], f"โฉนด {row['deed_number']}" if row["deed_number"] else ""]
            if part
        )
        detail_href = f"/property?{urlencode({'id': row['id'], 'back': back_param})}"
        table_rows.append(
            "<tr>"
            f'<td><a href="{detail_href}">{escape(row["asset_sequence"]) or "-"}</a></td>'
            f"<td>{escape(row['case_number']) or '-'}</td>"
            f"<td>{escape(summary) or '-'}</td>"
            f"<td>{location or '-'}</td>"
            f"<td>{escape(row['appraisal_officer']) or '-'}</td>"
            f"<td>{escape(row['auction_date_1']) or '-'}</td>"
            "</tr>"
        )

    if not table_rows:
        table_rows.append(
            '<tr><td colspan="6" class="empty">ไม่พบข้อมูลตามเงื่อนไขที่เลือก</td></tr>'
        )

    content = f"""
    <div class="hero">
      <div>
        <div class="eyebrow">LED Mirror</div>
        <h1>ค้นหาทรัพย์ในฐานข้อมูลท้องถิ่น</h1>
        <p>อ่านจาก SQLite ในเครื่องโดยตรง ข้อมูลที่เห็นจะมีเท่าที่ถูก scrape ลงฐานแล้วเท่านั้น</p>
      </div>
      <div class="stats">
        <div><strong>{total}</strong><span>รายการที่ตรงเงื่อนไข</span></div>
        <div><strong>{PAGE_SIZE}</strong><span>รายการต่อหน้า</span></div>
      </div>
    </div>

    <form class="search-card" method="get" action="/">
      <label>
        <span>ค้นหา</span>
        <input type="text" name="q" value="{escape(params.get('q', ''))}" placeholder="คดี / โฉนด / เจ้าของ / จังหวัด">
      </label>
      <label>
        <span>จังหวัด</span>
        <select name="province">{option_html(provinces, params.get('province', ''))}</select>
      </label>
      <label>
        <span>ประเภททรัพย์</span>
        <select name="asset_type">{option_html(asset_types, params.get('asset_type', ''))}</select>
      </label>
      <div class="actions">
        <button type="submit">ค้นหา</button>
        <a class="reset" href="/">ล้างค่า</a>
      </div>
    </form>

    {pagination_html(page, total, params)}

    <div class="table-wrap">
      <table class="results">
        <thead>
          <tr>
            <th>ลำดับ</th>
            <th>เลขคดี</th>
            <th>ทรัพย์</th>
            <th>ที่ตั้ง</th>
            <th>ราคาประเมิน</th>
            <th>นัดแรก</th>
          </tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </div>

    {pagination_html(page, total, params)}
    """
    return page_template("รายการทรัพย์", content)


def auction_rows(row):
    rows = []
    for index in range(1, 9):
        date_value = row_text(row, f"auction_date_{index}")
        status_value = row_text(row, f"auction_status_{index}")
        if not date_value and not status_value:
            continue
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(date_value) or '-'}</td>"
            f"<td>{escape(status_value) or '-'}</td>"
            "</tr>"
        )
    return rows


def render_detail_page(property_id, back_path):
    row = get_property(property_id)
    if not row:
        return page_template("ไม่พบข้อมูล", '<p class="empty">ไม่พบรายการที่ต้องการ</p>'), 404

    info_rows = []
    for label, key in DETAIL_FIELDS:
        value = row_text(row, key)
        if value:
            info_rows.append(
                f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
            )

    images = []
    for key in ("image_1", "image_2", "image_3"):
        src = image_src(row[key])
        if src:
            images.append(
                '<a class="image-card" href="{src}" target="_blank" rel="noreferrer">'
                '<img src="{src}" alt="{alt}"></a>'.format(
                    src=escape(src),
                    alt=escape(f"image-{key}"),
                )
            )

    auction_html = "".join(auction_rows(row))
    source_link = source_url(row["detail_path"])
    source_html = (
        f'<a class="source-link" href="{escape(source_link)}" target="_blank" rel="noreferrer">เปิดหน้าต้นทาง</a>'
        if source_link
        else ""
    )

    content = f"""
    <div class="detail-head">
      <div>
        <a class="back-link" href="{escape(back_path or '/')}">กลับไปหน้ารายการ</a>
        <h1>{escape(row['asset_type']) or 'รายละเอียดทรัพย์'}</h1>
        <p>{escape(row['case_number']) or '-'} | {escape(row['asset_sequence']) or '-'}</p>
      </div>
      <div class="detail-actions">{source_html}</div>
    </div>

    <div class="detail-grid">
      <section class="panel">
        <h2>รายละเอียด</h2>
        <table class="detail-table">
          <tbody>{''.join(info_rows) or '<tr><td class="empty">ไม่มีข้อมูล</td></tr>'}</tbody>
        </table>
      </section>

      <section class="panel">
        <h2>รูปภาพ</h2>
        <div class="images">{''.join(images) or '<div class="empty">ไม่มีรูปภาพ</div>'}</div>
      </section>
    </div>

    <section class="panel">
      <h2>ตารางนัดขาย</h2>
      <table class="results compact">
        <thead><tr><th>นัด</th><th>วันที่</th><th>สถานะ</th></tr></thead>
        <tbody>{auction_html or '<tr><td colspan="3" class="empty">ไม่มีข้อมูลนัดขาย</td></tr>'}</tbody>
      </table>
    </section>
    """
    return page_template("รายละเอียดทรัพย์", content), 200


def page_template(title, content):
    return f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --blue: #152a7c;
      --blue-dark: #0f1c57;
      --gold: #f3c84b;
      --paper: #fffdf6;
      --line: #d9d3c4;
      --text: #1c2230;
      --muted: #61697a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Tahoma, "Noto Sans Thai", sans-serif;
      color: var(--text);
      background:
        linear-gradient(180deg, rgba(21,42,124,0.08), rgba(21,42,124,0) 260px),
        linear-gradient(135deg, #fffefb, #f7f1de);
    }}
    .shell {{
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }}
    .masthead {{
      background: linear-gradient(135deg, var(--blue), var(--blue-dark));
      color: white;
      border: 4px solid var(--gold);
      padding: 18px 22px;
      box-shadow: 0 14px 28px rgba(16, 28, 84, 0.18);
    }}
    .masthead h1 {{
      margin: 0;
      font-size: 24px;
    }}
    .masthead p {{
      margin: 6px 0 0;
      color: rgba(255,255,255,0.88);
      font-size: 14px;
    }}
    .hero, .search-card, .panel, .table-wrap {{
      background: rgba(255,255,255,0.92);
      border: 1px solid var(--line);
      box-shadow: 0 10px 24px rgba(27, 34, 48, 0.07);
    }}
    .hero {{
      margin-top: 18px;
      padding: 18px 20px;
      display: grid;
      gap: 16px;
      grid-template-columns: 1.6fr 0.9fr;
      align-items: start;
    }}
    .hero h1, .detail-head h1 {{
      margin: 0;
      font-size: 26px;
      line-height: 1.15;
    }}
    .hero p, .detail-head p {{
      margin: 8px 0 0;
      color: var(--muted);
    }}
    .eyebrow {{
      color: var(--blue);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .stats {{
      display: grid;
      gap: 12px;
    }}
    .stats div {{
      padding: 14px 16px;
      background: var(--paper);
      border-left: 5px solid var(--gold);
    }}
    .stats strong {{
      display: block;
      font-size: 28px;
    }}
    .stats span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .search-card {{
      margin-top: 16px;
      padding: 16px;
      display: grid;
      gap: 14px;
      grid-template-columns: 2fr 1fr 1fr auto;
      align-items: end;
    }}
    label span, .panel h2 {{
      display: block;
      font-size: 13px;
      font-weight: 700;
      color: var(--blue);
      margin-bottom: 6px;
    }}
    input, select, button {{
      font: inherit;
    }}
    input, select {{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #bfc7d9;
      background: white;
    }}
    button, .reset, .source-link, .back-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      border: 0;
      text-decoration: none;
      cursor: pointer;
    }}
    button {{
      background: var(--blue);
      color: white;
      padding: 10px 16px;
      font-weight: 700;
    }}
    .reset, .source-link, .back-link {{
      color: var(--blue);
      font-weight: 700;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    .pager {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin: 16px 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .pager a {{
      text-decoration: none;
      color: var(--blue);
      font-weight: 700;
    }}
    .table-wrap, .panel {{
      padding: 0;
      overflow: hidden;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid #ece7d8;
      vertical-align: top;
      text-align: left;
    }}
    thead th {{
      background: #f2f5ff;
      color: var(--blue-dark);
      font-size: 13px;
    }}
    tbody tr:hover {{
      background: #fffbea;
    }}
    td a {{
      color: var(--blue);
      font-weight: 700;
      text-decoration: none;
    }}
    .empty {{
      text-align: center;
      color: var(--muted);
      padding: 24px;
    }}
    .detail-head {{
      margin: 18px 0 14px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }}
    .detail-grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: 1.3fr 0.9fr;
      margin-bottom: 18px;
    }}
    .panel {{
      padding: 16px 18px;
    }}
    .detail-table th {{
      width: 200px;
      color: var(--blue-dark);
      background: #fbfcff;
    }}
    .images {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }}
    .image-card {{
      display: block;
      background: var(--paper);
      border: 1px solid var(--line);
      padding: 8px;
    }}
    .image-card img {{
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      display: block;
    }}
    .compact th, .compact td {{
      padding: 10px 12px;
    }}
    @media (max-width: 860px) {{
      .hero, .search-card, .detail-grid {{
        grid-template-columns: 1fr;
      }}
      .detail-head {{
        flex-direction: column;
      }}
      .shell {{
        width: min(100vw - 20px, 1120px);
      }}
      th, td {{
        padding: 10px 11px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="masthead">
      <h1>Local LED Property Viewer</h1>
      <p>Read-only mirror over <code>{escape(DB_PATH)}</code></p>
    </header>
    {content}
  </div>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request(send_body=True)

    def do_HEAD(self):
        self.handle_request(send_body=False)

    def handle_request(self, send_body):
        parsed = urlparse(self.path)
        params = {k: v[-1] for k, v in parse_qs(parsed.query).items()}

        if parsed.path == "/":
            self.respond_html(render_list_page(params), send_body=send_body)
            return

        if parsed.path == "/property":
            property_id = params.get("id", "").strip()
            if not property_id.isdigit():
                self.respond_html(
                    page_template("ไม่พบข้อมูล", '<p class="empty">id ไม่ถูกต้อง</p>'),
                    400,
                    send_body=send_body,
                )
                return
            back_path = params.get("back", "/") or "/"
            body, status = render_detail_page(int(property_id), back_path)
            self.respond_html(body, status, send_body=send_body)
            return

        if parsed.path == "/file":
            self.serve_file(params.get("path", ""), send_body=send_body)
            return

        self.respond_html(
            page_template("ไม่พบหน้า", '<p class="empty">ไม่พบหน้าที่ต้องการ</p>'),
            404,
            send_body=send_body,
        )

    def serve_file(self, raw_path, send_body=True):
        if not raw_path:
            self.send_error(404)
            return

        real_path = os.path.abspath(raw_path)
        if not real_path.startswith(ROOT_DIR) or not os.path.isfile(real_path):
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(real_path)[0] or "application/octet-stream"
        with open(real_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def respond_html(self, body, status=200, send_body=True):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Local viewer for properties.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    init_db()
    ensure_indexes()

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Serving on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
