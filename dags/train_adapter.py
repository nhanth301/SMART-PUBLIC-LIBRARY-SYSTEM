from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
import psycopg2
import os
import pandas as pd
from psycopg2.extras import Json
from src.adapter import train_linear_adapter
# Configuration
HOST = os.getenv('HOST')
SQLITE_DB_PATH = os.getenv('CALIBRE_DB_PATH')
PG_DB = os.getenv('POSTGRES_DB')
PG_USER = os.getenv('POSTGRES_USER')
PG_PASS = os.getenv('POSTGRES_PASSWORD')
PG_HOST = os.getenv('POSTGRES_HOST')
PG_PORT = os.getenv('POSTGRES_INTERNAL_PORT')



def ingest(**kwargs):
    try:
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")
        cursor = pg_conn.cursor()
        query = """
            INSERT INTO triplet_data (anchor, pos, neg)
            SELECT ta.tag_embed as anchor, b.summary_embed as pos, (SELECT tag_embed FROM tags WHERE id <> ta.id ORDER BY ta.tag_embed <-> tags.tag_embed LIMIT 1) as neg
            FROM tags as ta
            JOIN 
            books_tags as bt
            ON ta.id = bt.tag_id
            JOIN books as b
            ON bt.book_id = b.id
        """
        cursor.execute(query)
        pg_conn.commit()
        print("Query executed and data inserted successfully.")
    
    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
    
    finally:
        # Đóng kết nối sau khi sử dụng
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")

def train_adapter(**kwargs):
    try:
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")
        query = """
            SELECT ta.tag_embed as anchor, b.summary_embed as pos, (SELECT tag_embed FROM tags WHERE id <> ta.id ORDER BY ta.tag_embed <-> tags.tag_embed LIMIT 1) as neg
            FROM tags as ta
            JOIN 
            books_tags as bt
            ON ta.id = bt.tag_id
            JOIN books as b
            ON bt.book_id = b.id
        """
        df = pd.read_sql_query(query, pg_conn)
        adapter_kwargs = {
            'num_epochs': 30,
            'batch_size': 64,
            'learning_rate': 0.005,
            'warmup_steps': 100,
            'max_grad_norm': 1.0,
            'margin': 1.0,
            'input_dim' : 768,
            'output_dim' : 128
        }
        adapter, losses = train_linear_adapter(df, **adapter_kwargs)
        del df 
        cursor = pg_conn.cursor()
        query = """
                INSERT INTO public.model (type, weights, timestamp)
                VALUES ('adapter_losses', %s, DEFAULT);
            """
        cursor.execute(query, [Json(losses)])
        pg_conn.commit()
        weights = adapter.state_dict()
        weights_serialized = {k: v.tolist() for k, v in weights.items()}
        return weights_serialized

    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
    
    finally:
        # Đóng kết nối sau khi sử dụng
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")



def save_adapter(**kwargs):
    try:
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")
        ti = kwargs['ti']
        weights_serialized = ti.xcom_pull(task_ids='train_adapter')
        with pg_conn.cursor() as cursor:
            query = """
                INSERT INTO public.model (type, weights, timestamp)
                VALUES ('adapter', %s, DEFAULT);
            """
            cursor.execute(query, [Json(weights_serialized)])
            pg_conn.commit()

    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
    
    finally:
        # Đóng kết nối sau khi sử dụng
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")

# DAG definition
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 9, 8),
    'execution_timeout': timedelta(minutes=10),  
}

dag = DAG(
    'train_adapter',
    default_args=default_args,
    description='Trainging Linear Adapter',
    schedule_interval=None, 
)
create_triplet_data_table = PostgresOperator(
    postgres_conn_id = 'my_postgres',
    task_id='create_triplet_data_table',
    sql="""
        DO $$
        BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
            CREATE EXTENSION vector;
        END IF;
        END $$;
        CREATE TABLE IF NOT EXISTS public.triplet_data
        (
            anchor vector(768),
            pos vector(768),
            neg vector(768)
        )
        TABLESPACE pg_default;
        ALTER TABLE IF EXISTS public.triplet_data OWNER TO admin;
    """,
    dag=dag
)

ingestion_task = PythonOperator(
    task_id='ingestion',
    python_callable=ingest,
    dag=dag,
)

training_task = PythonOperator(
    task_id='train_adapter',
    python_callable=train_adapter,
    dag=dag
)

save_adapter_task = PythonOperator(
    task_id='save_weights',
    python_callable=save_adapter,
    dag=dag
)

create_triplet_data_table >> ingestion_task >> training_task >> save_adapter_task