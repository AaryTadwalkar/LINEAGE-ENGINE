# Active Context

## Current Focus
Ready to begin Stage 3 — Storage Layer (real write_event() with Neo4j + Postgres).

## Last Completed
- Stage 2 fully built: pydantic_models, converter, router, sql_parser, dbt_parser, graph_writer stub
- Memory bank created (all 6 core files)
- Full integration test suite run — ALL 13 tests PASSED (exit code 0)
  - HTTP: COMPLETE/FAIL → ok, START → skipped, bad payload → 422
  - SQL parser: INSERT, CTE exclusion, CREATE TABLE AS, JOIN
  - dbt parser: model events, skip non-models, schema prefix
- Test script: `scripts/test_stage2.py`

## Immediate Next Steps
1. Build Stage 3 — replace graph_writer.py stub with real Neo4j + Postgres writes
2. Implement write_event(), _write_graph(), _write_postgres(), _propagate_pii_tags()
3. Test with seed script (`scripts/test_write_event.py`)
4. Verify Neo4j browser shows nodes and edges

## Active Decisions
- `graph_writer.py` is a STUB — logs only. Stage 3 replaces this file entirely.
- The ingestion router skips `START` events by design (no output datasets yet)
- FastAPI runs locally on Windows, DBs run in Docker

## Server State
- uvicorn running at http://localhost:8000
- Docker containers: neo4j + postgres both healthy
- Command: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Important File Paths
```
c:\Rubiscape\lineage-engine\
├── app/
│   ├── main.py               ← mounts ingestion_router + /health
│   ├── models.py             ← LineageEvent dataclass (shared)
│   ├── db_client.py          ← DB connection wrappers
│   ├── ingestion/
│   │   ├── pydantic_models.py  ← OLRunEvent validation
│   │   ├── converter.py        ← OL → LineageEvent
│   │   └── router.py           ← POST /lineage/events
│   └── storage/
│       └── graph_writer.py     ← STUB (replace in Stage 3)
├── parsers/
│   ├── sql_parser.py           ← SQLGlot parser
│   └── dbt_parser.py           ← manifest.json parser
├── docs/
│   ├── lineage_engine_master_build_doc.md  ← source of truth
│   └── current.md              ← what was done each stage
└── memory-bank/                ← this folder
```
