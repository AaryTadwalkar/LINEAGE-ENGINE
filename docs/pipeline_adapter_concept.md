# Concept: Pipeline Adapters, OpenLineage Events & API Endpoints

*Aary, this document explains every concept we just used.*

---

## 1. What Was the Problem?

We had a broken data chain. The simulator was trying to **parse Jaffle Shop SQL files** to discover what tables each file reads and writes. But **100% of those SQL files use Jinja templates** (`{{ ref('stg_customers') }}`), which our SQL parser cannot handle. So the parser skipped every single file and wrote nothing to the database.

Meanwhile, the dashboard search button was looking for `duckdb://jaffle_shop/raw_orders`, but even if parsing had worked, the actual URIs written were `sql_parser://raw_orders` — completely different.

**The data chain was broken in two places, so nothing ever showed up.**

---

## 2. The Solution: A Pipeline Adapter Plugin

Instead of trying to **reverse-engineer** the pipeline from SQL files, we define the pipeline **directly** as structured data in Python.

This is called a **Pipeline Adapter Pattern** — a single file that acts as the "translator" between your pipeline's world and the lineage engine's world.

```python
# pipeline_plugin.py — What you edit to switch pipelines

PIPELINE_JOBS = [
    {
        "job_name": "stg_orders",
        "inputs":  [("duckdb://jaffle_shop", "raw_orders")],   # reads from here
        "outputs": [("duckdb://jaffle_shop", "stg_orders")],   # produces this
    },
    ...
]
```

It's like a recipe card. Instead of watching someone cook and guessing what ingredients they used, you just read the recipe.

---

## 3. How We Tackled It: The Full Data Flow

Here is the exact path data travels — from your plugin definition to graph node on screen:

```
pipeline_plugin.py
      │
      │  (list of job dicts)
      ▼
run_live_demo.py → _build_ol_event(job)
      │
      │  (OpenLineage JSON — an international standard format)
      ▼
POST http://localhost:8000/lineage/events
      │
      │  (FastAPI receives it)
      ▼
app/ingestion/pydantic_models.py  → validates the JSON shape
app/ingestion/converter.py        → converts OL format → internal LineageEvent
app/storage/graph_writer.py       → writes to Neo4j + Postgres

Neo4j stores:
  (:Dataset {uri: "duckdb://jaffle_shop/raw_orders"})  ──CONSUMES──► (:Job {name: "stg_orders"})
  (:Job)  ──PRODUCES──►  (:Dataset {uri: "duckdb://jaffle_shop/stg_orders"})

React frontend:
  GET /lineage/upstream/duckdb://jaffle_shop/customers
      │
      ▼
  Cypher query traverses the graph backwards
      │
      ▼
  Returns all nodes & edges → React Flow draws the DAG on screen
```

---

## 4. What Is an "API Endpoint"?

An API endpoint is a URL that does something specific when you call it.

| Endpoint | Method | What it does |
|---|---|---|
| `/lineage/events` | POST | **Ingest** a pipeline event → save to database |
| `/lineage/upstream/{uri}` | GET | **Query** everything that produced this dataset |
| `/lineage/downstream/{uri}` | GET | **Query** everything this dataset feeds into |
| `/lineage/datasets` | GET | **List** all datasets in the graph |
| `/lineage/runs/global` | GET | **List** all recent job runs |

The simulator only uses the **POST endpoint** — it's pushing events in. The dashboard only uses the **GET endpoints** — it's reading back what's been stored.

---

## 5. The `plugin.py` Approach vs. SQL Parsing

| Approach | Pros | Cons |
|---|---|---|
| **SQL Parser** (old way) | Automatic, no manual work | Cannot handle Jinja, dbt, stored procedures |
| **Pipeline Plugin** (new way) | Explicit, always correct, easily swappable | Requires someone to write the job definitions |

In the real world, tools like Apache OpenLineage and dbt's artifacts give you the plugin data automatically. Our `pipeline_plugin.py` is a **manual stand-in** for that integration.

To switch this engine to track a completely different pipeline (e.g., an Airflow + Snowflake data warehouse), you only change one file: `pipeline_plugin.py`.
