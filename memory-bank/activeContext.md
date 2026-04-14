# Active Context

## Current Focus
All critical bugs are fixed. System should now show live-updating graph with proper edge labels.

## Last Completed
- **Bug fix**: `/lineage/runs/global` route moved BEFORE `/runs/{job_id:path}` — FastAPI was treating "global" as a job_id.
- **Bug fix**: Edge duplicate keys resolved — now use `source-type-target` key with index fallback.
- **Feature**: Edge labels added — PRODUCES (green), CONSUMES (orange) with color-coded arrows.
- **Feature**: GraphView now auto-polls every 4 seconds silently — graph grows live as simulator emits events.
- **Feature**: Upstream/Downstream explanation panel added to the workbench empty state.
- **Fix**: `datetime.utcnow()` deprecation replaced with `datetime.now(timezone.utc)`.

## Immediate Next Steps
- Stop old terminal, run `python run_live_demo.py` fresh.
- Click "Try Simulator Default Pipeline" — watch graph build node-by-node every 4 seconds.

## Immediate Next Steps
- Run `python run_live_demo.py` from a fresh terminal.
- After simulation completes (~15s), click 'Try Demo Pipeline' on the dashboard — the full Jaffle Shop DAG should appear.

## Immediate Next Steps
- Execute `python run_live_demo.py` locally and ensure aesthetic alignment with the simulated graph pipeline!
- Continue testing Neo4j queries under live stress conditions.

## Active Decisions
- A lineage "hop" (Dataset to Dataset) counts as `depth=1` from the API user's perspective, but internally the pipeline traverses `2` edges (from Dataset->Job->Dataset), ensuring queries calculate traversing depth correctly!
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
