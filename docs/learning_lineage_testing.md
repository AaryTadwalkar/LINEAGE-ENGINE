# Learning Concept: Simulating Pipeline Data for Testing

**Author:** Aary Tadwalkar & AI AGENT
**Topic:** How we test our Metadata Lineage Engine ingestion independently of full-scale workflow orchestrators like Airflow or dbt.

---

### 1. What was the problem?
We have built a powerful backend engine designed to capture and track metadata lineage, but we faced a "chicken-and-egg" barrier: **how do we test an engine that records complex pipeline data when we don't have a real data pipeline running?** 

Deploying a legitimate Apache Airflow environment, orchestrating actual data transformations, and configuring it to emit OpenLineage events takes a lot of time. Waiting for real pipelines to exist would bottleneck our ability to test if our API endpoints, graph nodes processing, and Cypher database querying actually work. 

### 2. Solution
We "mock" or "simulate" the pipeline! Because our engine's entry point is simply a REST API endpoint (`POST /lineage/events`), it operates on a structured contract. The engine explicitly does not care *who* or *what* generates the HTTP requests; all it cares about is that the incoming data payloads conform to the OpenLineage JSON schema format.

Instead of a heavy infrastructure, our solution was to create dummy payloads forming a logical Directed Acyclic Graph (DAG). 

### 3. How we tackled it and what did we use?
**The Logic:**
We manually constructed the anatomy of a believable data workflow:
- **Hop 1:** Extract `orders.csv` from S3 -> Load into Postgres `raw.orders`
- **Hop 2:** Clean Postgres `raw.orders` -> Write to `staging.orders`
- **Hop 3:** Join `staging.orders` with `raw.customers` -> Output into `mart.orders_enriched`
- **Hop 4:** Aggregate `mart.orders_enriched` -> Finalize into `reporting.order_summary`

This creates a realistic chain where some jobs have one input, and some (like Hop 3) have multiple inputs (to test converging node connections in Neo4j).

**The Technology/Stack:**
We built this tester using **our own logic alongside pure Python**, relying heavily on the `httpx` package.
- `httpx`: An elegant HTTP client used to fire synchronous HTTP `POST` requests to our running FastAPI app server. 
- Python `uuid` and `datetime`: Used to generate unique `runIds` and dynamic timestamps automatically, making our testing data distinct with every execution of the script.

By executing the `scripts/seed_dummy_data.py` script, Python plays the "actor" mimicking an enterprise ETL job, injecting a multi-hop lineage graph straight into our system within milliseconds. This grants immediate ability to traverse nodes, ensuring everything from Cypher querying logic to PII tagging propagation works reliably for production readiness!
