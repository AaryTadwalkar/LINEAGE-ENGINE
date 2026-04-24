# Concept Review: Brittle Container Name Health Checks vs. Application-Level Readiness

## 1. What was the problem?
When attempting to run `python run_live_demo.py`, the orchestrator script aborted with the error `Neo4j never became healthy`. 

The script was trying to poll Docker directly using the command `docker inspect --format "{{.State.Health.Status}}" container_name` to see if Neo4j was ready. However, the script was hardcoding the container names as `lineage-engine-neo4j-1` and `lineage-engine_neo4j_1`. 

Because Docker Compose's naming conventions change depending on the OS, the version of Docker Desktop, and the project directory name, these hardcoded names were incorrect on your system. Docker couldn't find the container by that exact name, returning an empty or unhealthy state, which caused the orchestrator to fail even though Neo4j was actually starting up fine.

## 2. Solution
We removed the direct `docker inspect` health check logic (`_wait_for_docker_healthy`) entirely from `run_live_demo.py`. Instead, we rely entirely on the FastAPI application's `/health` endpoint (`_wait_for_api`) to tell us when the backend stack is fully initialized.

## 3. How we tackled it and what did we use?
**Approach (Our Own Logic & FastAPI):**
Rather than interrogating the infrastructure (Docker) about the state of the databases, we interrogate the application itself.

1. **The Old Way (Brittle):** 
   - Ask Docker: "Is a container named exactly 'lineage-engine-neo4j-1' healthy?"
   - *Failure point:* If the container is named `lineage-engine-neo4j-1-XYZ`, Docker says "No", and the script dies.
2. **The New Way (Robust Application-Level Check):** 
   - The script pings the FastAPI backend at `http://localhost:8000/health`.
   - FastAPI inherently tries to connect to Neo4j and PostgreSQL internally (via `db_client.py`).
   - If FastAPI can successfully execute a test query, it returns `{"status": "healthy"}`.
   - The script waits until FastAPI returns this healthy status.

This delegates the responsibility of knowing "Are the databases ready?" to the backend application itself, which is independent of what Docker decides to name its containers!
