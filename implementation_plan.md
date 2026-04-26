# Lineage Engine — Combined Implementation Plan
## Stages 10 UX · 11 Pipelines · 12 RAG

> **No code changes have been made yet. This is a planning document only.**
> Stages execute in strict order. Stage 12 cannot start until Stage 11 is complete.

---

## Part 0 — Screenshot Verification (Is What You See Correct?)

### What you searched for
`duckdb://jaffle_shop/customers` — **Upstream** — Depth 5

### Is the graph correct? ✅ YES

Looking at `pipeline_plugin.py`, here is the expected graph:

```
raw_payments  ──[stg_payments]──► stg_payments ──┐
raw_customers ──[stg_customers]──► stg_customers ──┤──[customers]──► customers
raw_orders    ──[stg_orders]────► stg_orders    ──┘
```

**What you see in the screenshot matches this exactly.** The 3 raw sources fan into 3 staging jobs, then converge into the `customers` job producing the `customers` dataset.

### The extra nodes (`stg_customers_test`, `customers_test`)
You see these nodes in the screenshot:
- `stg_customers_test` (job)
- `customers_test` (job, bottom right)

These are **test artifacts** from `test_stage10.py`. The test seeds two jobs with `_test` suffixes (`stg_customers_test`, `customers_test`) into the **same graph** before the simulator runs. Since the DB is not wiped between the test run and the simulation, test nodes persist alongside real pipeline nodes.

> **Fix (already planned):** The tests should be run with a wipe-before and wipe-after strategy, OR the test script should use a clearly isolated namespace like `duckdb://__test__/...` so test nodes never pollute the real pipeline graph.

### The Column Lineage Screenshot (`stg_customers` selected)
You see:
- `3 COLUMNS: customer_id, first_name, last_name` ✅ Correct (matches `pipeline_plugin.py` stg_customers column_mappings)
- **UPSTREAM SOURCES for `customer_id`:**
  - `id` from `duckdb://jaffle_shop/raw_customers` via `stg_customers_test`
  - `id` from `duckdb://jaffle_shop/raw_customers` via `stg_customers`

The **duplicate `id` entries** are because both `stg_customers` (real job) and `stg_customers_test` (test job) both wrote a `TRANSFORMS` edge from `raw_customers/id → stg_customers/customer_id`. The data is accurate but shows test pollution.

### The "No lineage nodes found" Error (Screenshot 3)
You pressed **Downstream** on the `customers` dataset. `customers` is the **final mart** — it has no downstream consumers in our pipeline. So the result is correct data, just an ugly error banner. This needs a graceful UI treatment.

---

## Part 1 — Stage 10 UX Improvements (Fixes & Enhancements)

These are **4 targeted improvements** to the already-working Stage 10 system.

> **Risk: Zero** — All changes are frontend-only except the test isolation fix.

---

### Fix 1 — Test Isolation (Prevent Test Node Pollution)

**Problem:** `test_stage10.py` uses `duckdb://jaffle_shop` namespace, which pollutes the live demo graph with `_test` suffix nodes.

**Fix:** Change the test namespace to `duckdb://lineage_test` (a completely separate namespace that will never collide with the real Jaffle Shop graph). Every assertion URI in the test file gets updated to match.

| File | Change |
|---|---|
| `scripts/test_stage10.py` | Change `NS = "duckdb://jaffle_shop"` → `NS = "duckdb://lineage_test"` and update all URIs |

The wipe at the start of the test only deletes nodes within the test namespace, not the entire DB. This lets tests run even when the real graph has data.

**Alternative approach:** Add a `namespace: str` parameter to `wipe_db()` that only deletes nodes matching that namespace prefix. The Cypher query becomes:
```cypher
MATCH (n) WHERE n.uri STARTS WITH $prefix DETACH DELETE n
```

---

### Fix 2 — Graceful Empty State (No URI entered → Downstream pressed)

**Problem:** When the search bar has an empty URI and you press Downstream, it does nothing silently (because of `if (uri.trim())` guard). When a URI returns 0 nodes (like `customers` downstream), it shows a harsh red error banner.

**Fix A — Empty URI guard (visible feedback):**
Currently: `SearchBar.jsx` silently does nothing if `uri.trim()` is empty.
Plan: Show an inline validation hint "Please enter a Dataset URI first" styled as a gentle amber warning under the input box. No modal, no disruption. Auto-dismisses when user starts typing.

**Fix B — Zero-result state (not an error):**
Currently: `GraphView.jsx` sets `error('No lineage nodes found...')` which triggers the red error banner.
Plan: Distinguish between "zero results" (a valid, expected state) vs "actual error" (network failure, 404). Zero results shows a centered **informational card** (not red) saying:
> *"No downstream consumers found for `customers`. This dataset is a final destination — nothing reads from it."*

| File | Change |
|---|---|
| `frontend/src/components/SearchBar.jsx` | Add `emptyWarning` state, show amber hint when submit pressed with no URI |
| `frontend/src/pages/GraphView.jsx` | Split `error` state into `error` (real errors) and `emptyResult` (zero nodes). Show different UI for each. |

---

### Fix 3 — Add Downstream to Column Level

**Problem:** `ColumnPanel.jsx` only calls `getColumnImpact` for downstream. But the button says "Impact" not "Downstream". Users don't understand "Impact" = "Downstream".

**Plan:**
1. **Rename "Impact" button to "Downstream"** in `ColumnPanel.jsx` — same API call, clearer label.
2. **Add a count badge** next to each button showing how many columns were found (lazy-loaded after first click).
3. **The `getColumnImpact` API already does downstream traversal** — no backend changes needed.

| File | Change |
|---|---|
| `frontend/src/components/ColumnPanel.jsx` | Rename "Impact" → "Downstream", add count badge |

---

### Fix 4 — Column Graph View (Replace Popup Table with Graph)

**Problem (MAIN UX ask):** The column panel shows columns as a flat list in a side popup. Users want to see column-level lineage **as a graph**, visually consistent with the dataset-level graph.

**Plan — New Route: `/column-graph`**

This is the biggest frontend change in Stage 10 fixes. The idea:

#### New Page: `ColumnGraphView.jsx`
A dedicated full-screen page (same layout as `GraphView.jsx`) that renders column-to-column TRANSFORMS paths as a React Flow graph.

**How to trigger it:**
- In `ColumnPanel.jsx`, clicking a column's "Upstream" or "Downstream" button navigates to `/column-graph?col=<encoded_uri>&mode=upstream`
- Alternatively, a "Open as Graph ↗" button at the top of `ColumnPanel.jsx` opens it for the whole dataset's columns

**How the graph renders:**
- Each **Column node** renders as a small, rounded pill node (different from Dataset/Job nodes)
- Columns are **grouped by their parent Dataset** using React Flow's sub-flow or label grouping
- **TRANSFORMS edges** are drawn as directed arrows with the `via_job` name as edge label
- Color coding:
  - The **selected column** node: bright cyan highlight
  - Columns in the **same dataset**: same color group
  - Columns from **different datasets**: different color group

**Node data structure for React Flow:**
```
{
  id: column_uri,
  type: 'columnNode',        // new custom node type
  data: { name, dataset_uri, is_focal: true/false },
  position: { x, y }         // auto-layout via dagre (already used)
}
```

**Edge data structure:**
```
{
  id: `${src}->${dst}`,
  source: src_col_uri,
  target: dst_col_uri,
  label: via_job_name,
  animated: true
}
```

**API calls used:**
- For the graph: calls `GET /lineage/column-upstream/{uri}` or `GET /lineage/column-impact/{uri}` (existing endpoints, no new backend needed)
- To get all columns of a dataset to show as starting nodes: `GET /lineage/columns/{dataset_uri}` (existing)

**Layout:**
- Uses the existing `dagre` auto-layout from `LineageGraph.jsx`
- Columns from the same dataset are placed in a vertical column group
- TRANSFORMS edges flow left-to-right (upstream → focal → downstream)

**Files:**

| File | Status | Change |
|---|---|---|
| `frontend/src/pages/ColumnGraphView.jsx` | **NEW** | Full page column graph |
| `frontend/src/components/ColumnNode.jsx` | **NEW** | Custom React Flow node for columns |
| `frontend/src/App.jsx` | MODIFY | Add `/column-graph` route |
| `frontend/src/components/ColumnPanel.jsx` | MODIFY | Add "Open as Graph ↗" button, change Impact→Downstream |
| `frontend/src/components/Sidebar.jsx` | No change | Column Graph accessible from within the graph view only |

---

## Part 2 — Stage 11: Modular Pipeline System + data_pipelines Folder

> **Prerequisite:** Stage 10 UX fixes complete.

### User's Intent
> *"I will remove this external project and add a folder named `data_pipelines` as external project with Jaffle and other pipelines"*

This tells us the `data_pipelines/` folder will live **outside the lineage-engine repo** as a separate folder/project. The lineage engine must be able to **point to an external directory** for pipelines, not just its internal `pipelines/` folder.

### Updated Architecture

```
c:\Rubiscape\
├── lineage-engine\          ← our repo (unchanged structure)
│   ├── pipeline_registry.py ← auto-discovers from PIPELINE_DIR (configurable)
│   ├── pipeline_plugin.py   ← backward-compat shim
│   └── ...
│
└── data_pipelines\          ← EXTERNAL folder (user maintains this)
    ├── jaffle_shop.py       ← moved here from pipeline_plugin.py
    ├── ecommerce.py         ← new
    └── financial_etl.py     ← new
```

### How the registry finds the external folder

`pipeline_registry.py` reads the pipeline directory from:
1. **Environment variable** `LINEAGE_PIPELINE_DIR` (highest priority)
2. **`.env` file** entry `LINEAGE_PIPELINE_DIR=C:\Rubiscape\data_pipelines`
3. **Fallback:** `./pipelines/` inside the repo (for backward compat)

This means to switch to the external folder, the user just adds one line to `.env`:
```
LINEAGE_PIPELINE_DIR=C:\Rubiscape\data_pipelines
```

### Files

| File | Status | Change |
|---|---|---|
| `pipeline_registry.py` | **NEW** | Auto-discover from configurable dir |
| `pipeline_plugin.py` | MODIFY | Becomes a shim (imports from registry) |
| `.env` | MODIFY | Add `LINEAGE_PIPELINE_DIR` entry |
| `run_live_demo.py` | MODIFY | `argparse` for `--pipeline`, `--list-pipelines` |
| `app/api/config_router.py` | **NEW** | `GET /config/pipelines` endpoint |
| `app/main.py` | MODIFY | Mount config_router |
| `frontend/src/pages/ConfigView.jsx` | **NEW** | Pipeline selector + API URL config page |
| `frontend/src/components/Sidebar.jsx` | MODIFY | Add Config nav + pipeline badge |
| `frontend/src/App.jsx` | MODIFY | Add `/config` route |
| `frontend/src/api/lineageApi.js` | MODIFY | Dynamic baseURL from localStorage |
| `scripts/test_stage11.py` | **NEW** | Registry + API + CLI tests |

> Full implementation details for Stage 11 are already in `implementation_plan-stage-10-11` file. The only **new addition** from this session is the external `data_pipelines/` folder design via env var — that's a one-line change to `pipeline_registry.py`.

---

## Part 3 — Stage 12: RAG-Powered Natural Language Lineage Q&A

> **Prerequisite:** Stage 11 complete.
> **No code changes — developer-level plan only.**

### Goal
Allow users to ask questions about their data lineage in **plain English** and get accurate, grounded answers backed by the actual graph data.

**Example questions:**
> "Where does `customers.lifetime_value` come from?"
> "If I drop the `raw_orders.user_id` column, what breaks?"
> "Which datasets contain PII?"
> "What jobs ran in the last hour?"

---

### Architecture Overview

```
User Question
     │
     ▼
[Query Understanding Layer]     ← LLM (GPT-4o / Gemini) — classifies intent
     │
     ▼
[Context Retrieval Layer]       ← Structured Neo4j queries (NOT vector search)
     │                            + Optional: Postgres run log queries
     ▼
[Context Assembly Layer]        ← Formats Neo4j results into a text context
     │
     ▼
[Answer Generation Layer]       ← LLM with context → final answer
     │
     ▼
[Response + Sources]            ← Answer + citations (which nodes/edges used)
```

This is **Graph-Grounded RAG** (Retrieval Augmented Generation). The retrieval is from the **live Neo4j graph** — not from a vector DB or embedded documents. This makes answers always up-to-date.

---

### Layer 1 — Query Understanding

**Input:** Raw user question string
**Output:** Structured intent + extracted entities

The LLM is given a system prompt explaining the graph schema and asked to return a JSON:
```json
{
  "intent": "column_upstream",
  "entities": {
    "column": "customers.lifetime_value",
    "dataset": "customers"
  },
  "confidence": 0.95
}
```

**Supported intents:**
| Intent | Example question |
|---|---|
| `column_upstream` | "Where does column X come from?" |
| `column_impact` | "What breaks if I change column X?" |
| `dataset_upstream` | "What feeds into dataset X?" |
| `dataset_downstream` | "What depends on dataset X?" |
| `pii_audit` | "Which datasets have PII?" |
| `run_history` | "When did job X last run?" |
| `general` | Free-form — fallback to graph summary |

---

### Layer 2 — Context Retrieval

Each intent maps to **specific, pre-written Cypher queries** (NOT dynamic LLM-generated Cypher — too risky/unreliable):

| Intent | Cypher query called |
|---|---|
| `column_upstream` | Existing: `GET /lineage/column-upstream/{uri}` |
| `column_impact` | Existing: `GET /lineage/column-impact/{uri}` |
| `dataset_upstream` | Existing: `GET /lineage/upstream/{uri}` |
| `dataset_downstream` | Existing: `GET /lineage/downstream/{uri}` |
| `pii_audit` | `MATCH (d:Dataset) WHERE 'pii' IN d.tags RETURN d` |
| `run_history` | Postgres: `SELECT * FROM run_log WHERE job_name = $name ORDER BY start_time DESC LIMIT 10` |
| `general` | Summary: count of all nodes/edges, list of all datasets |

The retrieved data is passed back as **structured JSON** (the existing API response format).

---

### Layer 3 — Context Assembly

The structured JSON from Neo4j is converted to a **human-readable text block** that the LLM can understand:

```
=== LINEAGE CONTEXT ===
You asked about the upstream of column: duckdb://jaffle_shop/customers/lifetime_value

UPSTREAM CHAIN:
  1. Column: amount  |  Dataset: stg_payments  |  Via job: customers
  2. Column: amount  |  Dataset: raw_payments   |  Via job: stg_payments

This column flows from raw_payments.amount → stg_payments.amount → customers.lifetime_value
through 2 transformation jobs.
======================
```

---

### Layer 4 — Answer Generation

The assembled context + original question + system prompt → LLM → final answer.

**System prompt structure:**
```
You are a data lineage assistant for a Metadata Lineage Engine.
You have access to the actual graph data below. 
Answer the user's question using ONLY the provided context.
If the context does not contain enough information, say so clearly.
Never invent dataset names, column names, or job names.

SCHEMA REMINDER:
- Datasets are data tables/files
- Jobs are transformation steps (dbt models, Airflow tasks)
- Columns belong to Datasets
- TRANSFORMS edges connect columns through jobs

[CONTEXT BLOCK]
```

---

### New Files for Stage 12

| File | Purpose |
|---|---|
| `app/rag/intent_classifier.py` | Sends question to LLM, returns structured intent JSON |
| `app/rag/context_retriever.py` | Maps intent → Cypher/API call → raw data |
| `app/rag/context_assembler.py` | Converts raw data → human-readable text block |
| `app/rag/answer_generator.py` | Sends context + question to LLM → final answer |
| `app/rag/rag_engine.py` | Orchestrates all 4 layers end-to-end |
| `app/api/rag_router.py` | `POST /lineage/ask` endpoint |
| `frontend/src/pages/AskView.jsx` | New page: chat-style Q&A interface |
| `frontend/src/components/ChatBubble.jsx` | Individual message component |
| `frontend/src/components/SourceCard.jsx` | Shows which graph nodes backed the answer |
| `scripts/test_stage12.py` | Integration test: 5 sample questions with expected answer patterns |

---

### New API Endpoint: `POST /lineage/ask`

```
Request:
{
  "question": "Where does customers.lifetime_value come from?",
  "session_id": "abc123"   // optional, for conversation history
}

Response:
{
  "answer": "The `lifetime_value` column in the `customers` dataset originates from `raw_payments.amount`. It flows through two transformation jobs: first `stg_payments` maps `raw_payments.amount` → `stg_payments.amount`, then the `customers` job maps `stg_payments.amount` → `customers.lifetime_value`.",
  "intent": "column_upstream",
  "confidence": 0.95,
  "sources": [
    { "type": "column", "uri": "duckdb://jaffle_shop/customers/lifetime_value" },
    { "type": "column", "uri": "duckdb://jaffle_shop/stg_payments/amount" },
    { "type": "column", "uri": "duckdb://jaffle_shop/raw_payments/amount" }
  ],
  "context_used": "..."    // optional debug field
}
```

---

### LLM Provider Strategy

The LLM provider is **swappable via environment variable** `LINEAGE_LLM_PROVIDER`:
- `openai` → uses `openai` Python SDK (GPT-4o-mini for classify, GPT-4o for answer)
- `google` → uses `google-generativeai` SDK (Gemini Flash for classify, Gemini Pro for answer)
- `local` → uses `ollama` HTTP API (Llama 3.1 8B) — no API key required, runs on-device

Default: `local` (zero cost, works offline) with `openai` as production upgrade path.

---

### Frontend — New "Ask" Page

```
┌────────────────────────────────────────────────────────────────┐
│  🤖  Ask about your lineage                                     │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  [YOU]                                                           │
│  Where does customers.lifetime_value come from?                  │
│                                                                  │
│  [LINEAGE AI]                                                    │
│  The lifetime_value column originates from raw_payments.amount   │
│  flowing through 2 jobs: stg_payments → customers.               │
│                                                                  │
│  SOURCES USED:                                                   │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ 📊 raw_payments  │→ │ 📊 stg_payments  │→ customers          │
│  └──────────────────┘  └──────────────────┘                     │
│                                                                  │
│  ┌────────────────────────────────────┐  [Ask]                  │
│  │ Type your question here...         │                          │
│  └────────────────────────────────────┘                         │
└────────────────────────────────────────────────────────────────┘
```

---

### Stage 12 — Implementation Order

```
Backend (in order):
  1. .env               → Add LINEAGE_LLM_PROVIDER, OPENAI_API_KEY / GOOGLE_API_KEY
  2. requirements.txt   → Add openai, google-generativeai, ollama (optional)
  3. app/rag/intent_classifier.py   → LLM intent detection
  4. app/rag/context_retriever.py   → intent → Neo4j/Postgres queries
  5. app/rag/context_assembler.py   → raw data → readable text
  6. app/rag/answer_generator.py    → context + question → LLM answer
  7. app/rag/rag_engine.py          → orchestrate all 4 layers
  8. app/api/rag_router.py          → POST /lineage/ask
  9. app/main.py                    → mount rag_router
  10. scripts/test_stage12.py       → 5 question integration tests

Frontend (in order):
  11. frontend/src/components/ChatBubble.jsx  → message component
  12. frontend/src/components/SourceCard.jsx  → sources display
  13. frontend/src/pages/AskView.jsx          → full Q&A page
  14. frontend/src/components/Sidebar.jsx     → add "Ask AI" nav item
  15. frontend/src/App.jsx                    → add /ask route
```

---

## Open Questions for User Review

> [!IMPORTANT]
> **Q1 — Column Graph:** When you click "Open as Graph" for a column, should it show:
> - (A) Only the selected column and its 1-hop neighbours (fast, focused), or
> - (B) The entire column lineage for that dataset (all columns and all their TRANSFORMS paths)?

> [!IMPORTANT]
> **Q2 — Test Namespace:** Should the test isolation fix change the test namespace to `duckdb://lineage_test` (completely separate), or should the demo wipe the entire DB before running the simulation (simpler but loses any manually added data)?

> [!IMPORTANT]
> **Q3 — data_pipelines folder:** Will the `data_pipelines/` folder always be at a **fixed absolute path** (e.g. `C:\Rubiscape\data_pipelines`) or should the lineage engine prompt for it on startup? The `.env` approach is recommended.

> [!IMPORTANT]
> **Q4 — RAG LLM:** Do you have an OpenAI or Google API key, or should Stage 12 default to `ollama` (local LLM, free, no internet needed)? This affects `requirements.txt`.

> [!NOTE]
> **Q5 — Stage 11 timing:** Do you want to do the Stage 10 UX fixes (Fix 1-4) first as a mini-sprint, then Stage 11, then Stage 12? Or do you want Stage 10 fixes bundled into Stage 11?
