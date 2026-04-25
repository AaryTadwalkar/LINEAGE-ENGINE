import httpx

url = "http://localhost:8000/lineage/datasets"
try:
    r = httpx.get(url)
    print("Available datasets:")
    for d in r.json():
        print(f"  - {d['uri']}")
except Exception as e:
    print("Error:", e)
