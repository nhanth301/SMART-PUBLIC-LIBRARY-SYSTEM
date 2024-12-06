from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from src.main import train
from dotenv import load_dotenv
import os 
import torch
import ast
from collections import defaultdict

PG_DB = os.getenv('POSTGRES_DB')
PG_USER = os.getenv('POSTGRES_USER')
PG_PASS = os.getenv('POSTGRES_PASSWORD')
PG_HOST = os.getenv('POSTGRES_HOST')
PG_PORT = os.getenv('POSTGRES_INTERNAL_PORT')

def load_model(**kwargs):
    try:
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")

        with pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query1 = """
                SELECT weights
                FROM public.model
                WHERE type LIKE 'weights'
                ORDER BY timestamp DESC
                LIMIT 1;
            """
            query2 = """
                SELECT weights
                FROM public.model
                WHERE type LIKE 'optim'
                ORDER BY timestamp DESC
                LIMIT 1;
            """
            cursor.execute(query1)
            result1 = cursor.fetchone() 
            cursor.execute(query2)
            result2 = cursor.fetchone()
            
            if result1 and result2:
                weights = result1['weights']
                optim = result2['weights']
                ti = kwargs['ti']
                ti.xcom_push(key='weights', value=weights)
                ti.xcom_push(key='optim', value=optim)
                return weights, optim
            else:
                print("No weights found in the model table.")
                return None, None
    
    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
        return None, None
    
    finally:
        # Đóng kết nối sau khi sử dụng
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")

def train_model(**kwargs):

    try:
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")
        cursor = pg_conn.cursor()
        
        # Thực hiện query
        query = """
            SELECT summary_embed 
            FROM books 
            ORDER BY idx;
        """
        cursor.execute(query)
        embeddings = [torch.tensor(ast.literal_eval(row[0])) for row in cursor.fetchall()]

        query = """
            SELECT 
                ui.sid, 
                b.idx-1 as idx, 
                CASE 
                    WHEN ui.action = 'click' THEN 1 
                    WHEN ui.action = 'skip' THEN -1 
                    WHEN ui.action = 'read' THEN 2 
                    ELSE 0 
                END AS reward
            FROM 
                ui_history ui
            INNER JOIN 
                books b 
            ON 
                ui.bid = b.id 
            ORDER BY 
                ui.sid, 
                ui.timestamp;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        grouped_data = defaultdict(list)
        for row in rows:
            sid, idx, reward = row
            grouped_data[sid].append([idx, reward])

        ui_history = [grouped_data[sid] for sid in grouped_data]
        print(ui_history)
        cursor.close()
    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
        return None
    
    finally:
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")

    def convert_tensors_to_lists(d):
        if isinstance(d, torch.Tensor):
            # Chuyển tensor thành list và giữ nguyên dtype
            return d.detach().cpu().numpy().tolist()
        elif isinstance(d, dict):
            return {k: convert_tensors_to_lists(v) for k, v in d.items()}
        elif isinstance(d, list):
            # Xử lý trường hợp list chứa tensor
            return [convert_tensors_to_lists(item) for item in d]
        elif isinstance(d, tuple):
            # Xử lý trường hợp tuple
            return tuple(convert_tensors_to_lists(item) for item in d)
        else:
            return d
    ti = kwargs['ti']
    pretrained_weights = ti.xcom_pull(task_ids='load_model_state', key='weights')
    pretrained_optim = ti.xcom_pull(task_ids='load_model_state', key='optim')
    new_weights, new_optim = train(ui_history,embeddings,5,10,pretrained_weights, pretrained_optim)
    weights_serialized = {k: v.tolist() for k, v in new_weights.items()}
    optim_serialized = convert_tensors_to_lists(new_optim)
    ti.xcom_push(key='weights', value=weights_serialized)
    ti.xcom_push(key='optim', value=optim_serialized)
    ti.xcom_push(key='metadata', value={"embedding_dim" : len(embeddings[0]), "action_dim" : len(embeddings)})
    return weights_serialized, optim_serialized

def save_model(**kwargs):
    ti = kwargs['ti']
    new_weights = ti.xcom_pull(task_ids='train_model', key='weights')
    new_optim = ti.xcom_pull(task_ids='train_model', key='optim')
    metadata = ti.xcom_pull(task_ids='train_model', key='metadata')
    if not new_weights and not new_optim:
        print("No new weights to save.")
        return

    try:
        # Kết nối đến PostgreSQL
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT
        )
        print("PostgreSQL connection successful.")
        
        # Thực hiện lưu new_weights vào bảng
        with pg_conn.cursor() as cursor:
            query1 = """
                INSERT INTO public.model (type, weights, timestamp)
                VALUES ('weights', %s, DEFAULT);
            """
            cursor.execute(query1, [Json(new_weights)])

            # Lưu new_optim
            query2 = """
                INSERT INTO public.model (type, weights, timestamp)
                VALUES ('optim', %s, DEFAULT);
            """
            cursor.execute(query2, [Json(new_optim)])

            query3 = """
                INSERT INTO public.model (type, weights, timestamp)
                VALUES ('metadata', %s, DEFAULT);
            """
            cursor.execute(query3, [Json(metadata)])
            # Commit once after both inserts
            pg_conn.commit()

            print("New weights and optim saved successfully.")

    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
    finally:
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
    'train_rl',
    default_args=default_args,
    description='Trainging RL-RecSys Model',
    schedule_interval=None, 
)

create_model_table = PostgresOperator(
    task_id = 'create_model_table',
    sql = """
        CREATE TABLE IF NOT EXISTS public.model
        (
            id SERIAL NOT NULL,
            type character varying NOT NULL,
            weights JSON NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT model_pkey PRIMARY KEY (id)
        )
        TABLESPACE pg_default;

        ALTER TABLE IF EXISTS public.model OWNER TO admin;
    """,
    dag=dag
)


load_model_state_task = PythonOperator(
    task_id='load_model_state',
    python_callable=load_model,
    dag=dag,
)

train_task = PythonOperator(
        task_id='train_model',
        python_callable=train_model, 
        dag=dag
)

save_model_state_task = PythonOperator(
    task_id='save_model_state',
    python_callable=save_model,
    dag=dag,
)

create_model_table >> load_model_state_task >> train_task >> save_model_state_task



