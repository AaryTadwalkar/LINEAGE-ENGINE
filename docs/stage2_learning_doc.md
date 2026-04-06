# Stage 2 — Ingestion Layer: What We Used and Why

## 1. What Was The Problem

We needed the system to **receive lineage events** from 3 different sources:
- **Airflow** — sends JSON in OpenLineage format via HTTP POST
- **SQL files** — `.sql` scripts that have table names hidden inside SQL syntax
- **dbt** — a `manifest.json` file that describes model dependencies

Each source speaks a different "language". We needed one frontend door that could accept all of them and convert to a single internal format.

---

## 2. The Solution

Build an **Ingestion Layer** — a set of modules that:
1. Accept raw input (JSON, SQL string, manifest file)
2. **Validate** it (reject garbage before it touches the database)
3. **Convert** it to one internal format (`LineageEvent`)
4. Hand it off to Stage 3 to write to the database

---

## 3. How We Tackled It — File by File

### File 1: `app/ingestion/pydantic_models.py`
**Technology: Pydantic v2**

**Problem:** Airflow POSTs a big nested JSON. If any field is missing or wrong type, we must reject it before any database write happens.

**Solution:** We defined Python classes that describe the exact shape of the JSON:
```python
class OLRunEvent(BaseModel):
    eventType: str        # must be a string
    eventTime: datetime   # auto-parsed from ISO string
    run: OLRun            # nested object
    job: OLJob
    inputs: list[OLDataset]
    outputs: list[OLDataset]
```
FastAPI automatically calls Pydantic validation on every incoming request. Bad JSON → **422 error, no database touched**.

**Key trick:** `model_config = {"extra": "allow"}` — OpenLineage has dozens of optional fields. We don't crash on fields we don't know, we just ignore them.

---

### File 2: `app/ingestion/converter.py`
**Technology: Pure Python logic**

**Problem:** Airflow uses field names like `runId`, `nominalTime`, `eventType`. Our internal system uses `run_id`, `start_time`, `status`. We cannot mix these up across the codebase.

**Solution:** One single file that knows both languages and translates between them:
```python
def ol_event_to_lineage_event(event: OLRunEvent) -> LineageEvent:
    ...
```
After this function runs, the rest of the code never sees `runId` or `nominalTime` again. **Isolation principle** — one translator, everyone else speaks the internal language.

---

### File 3: `app/ingestion/router.py`
**Technology: FastAPI APIRouter**

**Problem:** We need a `POST /lineage/events` HTTP endpoint.

**Solution:** FastAPI's `APIRouter` — we define the route, declare what type it accepts (`OLRunEvent`), and FastAPI handles all the HTTP plumbing automatically. Swagger docs are generated for free.

**Key logic decision:** We skip `START` events:
```python
if event.eventType not in ("COMPLETE", "FAIL"):
    return {"status": "skipped", ...}
```
Why? A START event fires when a job begins — there are no output datasets yet. Nothing useful to store.

---

### File 4: `app/storage/graph_writer.py` (STUB)
**Technology: Logging only**

**Problem:** Stage 3 (the real database writer) doesn't exist yet. Stage 2 needs to be able to run and prove it works **right now**, without waiting.

**Solution:** A stub — a fake `write_event()` that just logs what it received:
```python
def write_event(event: LineageEvent) -> None:
    logger.info(f"[STUB] job={event.job.name}")
```
Stage 3 will **replace** this file with real Neo4j + Postgres writes. The interface (`write_event(event)`) never changes — Stage 2 doesn't need to know.

**Pattern used:** Dependency Inversion — Stage 2 depends on an *interface*, not an *implementation*.

---

### File 5: `parsers/sql_parser.py`
**Technology: SQLGlot**

**Problem:** A `.sql` file like:
```sql
WITH active AS (SELECT * FROM raw.orders WHERE status = 'active')
INSERT INTO clean.orders SELECT * FROM active
```
We need to know: "this job reads from `raw.orders` and writes to `clean.orders`". But `active` is a CTE — an intermediate name, not a real table in the database.

**Solution:** SQLGlot parses SQL into an **AST (Abstract Syntax Tree)** — a tree structure that represents the SQL logically. We then walk the tree:
1. Collect CTE names → exclude them
2. Find `INSERT INTO` / `CREATE TABLE AS` → those are **outputs**
3. Find all other `Table` references → those are **inputs**

```python
statements = sqlglot.parse(sql, dialect="postgres")
for statement in statements:
    for cte in statement.find_all(exp.CTE): ...
    for insert in statement.find_all(exp.Insert): ...
```

**Why SQLGlot?** No external service needed. Works offline. Supports both PostgreSQL and Snowflake dialects. 0 extra dependencies beyond the package.

---

### File 6: `parsers/dbt_parser.py`
**Technology: Python `json` module (built-in)**

**Problem:** dbt generates a `manifest.json` after every `dbt compile`. It contains a map of every model and what other models it depends on. We need to extract those as lineage edges.

**Solution:** Load the JSON, iterate nodes, filter for `resource_type == "model"`, and for each dependency create a `LineageEvent`:
```python
for dep_node_id in depends_on_nodes:
    dep_name = dep_node_id.split(".")[-1]  # "model.project.orders_raw" → "orders_raw"
    events.append(LineageEvent(...))
```
One dependency = one event. If model A depends on B and C = 2 events.

---

### `app/main.py` — The Update
**Added two lines:**
```python
from app.ingestion.router import router as ingestion_router
app.include_router(ingestion_router)
```
This mounts the route. Before this, the router file existed but nothing connected it to the running server.

---

## 4. The Flow (End to End)

```
Airflow POST JSON
      ↓
FastAPI receives it
      ↓
Pydantic v2 validates it (422 if bad)
      ↓
converter.py translates OL fields → LineageEvent
      ↓
router.py calls write_event(lineage_event)
      ↓
graph_writer.py [STUB] logs it
      ↓
Returns {"status": "ok"}
```

---

## 5. Verification

- `http://localhost:8000/docs` → Swagger UI shows **POST /lineage/events** under "ingestion" tag ✅
- `http://localhost:8000/health` → `{"status":"healthy","neo4j":"ok","postgres":"ok"}` ✅
- No import errors on server startup ✅
