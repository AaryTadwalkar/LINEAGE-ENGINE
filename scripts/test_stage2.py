"""
Integration tests for Stage 1 + Stage 2.
Run with: python scripts/test_stage2.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx
from parsers.sql_parser import parse_sql
from parsers.dbt_parser import parse_manifest
import json
import tempfile

PASSED = []
FAILED = []


def check(name, condition, got=None):
    if condition:
        print(f"  ✅ PASS: {name}")
        PASSED.append(name)
    else:
        print(f"  ❌ FAIL: {name}" + (f" | got: {got}" if got else ""))
        FAILED.append(name)


# ─────────────────────────────────────────────
# SECTION 1: POST /lineage/events — HTTP tests
# ─────────────────────────────────────────────
print("\n" + "="*55)
print("SECTION 1: POST /lineage/events (HTTP Integration)")
print("="*55)

BASE = "http://localhost:8000"

# Test 1 — COMPLETE event returns ok
print("\n[1] COMPLETE event → should return status: ok")
r = httpx.post(f"{BASE}/lineage/events", json={
    "eventType": "COMPLETE",
    "eventTime": "2024-01-15T14:32:00.000Z",
    "run": {
        "runId": "test-run-complete-001",
        "facets": {
            "nominalTime": {
                "nominalStartTime": "2024-01-15T14:30:00.000Z",
                "nominalEndTime": "2024-01-15T14:32:00.000Z"
            }
        }
    },
    "job": {
        "namespace": "local_dev",
        "name": "orders_pipeline.transform_step",
        "facets": {
            "ownership": {"owners": [{"name": "data-team", "type": "team"}]}
        }
    },
    "inputs": [{"namespace": "postgres", "name": "raw.orders", "facets": {}}],
    "outputs": [{"namespace": "postgres", "name": "clean.orders", "facets": {}}]
})
check("HTTP 200", r.status_code == 200, r.status_code)
check("status: ok", r.json().get("status") == "ok", r.json())
check("job name echoed", r.json().get("job") == "orders_pipeline.transform_step", r.json())
check("run_id echoed", r.json().get("run_id") == "test-run-complete-001", r.json())

# Test 2 — START event → skipped
print("\n[2] START event → should return status: skipped")
r2 = httpx.post(f"{BASE}/lineage/events", json={
    "eventType": "START",
    "eventTime": "2024-01-15T14:30:00.000Z",
    "run": {"runId": "test-run-start-001", "facets": {}},
    "job": {"namespace": "local_dev", "name": "some_job", "facets": {}},
    "inputs": [],
    "outputs": []
})
check("HTTP 200", r2.status_code == 200, r2.status_code)
check("status: skipped", r2.json().get("status") == "skipped", r2.json())

# Test 3 — FAIL event → processed
print("\n[3] FAIL event → should return status: ok")
r3 = httpx.post(f"{BASE}/lineage/events", json={
    "eventType": "FAIL",
    "eventTime": "2024-01-15T15:00:00.000Z",
    "run": {"runId": "test-run-fail-001", "facets": {}},
    "job": {"namespace": "local_dev", "name": "broken_job.step", "facets": {}},
    "inputs": [{"namespace": "postgres", "name": "raw.customers", "facets": {}}],
    "outputs": []
})
check("HTTP 200", r3.status_code == 200, r3.status_code)
check("status: ok", r3.json().get("status") == "ok", r3.json())

# Test 4 — Missing required field → 422
print("\n[4] Missing eventType → should return 422")
r4 = httpx.post(f"{BASE}/lineage/events", json={
    "eventTime": "2024-01-15T14:32:00.000Z",
    "run": {"runId": "xyz", "facets": {}},
    "job": {"namespace": "local_dev", "name": "some_job", "facets": {}}
})
check("HTTP 422", r4.status_code == 422, r4.status_code)

# Test 5 — Bad datetime → 422
print("\n[5] Bad eventTime format → should return 422")
r5 = httpx.post(f"{BASE}/lineage/events", json={
    "eventType": "COMPLETE",
    "eventTime": "not-a-date",
    "run": {"runId": "xyz", "facets": {}},
    "job": {"namespace": "local_dev", "name": "some_job", "facets": {}}
})
check("HTTP 422", r5.status_code == 422, r5.status_code)

# Test 6 — Empty inputs/outputs → still ok
print("\n[6] No inputs or outputs → should still return ok")
r6 = httpx.post(f"{BASE}/lineage/events", json={
    "eventType": "COMPLETE",
    "eventTime": "2024-01-15T14:32:00.000Z",
    "run": {"runId": "test-run-empty-001", "facets": {}},
    "job": {"namespace": "local_dev", "name": "no_data_job", "facets": {}},
    "inputs": [],
    "outputs": []
})
check("HTTP 200", r6.status_code == 200, r6.status_code)
check("status: ok", r6.json().get("status") == "ok", r6.json())

# Test 7 — Health still works
print("\n[7] Health check → both databases still ok")
r7 = httpx.get(f"{BASE}/health")
check("HTTP 200", r7.status_code == 200, r7.status_code)
check("neo4j ok", r7.json()["services"].get("neo4j") == "ok", r7.json())
check("postgres ok", r7.json()["services"].get("postgres") == "ok", r7.json())


# ─────────────────────────────────────────────
# SECTION 2: SQL Parser unit tests
# ─────────────────────────────────────────────
print("\n" + "="*55)
print("SECTION 2: SQL Parser (SQLGlot)")
print("="*55)

# Test A — Simple INSERT SELECT
print("\n[A] INSERT INTO ... SELECT * FROM ...")
sql_a = "INSERT INTO clean.orders SELECT * FROM raw.orders WHERE status = 'active'"
ea = parse_sql(sql_a, job_name="insert_test")
check("raw.orders is input", "sql_parser://raw.orders" in [d.uri for d in ea.inputs], [d.uri for d in ea.inputs])
check("clean.orders is output", "sql_parser://clean.orders" in [d.uri for d in ea.outputs], [d.uri for d in ea.outputs])
check("job name set", ea.job.name == "insert_test")
check("orchestrator = sql_script", ea.job.orchestrator == "sql_script")

# Test B — CTE not treated as real table
print("\n[B] CTE alias should NOT appear as input table")
sql_b = """
WITH active_orders AS (
    SELECT * FROM raw.orders WHERE status = 'active'
)
INSERT INTO clean.orders SELECT * FROM active_orders
"""
eb = parse_sql(sql_b)
input_uris_b = [d.uri for d in eb.inputs]
check("CTE not in inputs", "sql_parser://active_orders" not in input_uris_b, input_uris_b)
check("raw.orders in inputs", "sql_parser://raw.orders" in input_uris_b, input_uris_b)

# Test C — CREATE TABLE AS (Snowflake dialect)
print("\n[C] CREATE TABLE AS SELECT (Snowflake dialect)")
sql_c = "CREATE TABLE clean.orders AS SELECT * FROM raw.orders"
ec = parse_sql(sql_c, dialect="snowflake")
check("raw.orders is input", any(d.name == "raw.orders" for d in ec.inputs), [d.name for d in ec.inputs])
check("clean.orders is output", any(d.name == "clean.orders" for d in ec.outputs), [d.name for d in ec.outputs])

# Test D — JOIN: both tables are inputs
print("\n[D] JOIN — both tables should be inputs")
sql_d = "INSERT INTO reporting.summary SELECT o.*, c.name FROM clean.orders o JOIN customers c ON o.customer_id = c.id"
ed = parse_sql(sql_d)
input_names = [d.name for d in ed.inputs]
check("clean.orders in inputs", "clean.orders" in input_names or "orders" in input_names, input_names)
check("reporting.summary is output", any("summary" in d.name for d in ed.outputs), [d.name for d in ed.outputs])


# ─────────────────────────────────────────────
# SECTION 3: dbt Parser unit tests
# ─────────────────────────────────────────────
print("\n" + "="*55)
print("SECTION 3: dbt manifest.json Parser")
print("="*55)

sample_manifest = {
    "nodes": {
        "model.my_project.clean_orders": {
            "resource_type": "model",
            "name": "clean_orders",
            "schema": "analytics",
            "depends_on": {
                "nodes": [
                    "model.my_project.raw_orders",
                    "source.my_project.customers"
                ]
            }
        },
        "model.my_project.no_deps": {
            "resource_type": "model",
            "name": "no_deps",
            "schema": "analytics",
            "depends_on": {"nodes": []}
        },
        "test.my_project.some_test": {
            "resource_type": "test",
            "name": "some_test",
            "schema": "analytics",
            "depends_on": {"nodes": ["model.my_project.clean_orders"]}
        }
    }
}

print("\n[E] dbt manifest parsing")
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(sample_manifest, f)
    tmp_path = f.name

events = parse_manifest(tmp_path)
os.unlink(tmp_path)

check("2 events created (2 deps, 1 no-dep model skipped, 1 test skipped)", len(events) == 2, len(events))
job_names = [e.job.name for e in events]
check("dbt.clean_orders jobs", all("clean_orders" in j for j in job_names), job_names)
check("inputs from depends_on", any(e.inputs[0].name == "raw_orders" for e in events))
check("outputs use schema prefix", any(e.outputs[0].name == "analytics.clean_orders" for e in events))
check("orchestrator = dbt", all(e.job.orchestrator == "dbt" for e in events))


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print("\n" + "="*55)
print(f"RESULTS: {len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    print("FAILED tests:")
    for f in FAILED:
        print(f"  - {f}")
else:
    print("All tests passed ✅")
print("="*55)
sys.exit(0 if not FAILED else 1)
