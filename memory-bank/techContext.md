# Tech Context

## Stack — Pinned Versions

| Component | Technology | Version |
|---|---|---|
| Language | Python | **3.13** (planned 3.11, actual 3.13 — works fine) |
| Web framework | FastAPI | 0.115.0 |
| ASGI server | uvicorn | 0.29.0 |
| Data validation | Pydantic | >=2.9.0 (v2) |
| Graph database | Neo4j Community | 5.15.0 |
| Neo4j Python driver | neo4j | 5.19.0 |
| Relational database | PostgreSQL | 15.6 |
| Postgres Python driver | psycopg2 | 2.9.11 (**NOT** psycopg2-binary — binary fails on Windows) |
| SQL parser | SQLGlot | 23.12.2 |
| Testing | pytest | 8.2.0 |
| Integration testing | testcontainers | 4.4.0 |
| HTTP test client | httpx | 0.27.0 |
| Env loader | python-dotenv | 1.0.1 |

## Requirements.txt (actual installed)

```
fastapi==0.115.0
uvicorn==0.29.0
pydantic>=2.9.0
neo4j==5.19.0
psycopg2==2.9.11
sqlglot==23.12.2
pytest==8.2.0
testcontainers==4.4.0
httpx==0.27.0
python-dotenv==1.0.1
```

## Infrastructure

- **Docker Compose** runs Neo4j + PostgreSQL only
- **FastAPI runs locally** (not in Docker) — easier dev, hot reload works on Windows
- Databases use `localhost` URIs in `.env` (not Docker service names)

## .env Values (local dev)

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=lineage_password
POSTGRES_DSN=postgresql://lineage_user:lineage_password@localhost:5432/lineage_db
```

## How to Start Each Session

```powershell
# Terminal 1 — databases
cd C:\Rubiscape\lineage-engine
docker compose up -d

# Terminal 2 — API server
cd C:\Rubiscape\lineage-engine
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## URLs

| What | URL |
|---|---|
| FastAPI app | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Neo4j browser | http://localhost:7474 |
| PostgreSQL | port 5432 |

## Windows-Specific Gotchas

- Use `psycopg2` not `psycopg2-binary` (binary won't compile on Windows)
- Install with `pip install -r requirements.txt --prefer-binary`
- Python 3.13 works despite docs saying 3.11
