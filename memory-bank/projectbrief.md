# Project Brief — Metadata Capture & Lineage Engine

## What We Are Building

A **backend system** that automatically records every data movement in a graph database and makes that graph queryable via a REST API.

When Airflow finishes a task that reads from `raw.orders` and writes to `clean.orders`, our system records:
- A `Job` node for the Airflow task
- Two `Dataset` nodes (`raw.orders`, `clean.orders`)
- A `CONSUMES` edge (dataset → job)
- A `PRODUCES` edge (job → dataset)
- A `Run` node with timestamps and status

## Core Deliverable

4 REST API endpoints:
| Endpoint | What |
|---|---|
| `POST /lineage/events` | Ingest a lineage event (from Airflow/parsers) |
| `GET /lineage/upstream/{dataset_id}` | Full ancestry of a dataset |
| `GET /lineage/downstream/{dataset_id}` | Everything downstream of a dataset |
| `GET /lineage/runs/{job_id}` | Run history for a job |

## What This System Is NOT
- Not a data pipeline — it watches pipelines
- Not a frontend — pure REST API backend
- Not an Airflow replacement — we instrument it

## Source Document
`docs/lineage_engine_master_build_doc.md` — the single source of truth.
