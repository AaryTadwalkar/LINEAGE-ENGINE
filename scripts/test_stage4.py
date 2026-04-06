"""
Integration tests for Stage 4 (Query API).
Run with: python scripts/test_stage4.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx
from urllib.parse import quote
from datetime import datetime, timezone
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from app.storage.graph_writer import write_event
from app.db_client import get_neo4j_driver, get_postgres_conn

BASE = "http://localhost:8000"
PASSED = []
FAILED = []


def check(name, cond, got=None):
    if cond:
        print(f"  ✅ PASS: {name}")
        PASSED.append(name)
    else:
        print(f"  ❌ FAIL: {name}" + (f" | got: {got}" if got else ""))
        FAILED.append(name)


def wipe_db():
    driver = get_neo4j_driver()
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    
    conn = get_postgres_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM run_log")
    conn.commit()
    conn.close()


def seed_graph():
    """
    Creates a multi-hop graph:
    raw.users ──> j1 ──> staging.users ──┐
                                         ├──> j3 ──> clean.purchases ──> j4 ──> reporting.dashboard
    raw.orders ─> j2 ──> staging.orders ─┘
    """
    now = datetime.now(timezone.utc)
    
    # Event 1
    write_event(LineageEvent(
        job=JobRef(name="j1", owner="dev", orchestrator="airflow"),
        run=RunRef(run_id="run-j1", status="COMPLETE", start_time=now, end_time=now),
        inputs=[DatasetRef(namespace="pg", name="raw.users", uri="pg://raw.users", tags=["pii"])],
        outputs=[DatasetRef(namespace="pg", name="staging.users", uri="pg://staging.users", tags=[])],
        event_time=now
    ))
    
    # Event 2
    write_event(LineageEvent(
        job=JobRef(name="j2", owner="dev", orchestrator="airflow"),
        run=RunRef(run_id="run-j2", status="COMPLETE", start_time=now, end_time=now),
        inputs=[DatasetRef(namespace="pg", name="raw.orders", uri="pg://raw.orders", tags=[])],
        outputs=[DatasetRef(namespace="pg", name="staging.orders", uri="pg://staging.orders", tags=[])],
        event_time=now
    ))
    
    # Event 3
    write_event(LineageEvent(
        job=JobRef(name="j3", owner="dev", orchestrator="airflow"),
        run=RunRef(run_id="run-j3", status="COMPLETE", start_time=now, end_time=now),
        inputs=[
            DatasetRef(namespace="pg", name="staging.users", uri="pg://staging.users", tags=[]),
            DatasetRef(namespace="pg", name="staging.orders", uri="pg://staging.orders", tags=[])
        ],
        outputs=[DatasetRef(namespace="pg", name="clean.purchases", uri="pg://clean.purchases", tags=[])],
        event_time=now
    ))
    
    # Event 4
    write_event(LineageEvent(
        job=JobRef(name="j4", owner="dev", orchestrator="airflow"),
        run=RunRef(run_id="run-j4", status="COMPLETE", start_time=now, end_time=now),
        inputs=[DatasetRef(namespace="pg", name="clean.purchases", uri="pg://clean.purchases", tags=[])],
        outputs=[DatasetRef(namespace="pg", name="reporting.dashboard", uri="pg://reporting.dashboard", tags=[])],
        event_time=now
    ))


print("Wiping DB...")
wipe_db()
print("Seeding test graph...")
seed_graph()
# Give fastapi a tiny moment just in case
time.sleep(0.5)

print("\n" + "="*55)
print("TEST 1: Upstream Query")
print("="*55)
r = httpx.get(f"{BASE}/lineage/upstream/{quote('pg://reporting.dashboard', safe='')}?depth=10")
check("HTTP 200", r.status_code == 200, r.status_code)
data = r.json()
check("Direction = upstream", data.get("direction") == "upstream")

# Expected upstream datasets: clean.purchases, staging.users, staging.orders, raw.users, raw.orders
node_ids = [n["id"] for n in data.get("nodes", [])]
node_labels = [n["label"] for n in data.get("nodes", [])]
node_names = [n["properties"].get("name") for n in data.get("nodes", [])]

check("Contains root dataset", "reporting.dashboard" in node_names)
check("Contains raw.users", "raw.users" in node_names)
check("Contains raw.orders", "raw.orders" in node_names)
check("Contains all 4 jobs", all(j in node_names for j in ["j1", "j2", "j3", "j4"]))
# total datasets (6) + total jobs (4) = 10 nodes
check("Total node count is 10", len(node_names) == 10, len(node_names))

print("\n" + "="*55)
print("TEST 2: Downstream Query")
print("="*55)
r = httpx.get(f"{BASE}/lineage/downstream/{quote('pg://raw.users', safe='')}?depth=10")
check("HTTP 200", r.status_code == 200, r.status_code)
data = r.json()
node_names = [n["properties"].get("name") for n in data.get("nodes", [])]

# Downstream of raw.users: j1, staging.users, j3, clean.purchases, j4, reporting.dashboard
# Notice it DOES NOT include raw.orders, j2, staging.orders, because they are not downstream of raw.users.
check("Contains reporting.dashboard", "reporting.dashboard" in node_names)
check("Contains raw.users", "raw.users" in node_names)
check("Does NOT contain independent datasets (raw.orders)", "raw.orders" not in node_names)
check("Does NOT contain independent jobs (j2)", "j2" not in node_names)
# expecting: raw.users, j1, staging.users, j3, clean.purchases, j4, reporting.dashboard -> 7 nodes
check("Total node count is 7", len(node_names) == 7, len(node_names))


print("\n" + "="*55)
print("TEST 3: Depth Limiting")
print("="*55)
# Walk downstream from raw.users with depth=1
# Should only see raw.users --[CONSUMES]-> j1 --[PRODUCES]-> staging.users
r = httpx.get(f"{BASE}/lineage/downstream/{quote('pg://raw.users', safe='')}?depth=1")
check("HTTP 200", r.status_code == 200, r.status_code)
data = r.json()
node_names = [n["properties"].get("name") for n in data.get("nodes", [])]
check("Bounded depth works", "j3" not in node_names)
check("Exactly 3 nodes (dataset->job->dataset)", len(node_names) == 3, len(node_names))


print("\n" + "="*55)
print("TEST 4: Runs API")
print("="*55)
r = httpx.get(f"{BASE}/lineage/runs/j3")
check("HTTP 200", r.status_code == 200, r.status_code)
data = r.json()
check("job_id matches", data.get("job_id") == "j3")
check("run_count = 1", data.get("run_count") == 1)
check("status matches COMPLETE", data["runs"][0]["status"] == "COMPLETE")
check("input datasets present", "pg://staging.orders" in data["runs"][0]["input_datasets"])


print("\n" + "="*55)
print("TEST 5: Not Found")
print("="*55)
r = httpx.get(f"{BASE}/lineage/upstream/{quote('pg://does.not.exist', safe='')}")
check("HTTP 404 for upstream missing", r.status_code == 404, r.status_code)

r = httpx.get(f"{BASE}/lineage/downstream/{quote('pg://does.not.exist', safe='')}")
check("HTTP 404 for downstream missing", r.status_code == 404, r.status_code)

# Jobs that don't exist in runs API return empty array, not 404
r = httpx.get(f"{BASE}/lineage/runs/ghost_job")
check("HTTP 200 for missing job runs", r.status_code == 200, r.status_code)
check("run_count is 0", r.json().get("run_count") == 0)


# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
print("\n" + "="*55)
print(f"RESULTS: {len(PASSED)} passed  |  {len(FAILED)} failed")
sys.exit(0 if not FAILED else 1)
