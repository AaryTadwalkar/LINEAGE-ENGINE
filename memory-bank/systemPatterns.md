# System Patterns

## Architecture Overview

```
[Airflow OL] ──┐
[SQL Parser] ──┤── POST /lineage/events ──► Pydantic v2 validate ──► converter.py ──► write_event()
[dbt Parser] ──┘                                                                           │
                                                                                    [Stage 3 - Neo4j + Postgres]
                                                                                           │
                                               GET /lineage/upstream/{id} ◄── Cypher traversal
                                               GET /lineage/downstream/{id} ◄── Cypher traversal
                                               GET /lineage/runs/{job_id} ◄── SQL SELECT
```

## Neo4j Graph Schema

```
(:Job)──[:PRODUCES {timestamp}]──►(:Dataset)
(:Dataset)──[:CONSUMES {timestamp}]──►(:Job)
(:Job)──[:HAS_RUN]──►(:Run)
```

Node properties:
- `Job` — `name`, `owner`, `orchestrator`
- `Dataset` — `namespace`, `name`, `uri`, `tags[]`
- `Run` — `run_id`, `status`, `start_time`, `end_time`

Unique key: `Dataset.uri` = `"{namespace}://{name}"` e.g. `"postgres://clean.orders"`

## Key Design Patterns

### 1. Internal Dataclass Contract (models.py)
All stages import `LineageEvent` from `app/models.py`. Pydantic is NOT used here — plain Python dataclasses only. This decouples the internal format from the web layer.

### 2. Converter Pattern (ingestion/converter.py)
One file knows both "OpenLineage language" and "internal language". After conversion, the rest of the codebase never sees OL field names like `runId`, `nominalTime`, `eventType`.

### 3. Stub-First Development
Stage 2 uses a stub `write_event()` that just logs. Stage 3 replaces the file — the interface never changes. This lets stages develop independently.

### 4. MERGE-Based Idempotency (Stage 3)
All Neo4j writes use `MERGE`, not `CREATE`. Calling `write_event()` twice with the same event creates exactly 1 node, not 2. Safe for retries.

### 5. PostgreSQL as Audit Log
`run_log` table is a separate audit trail, independent of Neo4j. If Postgres write fails, it is logged but not raised — Neo4j is the source of truth for lineage.

### 6. PII Tag Propagation
1-hop only at write time. If input dataset has `pii` tag, output datasets get `pii` tag automatically. Multi-hop retroactive propagation is deferred to Phase 2.

## Interface Contracts (Locked — Do Not Change)

### Contract P2 → P3
```python
# P2 calls this. P3 implements this.
def write_event(event: LineageEvent) -> None: ...
```

### Contract P3 → P4
Neo4j node property names that Cypher queries depend on:
- `Job.name`, `Dataset.uri`, `Run.run_id` (unique MERGE keys)
- Edge types: `PRODUCES`, `CONSUMES`, `HAS_RUN`

## Module Responsibility

| Module | Owns |
|---|---|
| `app/models.py` | Internal dataclasses (shared by all) |
| `app/db_client.py` | DB connection singletons |
| `app/ingestion/` | HTTP validation, OL conversion, POST route |
| `app/storage/` | write_event() — Neo4j + Postgres writes |
| `app/api/` | GET query endpoints + Cypher strings |
| `parsers/` | SQL + dbt static parsers |
