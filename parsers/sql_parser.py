import sqlglot
import sqlglot.expressions as exp
from app.models import LineageEvent, JobRef, RunRef, DatasetRef
from datetime import datetime, timezone
import uuid
import os


def _normalise_table_name(table_expr) -> str:
    """
    Normalise multi-part table names.
    schema.table  →  schema.table
    table         →  table
    """
    parts = []
    if hasattr(table_expr, 'db') and table_expr.db:
        parts.append(table_expr.db.lower())
    parts.append(table_expr.name.lower())
    return ".".join(p for p in parts if p)


def parse_sql(sql: str, dialect: str = "postgres",
              job_name: str = "sql_script") -> LineageEvent:
    """
    Parses a SQL string and returns a LineageEvent.

    Extracts:
    - source tables: FROM clause, JOIN clauses
    - target tables: INSERT INTO, CREATE TABLE AS

    CTEs are identified and excluded from source tables —
    they are intermediate, not real dataset references.

    Args:
        sql:      Raw SQL string (SELECT, INSERT, CREATE TABLE AS, etc.)
        dialect:  "postgres" or "snowflake"
        job_name: Name for the job node. Defaults to "sql_script".

    Returns:
        LineageEvent with inputs (source tables) and outputs (target tables).

    Raises:
        ValueError: If SQLGlot cannot parse the SQL.
    """
    try:
        statements = sqlglot.parse(sql, dialect=dialect)
    except Exception as e:
        raise ValueError(f"SQLGlot could not parse SQL: {e}")

    source_tables: set[str] = set()
    target_tables: set[str] = set()
    cte_names: set[str] = set()

    for statement in statements:
        if statement is None:
            continue

        # Collect CTE names — these are NOT real tables
        for cte in statement.find_all(exp.CTE):
            if cte.alias:
                cte_names.add(cte.alias.lower())

        # Target tables: INSERT INTO
        for insert in statement.find_all(exp.Insert):
            if insert.this and isinstance(insert.this, exp.Table):
                target_tables.add(_normalise_table_name(insert.this))

        # Target tables: CREATE TABLE AS SELECT
        for create in statement.find_all(exp.Create):
            if create.this and isinstance(create.this, exp.Table):
                target_tables.add(_normalise_table_name(create.this))

        # Source tables: all table references not in CTEs or targets
        for table in statement.find_all(exp.Table):
            name = _normalise_table_name(table)
            if name and name not in cte_names and name not in target_tables:
                source_tables.add(name)

    # Remove targets from sources (handles self-join edge case)
    source_tables -= target_tables

    ns = "sql_parser"
    return LineageEvent(
        job=JobRef(name=job_name, owner="", orchestrator="sql_script"),
        run=RunRef(
            run_id=str(uuid.uuid4()),
            status="COMPLETE",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        inputs=[
            DatasetRef(namespace=ns, name=t, uri=f"{ns}://{t}")
            for t in sorted(source_tables)
        ],
        outputs=[
            DatasetRef(namespace=ns, name=t, uri=f"{ns}://{t}")
            for t in sorted(target_tables)
        ],
        event_time=datetime.now(timezone.utc),
    )


def parse_sql_file(filepath: str, dialect: str = "postgres") -> LineageEvent:
    """Convenience wrapper — reads a .sql file and calls parse_sql()."""
    with open(filepath, "r") as f:
        sql = f.read()
    job_name = os.path.basename(filepath).replace(".sql", "")
    return parse_sql(sql, dialect=dialect, job_name=job_name)
