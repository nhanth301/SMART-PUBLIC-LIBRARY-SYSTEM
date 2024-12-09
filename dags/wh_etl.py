from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
import psycopg2
import os

PG_DB = os.getenv('POSTGRES_DB')
PG_USER = os.getenv('POSTGRES_USER')
PG_PASS = os.getenv('POSTGRES_PASSWORD')
PG_HOST = os.getenv('POSTGRES_HOST')
PG_PORT = os.getenv('POSTGRES_INTERNAL_PORT')


# DAG definition
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 9, 8),
    'execution_timeout': timedelta(minutes=10),  
}

dag = DAG(
    'warehouse_etl',
    default_args=default_args,
    description='ETL DataWarehouse',
    schedule_interval=None, 
)


dw_ingest_task = PostgresOperator(
    postgres_conn_id = 'my_postgres',
    task_id = 'DW_ingest',
    sql="""
    INSERT INTO Fact_User_Interaction (sessionID, userID, bookID, actionID, timeID, created_at)
    SELECT 
        ui.sid,
        ui.uid,
        ui.bid,
        get_action_id(ui.action),
        get_time_id(ui.timestamp),
        to_timestamp(ui.timestamp)
    FROM ui_history ui
    WHERE NOT EXISTS (
        SELECT 1 
        FROM Fact_User_Interaction fi 
        WHERE fi.sessionID = ui.sid 
        AND fi.userID = ui.uid 
        AND fi.bookID = ui.bid 
        AND fi.created_at = to_timestamp(ui.timestamp)
    );

    -- Migrate recommendation history data
    INSERT INTO Fact_Recommendation (sessionID, userID, bookID, timeID, created_at)
    SELECT 
        rh.sid,
        rh.uid,
        rh.bid,
        get_time_id(rh.timestamp),
        to_timestamp(rh.timestamp)
    FROM rec_history rh
    WHERE NOT EXISTS (
        SELECT 1 
        FROM Fact_Recommendation fr 
        WHERE fr.sessionID = rh.sid 
        AND fr.userID = rh.uid 
        AND fr.bookID = rh.bid 
        AND fr.created_at = to_timestamp(rh.timestamp)
    );
    """,
    dag=dag
)

dw_ingest_task