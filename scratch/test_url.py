import httpx
import urllib.parse

uri = "duckdb://jaffle_shop/raw_customers"
encoded_uri = urllib.parse.quote(uri, safe="")
url = f"http://localhost:8000/lineage/downstream/{encoded_uri}"
print("Requesting URL:", url)

try:
    r = httpx.get(url, params={"depth": 5})
    print(r.status_code, r.text)
except Exception as e:
    print("Error:", e)
