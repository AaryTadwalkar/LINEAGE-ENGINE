import httpx
from urllib.parse import quote
r = httpx.get(f'http://localhost:8000/lineage/upstream/{quote("pg://reporting.dashboard", safe="")}?depth=10')
print('STATUS:', r.status_code)
print('BODY:', r.text)
