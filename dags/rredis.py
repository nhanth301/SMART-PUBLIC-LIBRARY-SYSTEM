from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
import psycopg2
import os
import redis
import json

PG_DB = os.getenv('POSTGRES_DB')
PG_USER = os.getenv('POSTGRES_USER')
PG_PASS = os.getenv('POSTGRES_PASSWORD')
PG_HOST = os.getenv('POSTGRES_HOST')
PG_PORT = os.getenv('POSTGRES_INTERNAL_PORT')

def read_data(**kwargs):
    redis_client = redis.StrictRedis(
    host='redis-ct', 
    port=6379,         
    decode_responses=True    
    )
    try:
        redis_client.ping()
        print("Kết nối thành công đến Redis!")
        retrieved_ui_data = [json.loads(item) for item in redis_client.lrange("ui_history", 0, -1)]
        redis_client.delete("ui_history")
        retrieved_rec_data = [json.loads(item) for item in redis_client.lrange("rec_history", 0, -1)]
        redis_client.delete("rec_history")
        return retrieved_ui_data, retrieved_rec_data
    except redis.ConnectionError:
        print("Không thể kết nối đến Redis.")
        return None, None 

def store_data(**kwargs):
    try:
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")
        pg_cursor = pg_conn.cursor()
        ti = kwargs['ti']
        ui_data, rec_data = ti.xcom_pull(task_ids='read_data')

        query = """
                INSERT INTO public.ui_history (sid, uid, bid, action, timestamp)
                VALUES (%s, %s, %s, %s, %s);
            """
        for d in ui_data:
            pg_cursor.execute(query,(d['sid'],d['uid'],d['bid'],d['action'],d['timestamp']))

        query = """
                INSERT INTO public.rec_history (sid, uid, bid, timestamp)
                VALUES (%s, %s, %s, %s);
            """
        for d in rec_data:
            pg_cursor.execute(query,(d['sid'],d['uid'],d['bid'],d['timestamp']))

        pg_conn.commit()
    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
        return None
    
    finally:
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 9, 8),
    'execution_timeout': timedelta(minutes=10),  
}

dag = DAG(
    'read_redis',
    default_args=default_args,
    description='Read data from redis and save to postgres',
    schedule_interval=None, 
)

read_data_task = PythonOperator(
    task_id='read_data',
    python_callable=read_data,
    dag=dag,
)
store_data_task = PythonOperator(
    task_id='store_data',
    python_callable=store_data,
    dag=dag,
)

read_data_task >> store_data_task