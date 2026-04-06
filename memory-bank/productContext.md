# Product Context

## The Problem We Solve

Modern data pipelines are invisible. When a dashboard shows wrong numbers, engineers spend days tracing back through dozens of jobs and SQL scripts to find where bad data entered. There is no authoritative record of how data flows through the system.

Specifically:
- Schema changes break downstream jobs and nobody knows which ones
- Model outputs fail and nobody can trace training data origin
- Manual spreadsheet docs get abandoned within weeks
- GDPR/HIPAA require full data traceability — which doesn't exist

## How It Should Work

1. Airflow runs a DAG task → our system **automatically** captures the lineage
2. A developer runs a SQL script → parser **extracts** the table dependencies
3. dbt compiles → manifest is **parsed** for model lineage
4. An engineer calls `GET /lineage/upstream/postgres://clean.orders` → gets the **full ancestry** in JSON

## Three Ingestion Paths

| Path | Source | Trigger |
|---|---|---|
| A — Runtime | Apache Airflow via OpenLineage | After every DAG task completes |
| B — Static SQL | `.sql` files via SQLGlot parser | Manual or scheduled |
| C — Static dbt | `manifest.json` via Python parser | After every `dbt compile` |

## User Experience Goals

- Engineer POSTs an event → gets `{"status": "ok"}` in <100ms
- Engineer calls upstream API → gets full graph in <2s on 100k edge graph
- PII tags automatically propagate to derived datasets
- Zero config for the caller — just send an OpenLineage JSON
