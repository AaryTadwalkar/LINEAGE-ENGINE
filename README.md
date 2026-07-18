# 🕸️ Lineage Engine

![Lineage Engine Banner](https://img.shields.io/badge/Status-Active-brightgreen)
![Python FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)
![React Vite](https://img.shields.io/badge/Frontend-React_Vite-61DAFB?logo=react&logoColor=black)
![Neo4j](https://img.shields.io/badge/Database-Neo4j-018bff?logo=neo4j&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql&logoColor=white)

**Lineage Engine** is a high-performance, enterprise-grade metadata lineage tracking system. It visualizes, tracks, and audits data flows and relationships across datasets, pipelines, and transformation jobs. By leveraging a powerful graph-based architecture, it maps precisely how data moves from source to destination, providing critical observability for modern data stacks.

<p align="center">
  <img src="images/Screenshot%202026-07-18%20232650.png" alt="Lineage Engine Dashboard" width="850"/>
</p>

---

## ✨ Key Features

- **Interactive Lineage Graphs**: Visualizes complex data pipelines as interactive Directed Acyclic Graphs (DAGs) for intuitive navigation and debugging.
  
  <p align="center">
    <img src="images/Screenshot%202026-07-18%20232729.png" alt="Interactive Lineage Graph" width="750"/>
  </p>
- **Column-Level Lineage**: Traces column-to-column transformations, allowing data engineers to pinpoint the exact origin of a metric or analyze downstream impact before making schema changes.
- **Robust Pipeline Integration**: Natively supports integration with industry-standard data orchestration tools, including **dbt** and **Apache Airflow**, utilizing the OpenLineage standard.
- **Real-Time Graph Traversal**: Powered by Neo4j, enabling rapid graph traversal to compute upstream dependencies and downstream impacts instantly.

## 🛠️ Technology Stack

Our architecture is built on a modern, scalable stack designed for performance and extensibility:

- **Frontend**: React, Vite, Tailwind CSS, React Flow (for advanced node-based graph rendering)
- **Backend**: Python, FastAPI (High-performance asynchronous API)
- **Graph Database**: Neo4j (Optimized for deep traversal of data relationships)
- **Relational Database**: PostgreSQL (Persistent storage for operational logs and configurations)
- **Infrastructure & Orchestration**: Docker, Docker Compose, Apache Airflow

## 📂 Project Structure

```text
LINEAGE-ENGINE/
├── app/               # FastAPI backend service
├── frontend/          # React web application
├── infra/             # Infrastructure initialization (Postgres schema scripts)
├── scripts/           # Testing, data simulation, and seeding scripts
├── airflow_dags/      # Example Airflow DAGs for OpenLineage integration
└── docker-compose.yml # Containerized local infrastructure configuration
```

## 🚀 Getting Started

Follow these steps to set up the Lineage Engine locally for development or evaluation.

### 1. Start the Infrastructure
Spin up the core infrastructure, including Neo4j, PostgreSQL, and Airflow, using Docker Compose:
```bash
docker-compose up -d
```

### 2. Launch the Backend API
Navigate to the root directory, install the required Python dependencies, and boot up the FastAPI server:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
> **Note**: Ensure your `.env` file is properly configured with your database credentials before starting the server.

### 3. Run the Web Application
In a new terminal window, install the Node modules and start the Vite development server:
```bash
cd frontend
npm install
npm run dev
```

### 4. Access and Test the Engine
- Open your browser and navigate to `http://localhost:5173` to view the interactive UI.
- To seed the Neo4j graph with sample pipelines and data, run the live demo script from the project root:
  ```bash
  python run_live_demo.py
  ```

## 🧪 Testing

The project includes a comprehensive suite of tests to validate graph logic and data integrity. Run tests using:

```bash
python scripts/test_stage10.py
```

## 📖 Architecture & Documentation

For an in-depth look at our roadmap, architectural decisions, and ongoing feature developments (such as RAG integration and advanced UX improvements), please refer to the [Implementation Plan](implementation_plan.md).

---

### 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to submit a pull request or open an issue.

### 📄 License
This project is licensed under the MIT License.
