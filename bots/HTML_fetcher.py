import sys
import requests
from datetime import datetime
from urllib.parse import quote

url = sys.argv[1]


# re-encode any Thai in the URL
def encode_thai_url(url):
    from urllib.parse import urlsplit, urlencode, parse_qsl

    parts = urlsplit(url)
    qs = parse_qsl(parts.query, encoding="cp874", errors="replace")
    new_qs = urlencode([(k, v) for k, v in qs], encoding="cp874")
    return parts._replace(query=new_qs).geturl()


encoded_url = encode_thai_url(url)
r = requests.get(encoded_url, timeout=20)
html = r.content.decode("cp874")

filename = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
with open(filename, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Saved to {filename}")
