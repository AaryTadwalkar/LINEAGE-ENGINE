You have 3 ways to feed real data in
Your pipeline accepts data from 3 paths, and you don't need all three — pick what's easiest for you right now.

Path A — OpenLineage JSON Events (easiest, no extra tools)
This is just HTTP POST calls with JSON. You don't need a real database or Airflow. You craft realistic JSON payloads and POST them directly to your running API.
The format your /lineage/events endpoint expects:
json{
  "eventType": "COMPLETE",
  "eventTime": "2024-01-15T10:30:00.000Z",
  "run": {
    "runId": "a1b2c3d4-0000-0000-0000-000000000001"
  },
  "job": {
    "namespace": "airflow",
    "name": "etl.load_orders"
  },
  "inputs": [
    {
      "namespace": "postgres://prod-db:5432",
      "name": "raw.orders",
      "facets": {
        "schema": {
          "fields": [
            {"name": "order_id", "type": "INTEGER"},
            {"name": "customer_id", "type": "INTEGER"},
            {"name": "amount", "type": "NUMERIC"}
          ]
        }
      }
    }
  ],
  "outputs": [
    {
      "namespace": "postgres://prod-db:5432",
      "name": "staging.orders_cleaned",
      "facets": {}
    }
  ]
}
A realistic multi-hop scenario you can POST right now (4 events building a real pipeline chain):
python# save as scripts/seed_real_events.py and run it
import httpx, uuid
from datetime import datetime, timezone

BASE = "http://localhost:8000"

def ts(): return datetime.now(timezone.utc).isoformat()

events = [
    # Job 1: raw ingest
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "ingest.raw_orders"},
        "inputs": [{"namespace": "s3://data-lake", "name": "landing/orders_2024.csv", "facets": {}}],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "raw.orders", "facets": {}}],
    },
    # Job 2: clean + transform
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "transform.clean_orders"},
        "inputs": [{"namespace": "postgres://prod:5432", "name": "raw.orders", "facets": {}}],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "staging.orders", "facets": {}}],
    },
    # Job 3: join with customers (multi-input!)
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
    # Job 4: final dashboard aggregate
    {
        "eventType": "COMPLETE", "eventTime": ts(),
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "airflow", "name": "reporting.dashboard_orders"},
        "inputs": [{"namespace": "postgres://prod:5432", "name": "mart.orders_enriched", "facets": {}}],
        "outputs": [{"namespace": "postgres://prod:5432", "name": "reporting.order_summary", "facets": {}}],
    },
]

for e in events:
    r = httpx.post(f"{BASE}/lineage/events", json=e)
    print(f"{e['job']['name']} → {r.status_code} {r.json()}")
Run it, then immediately test your query endpoints:
bash# Should return the entire 4-hop chain
GET http://localhost:8000/lineage/upstream/postgres%3A%2F%2Fprod%3A5432%2Freporting.order_summary?depth=5

Path B — Real SQL files (your sql_parser.py)
Feed actual .sql files — anything with INSERT INTO ... SELECT FROM, CREATE TABLE AS SELECT, CTEs, JOINs. You don't need a live DB — the parser only reads the SQL text.
Where to get real SQL for free:

github.com/dbt-labs/jaffle_shop — the canonical dbt demo project. The models/ folder has clean, realistic SQL (orders, customers, payments). Download the .sql files directly.
Your own project's migration or transformation SQL files
Any .sql dump file — the parser will extract SELECT ... FROM patterns

How to invoke your parser:
python# run from project root
from parsers.sql_parser import parse_sql_lineage
import httpx, json

sql = """
INSERT INTO mart.customer_orders
SELECT
    c.customer_id,
    COUNT(o.order_id) AS order_count,
    SUM(o.amount)     AS total_spent
FROM staging.customers c
JOIN staging.orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id
"""

event = parse_sql_lineage(sql, job_name="mart.customer_orders", namespace="postgres://prod:5432")
r = httpx.post("http://localhost:8000/lineage/events", json=event.dict())
print(r.json())

Path C — dbt manifest.json (your dbt_parser.py)
If you have dbt installed, run dbt compile in any project and it generates target/manifest.json. Feed that file to your parser.
Quickest path — jaffle_shop demo project:
bashpip install dbt-core dbt-postgres
git clone https://github.com/dbt-labs/jaffle_shop
cd jaffle_shop
dbt deps
dbt compile   # generates target/manifest.json without needing a real DB connection
Then:
pythonfrom parsers.dbt_parser import parse_dbt_manifest
import httpx

events = parse_dbt_manifest("jaffle_shop/target/manifest.json")
for e in events:
    r = httpx.post("http://localhost:8000/lineage/events", json=e.dict())
    print(f"{e.job.name} → {r.json()}")

Recommended order for today
StepWhat to doTime1Run the seed_real_events.py script above (Path A)5 min2Hit the upstream/downstream endpoints and verify graph in Neo4j browser (localhost:7474)10 min3Clone jaffle_shop, grab the .sql files, feed through sql_parser.py15 min4If you want dbt, do dbt compile on jaffle_shop for a real manifest.json20 min




Q->* ok how can i see visualization of the graphs and prostgres(tell me what do we actually store here in postgres)
* how can i test my system, i would need openlineage events, .sql files with actual quries that are ment to run on data and dbt manifest.json files. -> where we would get these
* can i test my system on a actual pipeline, is it available for free


1. Visualizing Neo4j + What Postgres actually stores
Neo4j — you already have a UI
Since your Docker container is running, you already have access to the Neo4j Browser. Open:
http://localhost:7474
Login with neo4j / lineage_password and run Cypher queries directly:
cypher-- See the entire graph
MATCH (n) RETURN n

-- See all relationships
MATCH (a)-[r]->(b) RETURN a, r, b

-- See just the lineage flow
MATCH path = (d1:Dataset)-[:CONSUMES|PRODUCES*]->(d2:Dataset)
RETURN path
It renders as an interactive visual graph — nodes you can drag, click, zoom. After you seed events, this is the best way to verify your graph looks correct.
For something more polished, Bloom is Neo4j's visual exploration tool — it's free with your Neo4j version at http://localhost:7474 under the "Explore" tab.

Postgres — what exactly is stored there
This is important to understand clearly. Postgres in your system stores only one table: run_log. It is a flat audit log — not the graph.
run_log table
─────────────────────────────────────────────────────────────
run_id      │ job_name                  │ status   │ started_at          │ ended_at
─────────────────────────────────────────────────────────────
abc-001     │ ingest.raw_orders         │ COMPLETE │ 2024-01-15 10:30:00 │ 2024-01-15 10:31:45
abc-002     │ transform.clean_orders    │ COMPLETE │ 2024-01-15 10:32:00 │ 2024-01-15 10:33:45
abc-003     │ transform.enrich_orders   │ FAIL     │ 2024-01-15 10:34:00 │ 2024-01-15 10:34:12
abc-004     │ reporting.dashboard       │ COMPLETE │ 2024-01-15 10:35:00 │ 2024-01-15 10:36:30
Why Postgres and not just Neo4j for this?
Neo4j stores the graph — relationships between datasets and jobs. Postgres stores the operational history — every time a job ran, when, and whether it succeeded. They serve different query patterns:
Neo4j answers:    "what is upstream of this table?"
Postgres answers: "how many times did this job fail last week?"
To view Postgres, the easiest free tool is pgAdmin or just run queries via terminal:
bashdocker exec -it <postgres_container_name> psql -U lineage_user -d lineage_db
SELECT * FROM run_log ORDER BY started_at DESC;

2. Where to get real test data for all three paths
Path A — OpenLineage events
You don't find these anywhere — you generate them yourself. But there's a free tool called openlineage-integration-common that has a built-in HTTP client that can replay saved events. The easiest approach is the seed script from our earlier conversation — just craft realistic JSON representing a real pipeline scenario.
Alternatively, the OpenLineage project itself maintains a public GitHub repo with hundreds of real example event JSON files used for their own testing:
github.com/OpenLineage/OpenLineage
→ /spec/facets/          ← JSON schema examples
→ /client/python/tests/  ← real event payloads used in tests
Download any of those .json files and POST them directly to your endpoint.

Path B — Real .sql files
Three free sources, in order of recommendation:
1. jaffle_shop — the standard dbt demo project, has clean realistic SQL
github.com/dbt-labs/jaffle_shop
→ /models/staging/       ← stg_orders.sql, stg_customers.sql, stg_payments.sql
→ /models/               ← orders.sql, customers.sql
These are real transformation queries with JOINs, CTEs, aggregations — exactly what your sql_parser handles.
2. GitLab's data team — a real company's actual production dbt project, open sourced
gitlab.com/gitlab-data/analytics
→ /transform/snowflake-dbt/models/
Hundreds of real SQL files from a real pipeline.
3. Your own brain — write 4-5 SQL files representing a simple pipeline. Since your parser only reads the file and extracts FROM/INSERT INTO, you don't need a real database — the SQL just needs to be syntactically valid.

Path C — dbt manifest.json
Two options:
Option 1 — Generate it yourself (15 minutes, free)
bashpip install dbt-core dbt-postgres
git clone https://github.com/dbt-labs/jaffle_shop
cd jaffle_shop
dbt deps
dbt compile --profiles-dir .   # generates target/manifest.json
dbt compile does NOT need a real database connection — it only resolves dependencies between models. You get a real manifest.json with a proper dependency graph.
Option 2 — Download a pre-generated one
The jaffle_shop repo sometimes includes a pre-compiled manifest in /target/. Otherwise the GitLab analytics repo above has one too. You can also find manifest.json examples on the dbt Slack community (free to join) or the dbt GitHub discussions.

3. Testing on a real free pipeline
Yes — there are fully free options. Here's a comparison:

Option 1 — jaffle_shop locally (best starting point)
What it is: A complete fake e-commerce dbt project — orders, customers, payments — designed specifically for learning and testing.
What you get: Real SQL models, real manifest.json, real dependency graph across ~8 tables.
Cost: Free. Runs entirely on your laptop.
What you need:
bash# Uses DuckDB — no database server needed at all
pip install dbt-core dbt-duckdb
git clone https://github.com/dbt-labs/jaffle_shop
cd jaffle_shop
dbt run   # actually executes the SQL, creates real tables
DuckDB runs in-memory — no Docker, no Postgres needed. After dbt run you have a real executed pipeline and a real manifest.json to feed your system.

Option 2 — Meltano (free, open source, full stack)
What it is: A free open source data platform that includes Airflow + dbt + OpenLineage all pre-configured together.
What you get: A full pipeline that actually emits real OpenLineage events automatically — Path A working for real, not simulated.
Cost: Free. Runs in Docker.
Why it matters for you: Meltano has OpenLineage built in. When you run a pipeline in Meltano, it automatically POSTs real events to whatever URL you configure — meaning you point it at http://localhost:8000/lineage/events and your engine starts receiving real events without any manual JSON crafting.

Option 3 — Astronomer's OpenLineage demo (fastest)
The OpenLineage project maintains a demo environment:
github.com/OpenLineage/OpenLineage
→ /integration/airflow/  ← has a working docker-compose with Airflow + OpenLineage pre-wired
You run their docker-compose, it spins up a real Airflow instance with the OpenLineage plugin already configured, runs a sample DAG, and emits real events. Point OPENLINEAGE_URL at your engine and you're receiving real Airflow events within 30 minutes.

Recommended path for this week
Day 1 — Path B + C together
  Clone jaffle_shop
  Run: dbt compile → get manifest.json → feed to dbt_parser.py
  Grab the .sql files from /models/ → feed to sql_parser.py
  Verify graph in Neo4j browser at localhost:7474

Day 2 — Path A simulated
  Write the seed_real_events.py script
  POST 6-8 events representing a realistic pipeline
  Query upstream/downstream endpoints
  Verify run_log in Postgres

Day 3 — Path A real (optional but satisfying)
  Set up jaffle_shop with dbt-duckdb
  Run dbt run → actual pipeline executes
  Wire Meltano or the OpenLineage Airflow demo
  Watch real events hit your engine automatically
The jaffle_shop project is the single best thing to start with — it covers Path B and C immediately, gives you real SQL and a real manifest, and if you go further it covers Path A too with Meltano or Airflow wiring. 