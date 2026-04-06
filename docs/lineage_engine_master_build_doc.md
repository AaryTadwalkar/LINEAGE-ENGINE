# Metadata Capture & Lineage Engine — Master Build Document

> This document contains everything needed to build the complete system from scratch.
> Hand this to any developer or AI and they have full context to begin building immediately.
> No external references required.

---

## Table of Contents

1. [What We Are Building](#1-what-we-are-building)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Tech Stack — Exact Versions](#3-tech-stack--exact-versions)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Stage 1 — Foundation & Infrastructure](#5-stage-1--foundation--infrastructure)
6. [Stage 2 — Ingestion Layer](#6-stage-2--ingestion-layer)
7. [Stage 3 — Storage Layer](#7-stage-3--storage-layer)
8. [Stage 4 — Query API](#8-stage-4--query-api)
9. [Interface Contracts](#9-interface-contracts)
10. [How to Work Independently (Mocks & Stubs)](#10-how-to-work-independently-mocks--stubs)
11. [Testing Strategy](#11-testing-strategy)
12. [Success Criteria](#12-success-criteria)
13. [What Is Out of Scope](#13-what-is-out-of-scope)

---

## 1. What We Are Building

### The Problem

Modern data pipelines are invisible. A dashboard shows wrong numbers — engineers spend days tracing back through dozens of jobs, SQL scripts, and transformation steps to find where the bad data entered. There is no authoritative record of how data flows through the system.

Specifically:
- When a dataset changes schema, no one knows which downstream jobs will break
- When a model produces unexpected output, no one can trace which training data it came from
- Manual documentation (spreadsheets) is abandoned within weeks because it cannot self-update
- Regulatory requirements (GDPR, HIPAA) demand full data traceability — which does not exist

### What We Build to Solve It

A **backend system** that automatically records every data movement in a graph database and makes that graph queryable via a REST API.

When Airflow finishes a task that reads from `raw.orders` and writes to `clean.orders`, our system automatically records:
- A `Job` node for the Airflow task
- Two `Dataset` nodes (`raw.orders`, `clean.orders`)
- A `CONSUMES` edge (job reads from raw.orders)
- A `PRODUCES` edge (job writes to clean.orders)
- A `Run` node with timestamps and status

An engineer can then call `GET /lineage/upstream/clean.orders` and get back the full ancestry of that dataset — every dataset and job in the chain that produced it — without writing a single Cypher query or knowing Neo4j exists.

### What This System Is NOT

- Not a data pipeline itself — it watches pipelines, it does not run them
- Not a frontend UI — pure backend REST API only
- Not an Airflow replacement — Airflow still orchestrates, we just instrument it
- Not a real-time streaming system — events are written synchronously on each job completion

### The Three Inputs

Data enters the system from three sources, all producing the same internal format:

| Path | Source | Trigger |
|---|---|---|
| A — Runtime | Apache Airflow via OpenLineage | Automatic after every DAG task completes |
| B — Static SQL | `.sql` files via SQLGlot parser | Manual or scheduled batch run |
| C — Static dbt | `manifest.json` via Python parser | Run after every `dbt compile` |

### The Four Outputs (API Endpoints)

| Endpoint | What it returns |
|---|---|
| `POST /lineage/events` | Ingests a lineage event (called by Airflow/parsers) |
| `GET /lineage/upstream/{dataset_id}` | All datasets and jobs upstream of this dataset |
| `GET /lineage/downstream/{dataset_id}` | All datasets and jobs downstream of this dataset |
| `GET /lineage/runs/{job_id}` | All historical runs of a specific job |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                          │
│                                                                 │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Airflow + OL  │  │  SQLGlot Parser │  │  dbt manifest    │  │
│  │  (runtime)    │  │  (SQL files)    │  │  (manifest.json) │  │
│  └───────┬───────┘  └────────┬────────┘  └────────┬─────────┘  │
│          │                   │                    │             │
│          └───────────────────┴────────────────────┘             │
│                              │                                  │
│                    POST /lineage/events                         │
│                    (Pydantic v2 validation)                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │ LineageEvent (internal dataclass)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                            │
│                                                                 │
│         write_event(event: LineageEvent)                        │
│                                                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐ │
│  │    Neo4j Graph DB        │  │     PostgreSQL               │ │
│  │                          │  │                              │ │
│  │  Job ──PRODUCES──► Dataset│  │  run_log table               │ │
│  │   │                      │  │  (audit trail)               │ │
│  │  HAS_RUN                 │  │                              │ │
│  │   │                      │  └──────────────────────────────┘ │
│  │  Run                     │                                   │
│  │                          │  + PII tag propagation hook       │
│  └──────────────────────────┘                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         QUERY API                               │
│                                                                 │
│  GET /lineage/upstream/{id}   ── Cypher backward traversal      │
│  GET /lineage/downstream/{id} ── Cypher forward traversal       │
│  GET /lineage/runs/{job_id}   ── SQL SELECT from run_log        │
│                                                                 │
│                    (FastAPI + Pydantic v2)                      │
└─────────────────────────────────────────────────────────────────┘
```

### The Graph Schema (Neo4j)

```
(:Job)──[:PRODUCES {timestamp}]──►(:Dataset)
(:Dataset)──[:CONSUMES {timestamp}]──►(:Job)
(:Job)──[:HAS_RUN]──►(:Run)
```

Node properties:
- `Job` — `name`, `owner`, `orchestrator`
- `Dataset` — `namespace`, `name`, `uri`, `tags[]`
- `Run` — `run_id`, `status`, `start_time`, `end_time`

The `uri` field on Dataset is the unique identifier used in API calls. Format: `namespace://name`, e.g. `postgres://clean.orders`.

---

## 3. Tech Stack — Exact Versions

Pin every version. Never use `latest`. Version drift is the most common source of "works on my machine" bugs.

| Component | Technology | Version | Why |
|---|---|---|---|
| Language | Python | 3.11 | Async-capable, modern type hints, required by FastAPI |
| Web framework | FastAPI | 0.111.0 | Auto Swagger docs, native Pydantic v2 support, async |
| ASGI server | uvicorn | 0.29.0 | Production-grade, works with FastAPI |
| Data validation | Pydantic | 2.7.0 | v2 is significantly faster than v1, required for FastAPI 0.111 |
| Graph database | Neo4j Community | 5.15.0 | Free, no licence, standard Cypher query language |
| Neo4j Python driver | neo4j | 5.19.0 | Official driver, supports async sessions |
| Relational database | PostgreSQL | 15.6 | Run metadata, audit log, independent of graph |
| Postgres Python driver | psycopg2-binary | 2.9.9 | Standard sync driver, simpler than asyncpg for this use case |
| SQL parser | SQLGlot | 23.12.2 | No dependencies, supports PostgreSQL + Snowflake dialects |
| Lineage standard | openlineage-airflow | 1.18.0 | Hooks into Airflow, emits OpenLineage JSON events |
| Workflow orchestrator | Apache Airflow | 2.9.1 | Pilot DAG only — we instrument it, we don't build it |
| Testing | pytest | 8.2.0 | Standard Python test runner |
| Integration testing | testcontainers | 4.4.0 | Spins up real Neo4j + Postgres containers in tests |
| Containerisation | Docker Compose | v2 | Single command to run the full stack |

### Python Dependencies (`requirements.txt`)

```
fastapi==0.111.0
uvicorn==0.29.0
pydantic==2.7.0
neo4j==5.19.0
psycopg2-binary==2.9.9
sqlglot==23.12.2
pytest==8.2.0
testcontainers==4.4.0
httpx==0.27.0
```

---

## 4. Project Folder Structure

```
lineage-engine/
│
├── docker-compose.yml          # All 4 services
├── .env.example                # All env var names (copy to .env)
├── requirements.txt            # Python dependencies
│
├── app/
│   ├── main.py                 # FastAPI app, mounts all routers
│   ├── models.py               # Shared internal dataclasses (LineageEvent etc.)
│   ├── db_client.py            # Neo4j + Postgres connection wrappers
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── router.py           # POST /lineage/events FastAPI router
│   │   ├── pydantic_models.py  # OpenLineage Pydantic v2 validation models
│   │   └── converter.py        # Converts OL JSON → LineageEvent dataclass
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   └── graph_writer.py     # write_event() — all Neo4j + Postgres writes
│   │
│   └── api/
│       ├── __init__.py
│       ├── router.py           # GET endpoints FastAPI router
│       ├── pydantic_models.py  # Response models (LineageGraphResponse etc.)
│       └── cypher_queries.py   # Raw Cypher strings, separated from logic
│
├── parsers/
│   ├── __init__.py
│   ├── sql_parser.py           # SQLGlot SQL → LineageEvent
│   └── dbt_parser.py           # manifest.json → list[LineageEvent]
│
├── infra/
│   ├── neo4j_init.cypher       # Schema constraints + indexes (auto-runs on startup)
│   └── postgres_init.sql       # run_log table migration (auto-runs on startup)
│
├── tests/
│   ├── conftest.py             # Testcontainers setup, shared fixtures
│   ├── test_ingestion.py       # POST /lineage/events tests
│   ├── test_storage.py         # write_event() unit + integration tests
│   ├── test_api.py             # GET endpoint integration tests
│   ├── test_parsers.py         # SQLGlot + dbt parser unit tests
│   └── test_performance.py     # 100k-edge graph latency tests
│
├── scripts/
│   ├── seed_mock_data.cypher   # Manually seed Neo4j for development
│   └── seed_100k_edges.py      # Performance test data generator
│
└── airflow_dags/
    └── pilot_dag.py            # Example Airflow DAG that emits OL events
```

---

## 5. Stage 1 — Foundation & Infrastructure

This stage must be completed before anyone else can write code. The deliverable is: `docker compose up` starts all 4 services in under 3 minutes, and the shared Python modules are committed and importable.

### 5.1 Environment Variables

Create `.env.example`. Every developer copies this to `.env` and fills in values. Never commit `.env`.

```bash
# .env.example

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=lineage_password

# PostgreSQL
POSTGRES_DSN=postgresql://lineage_user:lineage_password@postgres:5432/lineage_db

# OpenLineage (used by Airflow to find our endpoint)
OPENLINEAGE_URL=http://api:8000
OPENLINEAGE_NAMESPACE=local_dev

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
```

Note: Inside Docker Compose, service names (`neo4j`, `postgres`, `api`) are used as hostnames. Outside Docker (running tests locally without containers), replace with `localhost`.

### 5.2 docker-compose.yml

```yaml
version: "3.9"

services:

  neo4j:
    image: neo4j:5.15.0
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt protocol (used by Python driver)
    environment:
      NEO4J_AUTH: neo4j/lineage_password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
      - ./infra/neo4j_init.cypher:/var/lib/neo4j/import/init.cypher
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "lineage_password", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 10

  postgres:
    image: postgres:15.6
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: lineage_user
      POSTGRES_PASSWORD: lineage_password
      POSTGRES_DB: lineage_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres_init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lineage_user -d lineage_db"]
      interval: 5s
      timeout: 5s
      retries: 10

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: lineage_password
      POSTGRES_DSN: postgresql://lineage_user:lineage_password@postgres:5432/lineage_db
    volumes:
      - ./app:/app/app
      - ./parsers:/app/parsers
    depends_on:
      neo4j:
        condition: service_healthy
      postgres:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  airflow:
    image: apache/airflow:2.9.1
    ports:
      - "8080:8080"
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: sqlite:////opt/airflow/airflow.db
      OPENLINEAGE_URL: http://api:8000
      OPENLINEAGE_NAMESPACE: local_dev
    volumes:
      - ./airflow_dags:/opt/airflow/dags
    depends_on:
      api:
        condition: service_started
    command: airflow standalone

volumes:
  neo4j_data:
  postgres_data:
```

### 5.3 Neo4j Schema Init Script

```cypher
// infra/neo4j_init.cypher
// Runs automatically on first container startup via volume mount

// Uniqueness constraints (also create implicit indexes)
CREATE CONSTRAINT job_name_unique IF NOT EXISTS
  FOR (j:Job) REQUIRE j.name IS UNIQUE;

CREATE CONSTRAINT dataset_uri_unique IF NOT EXISTS
  FOR (d:Dataset) REQUIRE d.uri IS UNIQUE;

CREATE CONSTRAINT run_id_unique IF NOT EXISTS
  FOR (r:Run) REQUIRE r.run_id IS UNIQUE;

// Explicit index for PII tag propagation queries
// (searching datasets by tag value must be fast)
CREATE INDEX dataset_tags_index IF NOT EXISTS
  FOR (d:Dataset) ON (d.tags);
```

Note: The `IF NOT EXISTS` clause makes this script idempotent — safe to run multiple times on restart.

### 5.4 PostgreSQL Schema Init Script

```sql
-- infra/postgres_init.sql
-- Runs automatically when the postgres container first starts

CREATE TABLE IF NOT EXISTS run_log (
    run_id          UUID PRIMARY KEY,
    job_name        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('COMPLETE', 'FAIL', 'RUNNING', 'START')),
    start_time      TIMESTAMPTZ,
    end_time        TIMESTAMPTZ,
    input_datasets  TEXT[],
    output_datasets TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- P4's GET /lineage/runs/{job_id} filters by job_name
CREATE INDEX IF NOT EXISTS run_log_job_name_idx ON run_log (job_name);

-- Useful for time-range queries in future phases
CREATE INDEX IF NOT EXISTS run_log_start_time_idx ON run_log (start_time DESC);
```

### 5.5 Shared Python Models (`app/models.py`)

This is the internal contract between all pipeline stages. Every stage imports from here. Do not use Pydantic here — these are plain Python dataclasses so there is no dependency on the web layer.

```python
# app/models.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class DatasetRef:
    """A reference to a dataset — source or destination of a job."""
    namespace: str          # e.g. "postgres", "snowflake", "s3"
    name: str               # e.g. "clean.orders", "raw.customers"
    uri: str                # unique identifier: f"{namespace}://{name}"
    tags: list[str] = field(default_factory=list)  # e.g. ["pii", "sensitive"]


@dataclass
class JobRef:
    """A reference to a job/task that processed data."""
    name: str               # e.g. "load_orders.transform_step"
    owner: str = ""         # team or person responsible
    orchestrator: str = "airflow"  # "airflow", "dbt", "sql_script"


@dataclass
class RunRef:
    """A single execution of a job."""
    run_id: str             # UUID, unique per execution
    status: str             # "COMPLETE", "FAIL", "RUNNING", "START"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class LineageEvent:
    """
    The internal format for all lineage events regardless of source.
    P2 produces this. P3 consumes it. This is the only handoff between them.
    """
    job: JobRef
    run: RunRef
    inputs: list[DatasetRef]    # datasets this job read from
    outputs: list[DatasetRef]   # datasets this job wrote to
    event_time: Optional[datetime] = None
```

### 5.6 Database Client (`app/db_client.py`)

Single source of truth for database connections. Every module imports from here — no one initialises their own driver.

```python
# app/db_client.py
import os
import psycopg2
from neo4j import GraphDatabase
from functools import lru_cache


@lru_cache(maxsize=1)
def get_neo4j_driver():
    """
    Returns a singleton Neo4j driver instance.
    lru_cache ensures only one driver is created for the lifetime of the process.
    """
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


def get_postgres_conn():
    """
    Returns a new psycopg2 connection per call.
    Caller is responsible for closing it (use as context manager).
    """
    dsn = os.environ["POSTGRES_DSN"]
    return psycopg2.connect(dsn)
```

### 5.7 FastAPI App Skeleton (`app/main.py`)

```python
# app/main.py
from fastapi import FastAPI
from app.db_client import get_neo4j_driver, get_postgres_conn

app = FastAPI(
    title="Metadata Lineage Engine",
    description="Captures and exposes data lineage across heterogeneous pipelines.",
    version="1.0.0",
)


@app.get("/health", tags=["system"])
def health_check():
    """
    Verifies connectivity to both Neo4j and PostgreSQL.
    Returns 200 if both are reachable, 500 if either is down.
    """
    status = {"neo4j": "unknown", "postgres": "unknown"}
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run("RETURN 1")
        status["neo4j"] = "ok"
    except Exception as e:
        status["neo4j"] = f"error: {str(e)}"

    try:
        conn = get_postgres_conn()
        conn.close()
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in status.values())
    return {"status": "healthy" if all_ok else "degraded", "services": status}


# P2 mounts this router — ingestion endpoint
# from app.ingestion.router import router as ingestion_router
# app.include_router(ingestion_router)

# P4 mounts this router — query endpoints
# from app.api.router import router as api_router
# app.include_router(api_router)
```

---

## 6. Stage 2 — Ingestion Layer

P2 owns this entire stage. Receives raw data from 3 sources, validates it, converts it to `LineageEvent`, and calls `write_event()`. P2 does not know or care what `write_event()` does internally.

### 6.1 OpenLineage Event Format (What Airflow Sends)

When Airflow completes a task, it POSTs this JSON to `POST /lineage/events`:

```json
{
  "eventType": "COMPLETE",
  "eventTime": "2024-01-15T14:32:00.000Z",
  "run": {
    "runId": "550e8400-e29b-41d4-a716-446655440000",
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
      "ownership": {
        "owners": [{"name": "data-team", "type": "team"}]
      }
    }
  },
  "inputs": [
    {
      "namespace": "postgres",
      "name": "raw.orders",
      "facets": {
        "schema": {
          "fields": [
            {"name": "order_id", "type": "INTEGER"},
            {"name": "customer_id", "type": "INTEGER"}
          ]
        }
      }
    }
  ],
  "outputs": [
    {
      "namespace": "postgres",
      "name": "clean.orders"
    }
  ]
}
```

### 6.2 Pydantic Validation Models (`app/ingestion/pydantic_models.py`)

These validate incoming JSON strictly before anything touches the database. Invalid payloads are rejected with 422 — no partial writes.

```python
# app/ingestion/pydantic_models.py
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class OLDataset(BaseModel):
    namespace: str
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)


class OLRunFacets(BaseModel):
    nominalTime: Optional[dict[str, Any]] = None
    model_config = {"extra": "allow"}   # ignore unknown facets


class OLRun(BaseModel):
    runId: str
    facets: OLRunFacets = Field(default_factory=OLRunFacets)


class OLJobFacets(BaseModel):
    ownership: Optional[dict[str, Any]] = None
    model_config = {"extra": "allow"}


class OLJob(BaseModel):
    namespace: str
    name: str
    facets: OLJobFacets = Field(default_factory=OLJobFacets)


class OLRunEvent(BaseModel):
    """
    Pydantic model for a full OpenLineage RunEvent.
    This is what Airflow POSTs to /lineage/events.
    """
    eventType: str          # "START", "COMPLETE", "FAIL", "ABORT"
    eventTime: datetime
    run: OLRun
    job: OLJob
    inputs: list[OLDataset] = Field(default_factory=list)
    outputs: list[OLDataset] = Field(default_factory=list)
    producer: str = ""
    schemaURL: str = ""
    model_config = {"extra": "allow"}  # OpenLineage has many optional fields
```

### 6.3 Converter (`app/ingestion/converter.py`)

Converts validated OpenLineage Pydantic model → internal `LineageEvent` dataclass. This is the only place where OL-specific field names are known.

```python
# app/ingestion/converter.py
from app.ingestion.pydantic_models import OLRunEvent, OLDataset
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from datetime import datetime


def ol_dataset_to_ref(ds: OLDataset) -> DatasetRef:
    return DatasetRef(
        namespace=ds.namespace,
        name=ds.name,
        uri=f"{ds.namespace}://{ds.name}",
        tags=[],    # tags come from the graph, not from OL events
    )


def ol_event_to_lineage_event(event: OLRunEvent) -> LineageEvent:
    """
    Converts an OpenLineage RunEvent into the internal LineageEvent format.
    This is the only function that knows about OL field names.
    """
    # Extract owner from job facets if present
    owner = ""
    if event.job.facets.ownership:
        owners = event.job.facets.ownership.get("owners", [])
        if owners:
            owner = owners[0].get("name", "")

    # Extract timing from run facets if present
    start_time = None
    end_time = None
    if event.run.facets.nominalTime:
        nt = event.run.facets.nominalTime
        if nt.get("nominalStartTime"):
            start_time = datetime.fromisoformat(
                nt["nominalStartTime"].replace("Z", "+00:00")
            )
        if nt.get("nominalEndTime"):
            end_time = datetime.fromisoformat(
                nt["nominalEndTime"].replace("Z", "+00:00")
            )

    return LineageEvent(
        job=JobRef(
            name=event.job.name,
            owner=owner,
            orchestrator="airflow",
        ),
        run=RunRef(
            run_id=event.run.runId,
            status=event.eventType,  # "COMPLETE", "FAIL", etc.
            start_time=start_time or event.eventTime,
            end_time=end_time,
        ),
        inputs=[ol_dataset_to_ref(ds) for ds in event.inputs],
        outputs=[ol_dataset_to_ref(ds) for ds in event.outputs],
        event_time=event.eventTime,
    )
```

### 6.4 Ingestion Router (`app/ingestion/router.py`)

```python
# app/ingestion/router.py
from fastapi import APIRouter, HTTPException
from app.ingestion.pydantic_models import OLRunEvent
from app.ingestion.converter import ol_event_to_lineage_event
from app.storage.graph_writer import write_event
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lineage", tags=["ingestion"])


@router.post("/events", status_code=200)
def ingest_event(event: OLRunEvent):
    """
    Receives an OpenLineage RunEvent from Airflow (or any OL-compatible source).
    Validates the payload, converts to internal format, writes to graph + postgres.

    Returns 200 on success.
    Returns 422 if the JSON payload fails Pydantic validation (auto-handled by FastAPI).
    Returns 500 if the database write fails.
    """
    logger.info(f"Received event: job={event.job.name} run={event.run.runId} type={event.eventType}")

    # Skip START events — only write COMPLETE and FAIL
    # (START events have no output datasets yet)
    if event.eventType not in ("COMPLETE", "FAIL"):
        return {"status": "skipped", "reason": f"eventType {event.eventType} not processed"}

    try:
        lineage_event = ol_event_to_lineage_event(event)
        write_event(lineage_event)     # P3's function — P2 calls it, P3 implements it
        logger.info(f"Successfully wrote event for job={event.job.name}")
        return {"status": "ok", "job": event.job.name, "run_id": event.run.runId}
    except Exception as e:
        logger.error(f"Failed to write event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Storage write failed: {str(e)}")
```

### 6.5 SQLGlot SQL Parser (`parsers/sql_parser.py`)

Parses `.sql` files and extracts source and target table references. Output is a `LineageEvent` in the same format as Airflow events.

```python
# parsers/sql_parser.py
import sqlglot
import sqlglot.expressions as exp
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from datetime import datetime, timezone
import uuid
import os


def _extract_tables(ast: sqlglot.Expression, node_type) -> set[str]:
    """Walk the AST and collect all table references of a given type."""
    return {
        table.name.lower()
        for table in ast.find_all(node_type)
        if table.name  # exclude anonymous/derived tables
    }


def _normalise_table_name(table_expr: exp.Table) -> str:
    """
    Normalise multi-part table names.
    db.schema.table  →  schema.table
    schema.table     →  schema.table
    table            →  table
    """
    parts = []
    if table_expr.args.get("db"):
        pass  # drop the database prefix
    if table_expr.args.get("db") and table_expr.args.get("table"):
        pass
    if hasattr(table_expr, "db") and table_expr.db:
        parts.append(table_expr.db.lower())
    parts.append(table_expr.name.lower())
    return ".".join(parts)


def parse_sql(sql: str, dialect: str = "postgres", job_name: str = None) -> LineageEvent:
    """
    Parse a SQL string and return a LineageEvent representing its lineage.

    Args:
        sql: Raw SQL string (SELECT, INSERT, CREATE TABLE AS, etc.)
        dialect: "postgres" or "snowflake"
        job_name: Optional name for the job. Defaults to the SQL file name.

    Returns:
        LineageEvent with inputs (source tables) and outputs (target tables).

    Raises:
        ValueError: If SQLGlot cannot parse the SQL.
    """
    try:
        statements = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"SQLGlot could not parse SQL: {e}")

    source_tables: set[str] = set()
    target_tables: set[str] = set()

    # Collect all CTE names — these are NOT real tables
    cte_names: set[str] = set()

    for statement in statements:
        if statement is None:
            continue

        # Find CTE names to exclude from source tables
        for cte in statement.find_all(exp.CTE):
            if cte.alias:
                cte_names.add(cte.alias.lower())

        # Target tables: INSERT INTO, CREATE TABLE AS SELECT
        for insert in statement.find_all(exp.Insert):
            if insert.this and isinstance(insert.this, exp.Table):
                target_tables.add(_normalise_table_name(insert.this))

        for create in statement.find_all(exp.Create):
            if create.this and isinstance(create.this, exp.Table):
                target_tables.add(_normalise_table_name(create.this))

        # Source tables: FROM clause, JOIN clauses
        # But NOT subqueries (those are anonymous)
        for table in statement.find_all(exp.Table):
            name = _normalise_table_name(table)
            # Skip if this table is a CTE reference or a target table
            if name and name not in cte_names and name not in target_tables:
                source_tables.add(name)

    # Remove targets from sources (a table can appear in both if self-join)
    source_tables -= target_tables

    namespace = "sql_parser"
    inputs = [
        DatasetRef(namespace=namespace, name=t, uri=f"{namespace}://{t}")
        for t in sorted(source_tables)
    ]
    outputs = [
        DatasetRef(namespace=namespace, name=t, uri=f"{namespace}://{t}")
        for t in sorted(target_tables)
    ]

    return LineageEvent(
        job=JobRef(
            name=job_name or "sql_script",
            owner="",
            orchestrator="sql_script",
        ),
        run=RunRef(
            run_id=str(uuid.uuid4()),
            status="COMPLETE",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        inputs=inputs,
        outputs=outputs,
        event_time=datetime.now(timezone.utc),
    )


def parse_sql_file(filepath: str, dialect: str = "postgres") -> LineageEvent:
    """Convenience wrapper that reads a file and calls parse_sql()."""
    with open(filepath, "r") as f:
        sql = f.read()
    job_name = os.path.basename(filepath).replace(".sql", "")
    return parse_sql(sql, dialect=dialect, job_name=job_name)
```

### 6.6 dbt Manifest Parser (`parsers/dbt_parser.py`)

```python
# parsers/dbt_parser.py
import json
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from datetime import datetime, timezone
import uuid


def parse_manifest(manifest_path: str) -> list[LineageEvent]:
    """
    Parse a dbt manifest.json file and return one LineageEvent
    per model dependency relationship.

    The manifest.json is generated by running `dbt compile` or `dbt run`.
    It lives at target/manifest.json in the dbt project root.

    Args:
        manifest_path: Absolute or relative path to manifest.json

    Returns:
        List of LineageEvent — one per (model, dependency) pair.
        If model A depends on model B and C, returns 2 events.
    """
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    nodes = manifest.get("nodes", {})
    events = []

    for node_id, node in nodes.items():
        # Only process model nodes — skip tests, snapshots, analyses, sources
        if node.get("resource_type") not in ("model",):
            continue

        model_name = node.get("name", node_id)
        schema = node.get("schema", "dbt")
        depends_on_nodes = node.get("depends_on", {}).get("nodes", [])

        if not depends_on_nodes:
            # Model with no dependencies — still record it as a dataset
            # but there's no lineage edge to create
            continue

        for dep_node_id in depends_on_nodes:
            # dep_node_id looks like: "model.my_project.orders_raw"
            # or "source.my_project.raw_orders"
            dep_parts = dep_node_id.split(".")
            dep_name = dep_parts[-1] if dep_parts else dep_node_id

            event = LineageEvent(
                job=JobRef(
                    name=f"dbt.{model_name}",
                    owner="",
                    orchestrator="dbt",
                ),
                run=RunRef(
                    run_id=str(uuid.uuid4()),
                    status="COMPLETE",
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                ),
                inputs=[
                    DatasetRef(
                        namespace="dbt",
                        name=dep_name,
                        uri=f"dbt://{dep_name}",
                    )
                ],
                outputs=[
                    DatasetRef(
                        namespace="dbt",
                        name=f"{schema}.{model_name}",
                        uri=f"dbt://{schema}.{model_name}",
                    )
                ],
                event_time=datetime.now(timezone.utc),
            )
            events.append(event)

    return events
```

### 6.7 Pilot Airflow DAG (`airflow_dags/pilot_dag.py`)

```python
# airflow_dags/pilot_dag.py
"""
Pilot DAG for testing OpenLineage event emission.
This DAG does fake work — the point is that it triggers
OpenLineage events that our engine receives and records.

Requires: openlineage-airflow installed in the Airflow environment.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


def extract_raw_orders():
    """Simulates reading from a raw source."""
    print("Extracting raw orders...")
    # In a real pipeline this would query a database


def transform_orders():
    """Simulates a transformation step."""
    print("Transforming orders...")


def load_clean_orders():
    """Simulates loading to a destination."""
    print("Loading clean orders...")


with DAG(
    dag_id="pilot_lineage_dag",
    start_date=datetime(2024, 1, 1),
    schedule=timedelta(days=1),
    catchup=False,
    default_args={
        "owner": "data-team",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    # OpenLineage reads these to name the datasets
    # Format: {"inputs": [...], "outputs": [...]} per task
) as dag:

    extract = PythonOperator(
        task_id="extract_raw_orders",
        python_callable=extract_raw_orders,
        # openlineage-airflow will auto-detect and emit lineage
        # but we can also be explicit:
        inlets=[{"namespace": "postgres", "name": "raw.orders"}],
        outlets=[{"namespace": "postgres", "name": "staging.orders"}],
    )

    transform = PythonOperator(
        task_id="transform_orders",
        python_callable=transform_orders,
        inlets=[{"namespace": "postgres", "name": "staging.orders"}],
        outlets=[{"namespace": "postgres", "name": "clean.orders"}],
    )

    load = PythonOperator(
        task_id="load_clean_orders",
        python_callable=load_clean_orders,
        inlets=[{"namespace": "postgres", "name": "clean.orders"}],
        outlets=[{"namespace": "postgres", "name": "reporting.orders_summary"}],
    )

    extract >> transform >> load
```

---

## 7. Stage 3 — Storage Layer

P3 owns this stage completely. The only public interface is `write_event(event: LineageEvent)`. P2 calls it. P3 implements everything inside it. P3 does not touch any FastAPI code.

### 7.1 The Main Write Function (`app/storage/graph_writer.py`)

```python
# app/storage/graph_writer.py
from app.models import LineageEvent, DatasetRef, JobRef, RunRef
from app.db_client import get_neo4j_driver, get_postgres_conn
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def write_event(event: LineageEvent) -> None:
    """
    PUBLIC INTERFACE — P2 calls this, P3 implements this.

    Writes a complete lineage event to Neo4j and PostgreSQL.
    All Neo4j operations happen in a single transaction.
    PostgreSQL insert happens after Neo4j succeeds.
    PII tag propagation runs as a post-write step.

    Args:
        event: A validated LineageEvent from the ingestion layer.

    Raises:
        Exception: If Neo4j write fails. Postgres failure is logged but not raised.
    """
    driver = get_neo4j_driver()

    with driver.session() as session:
        session.execute_write(_write_graph, event)

    _write_postgres(event)
    _propagate_pii_tags(event)

    logger.info(
        f"write_event complete: job={event.job.name} "
        f"run={event.run.run_id} "
        f"inputs={len(event.inputs)} outputs={len(event.outputs)}"
    )


def _write_graph(tx, event: LineageEvent) -> None:
    """
    All Neo4j writes in one transaction.
    Uses MERGE everywhere — safe to call multiple times with same data.
    """
    _upsert_job(tx, event.job)

    for dataset in event.inputs:
        _upsert_dataset(tx, dataset)
        _create_consumes_edge(tx, dataset, event.job, event.event_time)

    for dataset in event.outputs:
        _upsert_dataset(tx, dataset)
        _create_produces_edge(tx, event.job, dataset, event.event_time)

    _create_run(tx, event.run)
    _create_has_run_edge(tx, event.job, event.run)


def _upsert_job(tx, job: JobRef) -> None:
    tx.run(
        """
        MERGE (j:Job {name: $name})
        ON CREATE SET
            j.owner = $owner,
            j.orchestrator = $orchestrator,
            j.created_at = $now
        ON MATCH SET
            j.owner = $owner,
            j.orchestrator = $orchestrator
        """,
        name=job.name,
        owner=job.owner,
        orchestrator=job.orchestrator,
        now=datetime.now(timezone.utc).isoformat(),
    )


def _upsert_dataset(tx, dataset: DatasetRef) -> None:
    tx.run(
        """
        MERGE (d:Dataset {uri: $uri})
        ON CREATE SET
            d.namespace = $namespace,
            d.name = $name,
            d.tags = $tags,
            d.created_at = $now
        """,
        uri=dataset.uri,
        namespace=dataset.namespace,
        name=dataset.name,
        tags=dataset.tags,
        now=datetime.now(timezone.utc).isoformat(),
    )


def _create_produces_edge(tx, job: JobRef, dataset: DatasetRef, ts) -> None:
    """Job → PRODUCES → Dataset"""
    tx.run(
        """
        MATCH (j:Job {name: $job_name})
        MATCH (d:Dataset {uri: $dataset_uri})
        MERGE (j)-[r:PRODUCES]->(d)
        ON CREATE SET r.timestamp = $timestamp
        """,
        job_name=job.name,
        dataset_uri=dataset.uri,
        timestamp=ts.isoformat() if ts else datetime.now(timezone.utc).isoformat(),
    )


def _create_consumes_edge(tx, dataset: DatasetRef, job: JobRef, ts) -> None:
    """Dataset → CONSUMES → Job"""
    tx.run(
        """
        MATCH (d:Dataset {uri: $dataset_uri})
        MATCH (j:Job {name: $job_name})
        MERGE (d)-[r:CONSUMES]->(j)
        ON CREATE SET r.timestamp = $timestamp
        """,
        dataset_uri=dataset.uri,
        job_name=job.name,
        timestamp=ts.isoformat() if ts else datetime.now(timezone.utc).isoformat(),
    )


def _create_run(tx, run: RunRef) -> None:
    tx.run(
        """
        MERGE (r:Run {run_id: $run_id})
        ON CREATE SET
            r.status = $status,
            r.start_time = $start_time,
            r.end_time = $end_time
        """,
        run_id=run.run_id,
        status=run.status,
        start_time=run.start_time.isoformat() if run.start_time else None,
        end_time=run.end_time.isoformat() if run.end_time else None,
    )


def _create_has_run_edge(tx, job: JobRef, run: RunRef) -> None:
    tx.run(
        """
        MATCH (j:Job {name: $job_name})
        MATCH (r:Run {run_id: $run_id})
        MERGE (j)-[:HAS_RUN]->(r)
        """,
        job_name=job.name,
        run_id=run.run_id,
    )


def _write_postgres(event: LineageEvent) -> None:
    """
    Inserts a run record into run_log.
    This is an audit log — independent of Neo4j.
    Failure here is logged but does not raise (graph is source of truth).
    """
    try:
        conn = get_postgres_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO run_log
                        (run_id, job_name, status, start_time, end_time,
                         input_datasets, output_datasets)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO NOTHING
                    """,
                    (
                        event.run.run_id,
                        event.job.name,
                        event.run.status,
                        event.run.start_time,
                        event.run.end_time,
                        [d.uri for d in event.inputs],
                        [d.uri for d in event.outputs],
                    ),
                )
        conn.close()
    except Exception as e:
        logger.error(f"Postgres write failed for run {event.run.run_id}: {e}")
        # Do not re-raise — graph is source of truth


def _propagate_pii_tags(event: LineageEvent) -> None:
    """
    Post-write hook: if any input dataset carries a pii or sensitive tag,
    propagate that tag to all output datasets in this event.

    This is 1-hop propagation only — direct outputs of this event.
    Multi-hop propagation across historical edges is Phase 2 scope.
    """
    pii_tags = {"pii", "sensitive"}
    input_has_pii = any(
        bool(pii_tags.intersection(set(d.tags)))
        for d in event.inputs
    )

    if not input_has_pii:
        return

    driver = get_neo4j_driver()
    with driver.session() as session:
        for output in event.outputs:
            session.run(
                """
                MATCH (d:Dataset {uri: $uri})
                WHERE NOT 'pii' IN d.tags
                SET d.tags = d.tags + ['pii']
                """,
                uri=output.uri,
            )
    logger.info(
        f"PII tags propagated to {len(event.outputs)} output datasets "
        f"from job {event.job.name}"
    )
```

---

## 8. Stage 4 — Query API

P4 owns this stage. The 3 GET endpoints that consumers use. P4 writes Cypher traversal queries and wraps them in FastAPI routes with Pydantic v2 response models.

### 8.1 Response Models (`app/api/pydantic_models.py`)

```python
# app/api/pydantic_models.py
from pydantic import BaseModel
from typing import Optional, Any


class NodeModel(BaseModel):
    """Represents a single node in the lineage graph."""
    id: str                     # Neo4j element ID
    label: str                  # "Job", "Dataset", or "Run"
    properties: dict[str, Any]  # All node properties


class EdgeModel(BaseModel):
    """Represents a directed relationship between two nodes."""
    source_id: str
    target_id: str
    type: str                   # "PRODUCES", "CONSUMES", "HAS_RUN"
    properties: dict[str, Any]


class LineageGraphResponse(BaseModel):
    """
    Response for upstream and downstream traversal endpoints.
    Returns the full subgraph as nodes + edges.
    """
    dataset_id: str
    direction: str              # "upstream" or "downstream"
    depth: int
    nodes: list[NodeModel]
    edges: list[EdgeModel]
    node_count: int
    edge_count: int


class RunRecord(BaseModel):
    run_id: str
    job_name: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    input_datasets: list[str] = []
    output_datasets: list[str] = []


class RunsResponse(BaseModel):
    job_id: str
    run_count: int
    runs: list[RunRecord]
```

### 8.2 Cypher Queries (`app/api/cypher_queries.py`)

Cypher strings are kept separate from route logic. Easy to test and tune independently.

```python
# app/api/cypher_queries.py

UPSTREAM_QUERY = """
MATCH (start:Dataset {uri: $uri})
CALL apoc.path.subgraphAll(start, {
    relationshipFilter: 'CONSUMES>|<PRODUCES',
    maxLevel: $depth
})
YIELD nodes, relationships
RETURN nodes, relationships
"""

# Fallback if APOC is not available — pure Cypher variable-length path
UPSTREAM_QUERY_NO_APOC = """
MATCH path = (start:Dataset {uri: $uri})
              -[:CONSUMES*0..{depth}]->(j:Job)
              -[:CONSUMES*0..{depth}]->(upstream:Dataset)
WHERE start <> upstream
RETURN DISTINCT
    nodes(path) AS path_nodes,
    relationships(path) AS path_rels
LIMIT 1000
"""

DOWNSTREAM_QUERY = """
MATCH path = (start:Dataset {uri: $uri})
              <-[:PRODUCES*0..{depth}]-(j:Job)
              -[:PRODUCES*0..{depth}]->(downstream:Dataset)
WHERE start <> downstream
RETURN DISTINCT
    nodes(path) AS path_nodes,
    relationships(path) AS path_rels
LIMIT 1000
"""

DATASET_EXISTS_QUERY = """
MATCH (d:Dataset {uri: $uri})
RETURN d.uri AS uri LIMIT 1
"""
```

### 8.3 Query API Router (`app/api/router.py`)

```python
# app/api/router.py
from fastapi import APIRouter, HTTPException, Query
from app.api.pydantic_models import LineageGraphResponse, RunsResponse, NodeModel, EdgeModel, RunRecord
from app.db_client import get_neo4j_driver, get_postgres_conn
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lineage", tags=["query"])


def _neo4j_node_to_model(node) -> NodeModel:
    label = list(node.labels)[0] if node.labels else "Unknown"
    return NodeModel(
        id=str(node.element_id),
        label=label,
        properties=dict(node),
    )


def _neo4j_rel_to_model(rel) -> EdgeModel:
    return EdgeModel(
        source_id=str(rel.start_node.element_id),
        target_id=str(rel.end_node.element_id),
        type=rel.type,
        properties=dict(rel),
    )


@router.get("/upstream/{dataset_id}", response_model=LineageGraphResponse)
def get_upstream(
    dataset_id: str,
    depth: int = Query(default=10, ge=1, le=20, description="Max traversal hops"),
):
    """
    Returns all datasets and jobs that are upstream of the given dataset.
    Walks CONSUMES edges backwards — finding everything that produced this data.

    dataset_id: The URI of the dataset, e.g. "postgres://clean.orders"
    depth: Maximum number of hops to traverse (default 10, max 20)
    """
    driver = get_neo4j_driver()

    with driver.session() as session:
        # First check if dataset exists
        exists = session.run(
            "MATCH (d:Dataset {uri: $uri}) RETURN d.uri LIMIT 1",
            uri=dataset_id
        ).single()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

        result = session.run(
            f"""
            MATCH path = (start:Dataset {{uri: $uri}})
                          <-[:PRODUCES*1..{depth}]-(j:Job)
                          -[:PRODUCES*1..{depth}]->(upstream:Dataset)
            WHERE start <> upstream
            RETURN DISTINCT nodes(path) AS ns, relationships(path) AS rs
            LIMIT 1000
            """,
            uri=dataset_id,
        )

        all_nodes: dict[str, NodeModel] = {}
        all_edges: list[EdgeModel] = []

        for record in result:
            for node in record["ns"]:
                node_model = _neo4j_node_to_model(node)
                all_nodes[node_model.id] = node_model
            for rel in record["rs"]:
                all_edges.append(_neo4j_rel_to_model(rel))

    return LineageGraphResponse(
        dataset_id=dataset_id,
        direction="upstream",
        depth=depth,
        nodes=list(all_nodes.values()),
        edges=all_edges,
        node_count=len(all_nodes),
        edge_count=len(all_edges),
    )


@router.get("/downstream/{dataset_id}", response_model=LineageGraphResponse)
def get_downstream(
    dataset_id: str,
    depth: int = Query(default=10, ge=1, le=20),
):
    """
    Returns all datasets and jobs downstream of the given dataset.
    Walks PRODUCES edges forward — finding everything this data feeds into.
    """
    driver = get_neo4j_driver()

    with driver.session() as session:
        exists = session.run(
            "MATCH (d:Dataset {uri: $uri}) RETURN d.uri LIMIT 1",
            uri=dataset_id
        ).single()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

        result = session.run(
            f"""
            MATCH path = (start:Dataset {{uri: $uri}})
                          <-[:PRODUCES*1..{depth}]-(j:Job)
                          -[:PRODUCES*1..{depth}]->(downstream:Dataset)
            WHERE start <> downstream
            RETURN DISTINCT nodes(path) AS ns, relationships(path) AS rs
            LIMIT 1000
            """,
            uri=dataset_id,
        )

        all_nodes: dict[str, NodeModel] = {}
        all_edges: list[EdgeModel] = []

        for record in result:
            for node in record["ns"]:
                node_model = _neo4j_node_to_model(node)
                all_nodes[node_model.id] = node_model
            for rel in record["rs"]:
                all_edges.append(_neo4j_rel_to_model(rel))

    return LineageGraphResponse(
        dataset_id=dataset_id,
        direction="downstream",
        depth=depth,
        nodes=list(all_nodes.values()),
        edges=all_edges,
        node_count=len(all_nodes),
        edge_count=len(all_edges),
    )


@router.get("/runs/{job_id}", response_model=RunsResponse)
def get_runs(job_id: str, limit: int = Query(default=50, ge=1, le=500)):
    """
    Returns the run history of a specific job from PostgreSQL.
    Returns empty list (not 404) if the job has no recorded runs.

    job_id: The job name, e.g. "orders_pipeline.transform_step"
    """
    try:
        conn = get_postgres_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, job_name, status, start_time, end_time,
                       input_datasets, output_datasets
                FROM run_log
                WHERE job_name = %s
                ORDER BY start_time DESC
                LIMIT %s
                """,
                (job_id, limit),
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Postgres query failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

    runs = [
        RunRecord(
            run_id=str(row[0]),
            job_name=row[1],
            status=row[2],
            start_time=row[3].isoformat() if row[3] else None,
            end_time=row[4].isoformat() if row[4] else None,
            input_datasets=row[5] or [],
            output_datasets=row[6] or [],
        )
        for row in rows
    ]

    return RunsResponse(job_id=job_id, run_count=len(runs), runs=runs)
```

---

## 9. Interface Contracts

These are the only 3 points where one stage hands off to another. Agree and lock these before Week 3. Changing them after coding begins breaks multiple people.

### Contract 1: P1 → Everyone

| What | Value |
|---|---|
| `LineageEvent` fields | `job: JobRef`, `run: RunRef`, `inputs: list[DatasetRef]`, `outputs: list[DatasetRef]`, `event_time: Optional[datetime]` |
| `DatasetRef.uri` format | `"{namespace}://{name}"` e.g. `"postgres://clean.orders"` |
| Neo4j node property names | `Job.name`, `Dataset.uri`, `Run.run_id` (these are the unique keys for MERGE) |
| Edge type names | `PRODUCES`, `CONSUMES`, `HAS_RUN` |
| Postgres table | `run_log` with columns as defined in `postgres_init.sql` |
| Env var names | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `POSTGRES_DSN` |
| Docker service names | `neo4j`, `postgres`, `api`, `airflow` |

### Contract 2: P2 → P3

```python
# P2 calls this. P3 implements this. This is the entire interface.
def write_event(event: LineageEvent) -> None:
    ...
```

P2 imports: `from app.storage.graph_writer import write_event`

P2 guarantees: `event` is a valid `LineageEvent` with at least `job.name` and `run.run_id` set. Inputs and outputs may be empty lists.

P3 guarantees: returns `None` on success, raises `Exception` on failure (P2's endpoint catches and returns 500).

### Contract 3: P3 → P4

P3 writes these exact property names to Neo4j. P4's Cypher queries read them.

```
(:Job)    — properties: name (str), owner (str), orchestrator (str)
(:Dataset) — properties: uri (str), namespace (str), name (str), tags (list[str])
(:Run)    — properties: run_id (str), status (str), start_time (str ISO), end_time (str ISO)

(:Job)-[:PRODUCES {timestamp: str ISO}]->(:Dataset)
(:Dataset)-[:CONSUMES {timestamp: str ISO}]->(:Job)
(:Job)-[:HAS_RUN]->(:Run)
```

---

## 10. How to Work Independently (Mocks & Stubs)

Because stages depend on each other, each person uses stubs to work in parallel before the real implementation exists.

### P2 — Stubbing P3's `write_event()`

Create `app/storage/graph_writer.py` locally with:

```python
# STUB — replace with P3's real implementation when ready
from app.models import LineageEvent
import logging

logger = logging.getLogger(__name__)

def write_event(event: LineageEvent) -> None:
    logger.info(f"[STUB] write_event called: job={event.job.name} run={event.run.run_id}")
    logger.info(f"[STUB] inputs: {[d.uri for d in event.inputs]}")
    logger.info(f"[STUB] outputs: {[d.uri for d in event.outputs]}")
    # Does nothing — just logs. Replace with P3's code when ready.
```

P2 builds and tests the full ingestion path against this stub. When P3 commits the real implementation, P2 deletes the stub file and re-runs tests.

### P3 — Developing Without Waiting for P2

P3 writes a hardcoded test event and calls `write_event()` directly:

```python
# scripts/test_write_event.py — run this to test P3's code in isolation
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from app.storage.graph_writer import write_event
from datetime import datetime, timezone

test_event = LineageEvent(
    job=JobRef(name="test_job", owner="dev", orchestrator="manual"),
    run=RunRef(
        run_id="test-run-001",
        status="COMPLETE",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    ),
    inputs=[DatasetRef(namespace="postgres", name="raw.orders", uri="postgres://raw.orders", tags=["pii"])],
    outputs=[DatasetRef(namespace="postgres", name="clean.orders", uri="postgres://clean.orders")],
    event_time=datetime.now(timezone.utc),
)

write_event(test_event)
print("Done — check Neo4j browser at http://localhost:7474")
```

P3 runs this script directly, inspects Neo4j browser, and iterates. No P2 needed.

### P4 — Seeding Mock Data Without Waiting for P3

P4 seeds the graph directly using Cypher in the Neo4j browser or via a script:

```cypher
// scripts/seed_mock_data.cypher
// Run in Neo4j browser at http://localhost:7474

// Create a simple 3-step pipeline
CREATE (raw:Dataset {uri: "postgres://raw.orders", name: "raw.orders", namespace: "postgres", tags: ["pii"]})
CREATE (staging:Dataset {uri: "postgres://staging.orders", name: "staging.orders", namespace: "postgres", tags: ["pii"]})
CREATE (clean:Dataset {uri: "postgres://clean.orders", name: "clean.orders", namespace: "postgres", tags: ["pii"]})

CREATE (j1:Job {name: "extract_job", owner: "data-team", orchestrator: "airflow"})
CREATE (j2:Job {name: "transform_job", owner: "data-team", orchestrator: "airflow"})

CREATE (r1:Run {run_id: "run-001", status: "COMPLETE", start_time: "2024-01-15T10:00:00Z"})
CREATE (r2:Run {run_id: "run-002", status: "COMPLETE", start_time: "2024-01-15T10:05:00Z"})

CREATE (raw)-[:CONSUMES {timestamp: "2024-01-15T10:00:00Z"}]->(j1)
CREATE (j1)-[:PRODUCES {timestamp: "2024-01-15T10:02:00Z"}]->(staging)
CREATE (staging)-[:CONSUMES {timestamp: "2024-01-15T10:05:00Z"}]->(j2)
CREATE (j2)-[:PRODUCES {timestamp: "2024-01-15T10:07:00Z"}]->(clean)
CREATE (j1)-[:HAS_RUN]->(r1)
CREATE (j2)-[:HAS_RUN]->(r2)
```

P4 builds all 3 endpoints against this mock graph. When P3's real writes populate Neo4j, the endpoints work against real data with zero changes.

---

## 11. Testing Strategy

### Test File: `tests/conftest.py`

```python
# tests/conftest.py
import pytest
from testcontainers.neo4j import Neo4jContainer
from testcontainers.postgres import PostgresContainer
from neo4j import GraphDatabase
import psycopg2
import os


@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5.15.0").with_env("NEO4J_AUTH", "neo4j/testpassword") as neo4j:
        yield neo4j


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15.6") as postgres:
        yield postgres


@pytest.fixture(autouse=True)
def set_env_vars(neo4j_container, postgres_container):
    """Sets env vars so db_client.py connects to test containers."""
    os.environ["NEO4J_URI"] = neo4j_container.get_connection_url()
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "testpassword"
    os.environ["POSTGRES_DSN"] = postgres_container.get_connection_url()
    yield
    # Clear lru_cache after each test so fresh connections are made
    from app.db_client import get_neo4j_driver
    get_neo4j_driver.cache_clear()


@pytest.fixture(autouse=True)
def clean_neo4j(neo4j_container):
    """Wipe all nodes and edges before each test."""
    driver = GraphDatabase.driver(
        neo4j_container.get_connection_url(),
        auth=("neo4j", "testpassword")
    )
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    driver.close()
    yield


@pytest.fixture
def sample_event():
    from app.models import LineageEvent, JobRef, RunRef, DatasetRef
    from datetime import datetime, timezone
    return LineageEvent(
        job=JobRef(name="test.job", owner="test-team", orchestrator="airflow"),
        run=RunRef(run_id="test-run-001", status="COMPLETE",
                   start_time=datetime.now(timezone.utc),
                   end_time=datetime.now(timezone.utc)),
        inputs=[DatasetRef(namespace="postgres", name="raw.orders",
                           uri="postgres://raw.orders", tags=[])],
        outputs=[DatasetRef(namespace="postgres", name="clean.orders",
                            uri="postgres://clean.orders", tags=[])],
        event_time=datetime.now(timezone.utc),
    )
```

### Test File: `tests/test_storage.py`

```python
# tests/test_storage.py
from app.storage.graph_writer import write_event
from app.db_client import get_neo4j_driver
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from datetime import datetime, timezone


def test_write_event_creates_job_node(sample_event):
    write_event(sample_event)
    driver = get_neo4j_driver()
    with driver.session() as s:
        result = s.run("MATCH (j:Job {name: 'test.job'}) RETURN j").single()
    assert result is not None
    assert result["j"]["name"] == "test.job"


def test_write_event_creates_dataset_nodes(sample_event):
    write_event(sample_event)
    driver = get_neo4j_driver()
    with driver.session() as s:
        count = s.run("MATCH (d:Dataset) RETURN count(d) AS c").single()["c"]
    assert count == 2  # raw.orders and clean.orders


def test_write_event_creates_edges(sample_event):
    write_event(sample_event)
    driver = get_neo4j_driver()
    with driver.session() as s:
        produces = s.run("MATCH ()-[r:PRODUCES]->() RETURN count(r) AS c").single()["c"]
        consumes = s.run("MATCH ()-[r:CONSUMES]->() RETURN count(r) AS c").single()["c"]
    assert produces == 1
    assert consumes == 1


def test_pii_propagates_to_output(sample_event):
    # Tag the input dataset as PII
    sample_event.inputs[0].tags = ["pii"]
    write_event(sample_event)

    driver = get_neo4j_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (d:Dataset {uri: 'postgres://clean.orders'}) RETURN d.tags AS tags"
        ).single()
    assert "pii" in result["tags"]


def test_write_event_idempotent(sample_event):
    """Calling write_event twice with the same event should not duplicate nodes."""
    write_event(sample_event)
    write_event(sample_event)
    driver = get_neo4j_driver()
    with driver.session() as s:
        job_count = s.run("MATCH (j:Job) RETURN count(j) AS c").single()["c"]
    assert job_count == 1
```

### Test File: `tests/test_api.py`

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app
from app.storage.graph_writer import write_event

client = TestClient(app)


def test_upstream_returns_404_for_unknown_dataset():
    response = client.get("/lineage/upstream/postgres://nonexistent")
    assert response.status_code == 404


def test_upstream_returns_correct_ancestors(sample_event):
    write_event(sample_event)
    response = client.get("/lineage/upstream/postgres://clean.orders")
    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] >= 2
    uris = [n["properties"].get("uri") for n in body["nodes"]]
    assert "postgres://raw.orders" in uris


def test_runs_returns_empty_list_for_unknown_job():
    response = client.get("/lineage/runs/nonexistent.job")
    assert response.status_code == 200
    assert response.json()["runs"] == []


def test_runs_returns_history(sample_event):
    write_event(sample_event)
    response = client.get("/lineage/runs/test.job")
    assert response.status_code == 200
    assert response.json()["run_count"] == 1
    assert response.json()["runs"][0]["status"] == "COMPLETE"
```

### Test File: `tests/test_parsers.py`

```python
# tests/test_parsers.py
from parsers.sql_parser import parse_sql


def test_simple_insert_select():
    sql = "INSERT INTO clean.orders SELECT * FROM raw.orders WHERE status = 'active'"
    event = parse_sql(sql)
    input_uris = [d.uri for d in event.inputs]
    output_uris = [d.uri for d in event.outputs]
    assert "sql_parser://raw.orders" in input_uris
    assert "sql_parser://clean.orders" in output_uris


def test_cte_not_treated_as_source():
    sql = """
    WITH active_orders AS (SELECT * FROM raw.orders WHERE status = 'active')
    INSERT INTO clean.orders SELECT * FROM active_orders
    """
    event = parse_sql(sql)
    input_uris = [d.uri for d in event.inputs]
    assert "sql_parser://active_orders" not in input_uris
    assert "sql_parser://raw.orders" in input_uris


def test_snowflake_dialect():
    sql = "CREATE TABLE clean.orders AS SELECT * FROM raw.orders"
    event = parse_sql(sql, dialect="snowflake")
    assert any(d.name == "raw.orders" for d in event.inputs)
    assert any(d.name == "clean.orders" for d in event.outputs)
```

### Performance Test: `tests/test_performance.py`

```python
# tests/test_performance.py
import time
from fastapi.testclient import TestClient
from app.main import app
from app.db_client import get_neo4j_driver

client = TestClient(app)


def seed_100k_edges():
    """Seeds a chain of 1000 datasets connected by 999 jobs — ~100k relationships."""
    driver = get_neo4j_driver()
    with driver.session() as s:
        # Create datasets
        s.run("UNWIND range(0, 1000) AS i CREATE (:Dataset {uri: 'test://dataset_' + i, name: 'dataset_' + i, namespace: 'test', tags: []})")
        # Create jobs and edges
        s.run("""
            UNWIND range(0, 999) AS i
            MATCH (src:Dataset {uri: 'test://dataset_' + i})
            MATCH (dst:Dataset {uri: 'test://dataset_' + (i+1)})
            CREATE (j:Job {name: 'job_' + i, owner: '', orchestrator: 'test'})
            CREATE (src)-[:CONSUMES {timestamp: '2024-01-01T00:00:00Z'}]->(j)
            CREATE (j)-[:PRODUCES {timestamp: '2024-01-01T00:01:00Z'}]->(dst)
        """)


def test_upstream_under_2_seconds():
    seed_100k_edges()
    start = time.time()
    response = client.get("/lineage/upstream/test://dataset_999?depth=10")
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 2.0, f"Upstream query took {elapsed:.2f}s — exceeds 2s limit"


def test_downstream_under_2_seconds():
    seed_100k_edges()
    start = time.time()
    response = client.get("/lineage/downstream/test://dataset_0?depth=10")
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 2.0, f"Downstream query took {elapsed:.2f}s — exceeds 2s limit"
```

---

## 12. Success Criteria

These are the measurable outcomes that define project completion. Each maps to the objectives in the original project spec.

| ID | Criterion | Measured by |
|---|---|---|
| O1 | ≥90% of Airflow DAG runs produce a captured event in Neo4j within 60 seconds of completion | Manual verification during pilot DAG run |
| O2 | All 4 API endpoints return correct results in <2 seconds on a graph of up to 100k edges | `tests/test_performance.py` |
| O3 | SQLGlot parser correctly extracts source/target tables from ≥85% of 50 representative SQL scripts | Parser accuracy report |
| O4 | 100% of datasets derived from a PII-tagged source are auto-tagged on ingestion | `test_pii_propagates_to_output` in `test_storage.py` |
| O5 | Docker Compose environment starts cleanly on macOS/Linux in under 3 minutes | Manual check on fresh clone |

---

## 13. What Is Out of Scope

Do not build these in this phase. They are explicitly deferred to Phase 2.

- **Column-level lineage** — we track table-level only. Individual column provenance is Phase 2
- **Authentication / authorisation** — all endpoints are unauthenticated in Phase 1
- **Multi-orchestrator support** — only Airflow is supported. Spark, Flink, etc. are Phase 2
- **AI-powered natural language querying** — no LLM integration in Phase 1
- **Governance policy enforcement** — we propagate PII tags but do not enforce access rules
- **Frontend UI** — pure REST API only, no dashboard
- **Multi-hop historical PII propagation** — PII propagates 1 hop at write time only. Retroactively propagating across existing graph edges is Phase 2
- **Real-time streaming** — events are written synchronously, not via Kafka/Pub-Sub

---

*This document was generated from the project specification (Metadata_Lineage_Engine_Final_doc.docx) and team architecture decisions. It supersedes all previous work division documents and is the single source of truth for building this system.*
