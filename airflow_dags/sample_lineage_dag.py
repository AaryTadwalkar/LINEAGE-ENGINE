from datetime import datetime
from airflow import DAG, Dataset
from airflow.operators.bash import BashOperator

# Define Datasets (Airflow 2.4+ Datasets are natively picked up by OpenLineage)
raw_source = Dataset("postgres://demo_db/raw.source")
staging_extracted = Dataset("postgres://demo_db/staging.extracted")
clean_final = Dataset("postgres://demo_db/clean.final")

with DAG(
    'sample_lineage_dag',
    schedule_interval=None,
    start_date=datetime(2023, 1, 1),
    catchup=False,
    description='A simple DAG to test OpenLineage emission to Lineage Engine',
) as dag:
    
    task1 = BashOperator(
        task_id='extract_data',
        bash_command='echo "Extracting data from raw.source..."',
        inlets=[raw_source],
        outlets=[staging_extracted]
    )

    task2 = BashOperator(
        task_id='transform_data',
        bash_command='echo "Transforming data to clean.final..."',
        inlets=[staging_extracted],
        outlets=[clean_final]
    )

    task1 >> task2
