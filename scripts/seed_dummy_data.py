import httpx
import uuid
from datetime import datetime, timezone

BASE = "http://localhost:8000"

def ts(): 
    return datetime.now(timezone.utc).isoformat()

events = [
    # Job 1: raw ingest from S3 to Postgres
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "ingest.raw_orders"},
        "inputs": [{"namespace": "s3://data-lake", "name": "landing/orders_2024.csv", "facets": {}}],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "raw.orders", "facets": {}}],
    },
    # Job 2: clean and transform phase
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "transform.clean_orders"},
        "inputs": [{"namespace": "postgres://prod:5432", "name": "raw.orders", "facets": {}}],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "staging.orders", "facets": {}}],
    },
    # Job 3: Enrichment/Join with another static dataset (customers)
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "transform.enrich_orders"},
        "inputs": [
            {"namespace": "postgres://prod:5432", "name": "staging.orders", "facets": {}},
            {"namespace": "postgres://prod:5432", "name": "raw.customers", "facets": {}},
        ],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "mart.orders_enriched", "facets": {}}],
    },
    # Job 4: final dashboard aggregation
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "reporting.dashboard_orders"},
        "inputs": [{"namespace": "postgres://prod:5432", "name": "mart.orders_enriched", "facets": {}}],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "reporting.order_summary", "facets": {}}],
    },
]

def main():
    print("🚀 Sending dummy lineage events to the Lineage Engine...")
    print("-" * 50)
    for e in events:
        try:
            r = httpx.post(f"{BASE}/lineage/events", json=e)
            if r.status_code == 200:
                print(f"✅ SUCCESS: {e['job']['name']} -> {r.json()}")
            else:
                print(f"❌ FAILED: {e['job']['name']} -> Status {r.status_code}: {r.text}")
        except Exception as ex:
            print(f"❌ ERROR: Couldn't connect to API for {e['job']['name']}.")
            print(f"   Ensure the FastAPI server is running at {BASE}")
            print(f"   Exception: {ex}")
    print("-" * 50)
    print("Done! You can now test the Upstream/Downstream endpoints, or check the Neo4j UI (http://localhost:7474).")

if __name__ == "__main__":
    main()
