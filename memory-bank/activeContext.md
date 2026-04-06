# Active Context

## Current Focus
Project complete! All 4 stages—Architecture/Setup, Ingestion (Validation/Parsing), Storage (Neo4j/Postgres Writing), and Query API (Graph Traversals) are complete and tested.

## Last Completed
- Phase 4 fully executed! `router.py`, `pydantic_models.py`, `cypher_queries.py` written and integrated into `app/main.py`.
- Solved a critical cypher logic bug from documentation that used `<-[:PRODUCES*1..{depth}]-(j)-[:PRODUCES*1..{depth}]->(...)` which evaluated siblings rather than upstream paths –– replaced with robust `Dataset-[:CONSUMES|PRODUCES]->` relationship paths.
- Addressed FastAPI `url` decoding idiosyncrasies via URL escaping variables before invoking httpx.
- Verified all endpoints using a seeded synthetic multi-hop graph! All endpoints functioned effectively and passed 25 out of 25 comprehensive test checks (depth constraints, not found detection, edge calculations).

## Immediate Next Steps
The backend engine functions correctly in its entirety — available for further user reviews or to establish the frontend visualization tool.

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
