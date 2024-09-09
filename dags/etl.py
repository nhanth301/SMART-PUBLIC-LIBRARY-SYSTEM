from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import re
import sqlite3
import psycopg2
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


SQLITE_DB_PATH = '/opt/airflow/calibre/metadata.db'
PG_DB = 'spls'
PG_USER = 'admin'
PG_PASS = 'admin'
PG_HOST = 'postgres-ct'
PG_PORT = '5432'

sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)

def extract_description(file_path):
    """Trích xuất nội dung của trường description từ file XML."""
    try:
        tree = ET.parse(file_path)
    except:
        return "NaN"
    root = tree.getroot()
    namespace = {'dc': 'http://purl.org/dc/elements/1.1/'}
    description = root.find('.//dc:description', namespace)
    return description.text if description is not None else None

def clean_description(raw_description):
    """Chuẩn hóa và làm sạch nội dung description."""
    if raw_description is None:
        return "NaN"
    
    # Loại bỏ các thẻ HTML
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_description)
    
    # Chuẩn hóa khoảng trắng
    return ' '.join(cleantext.split())

def connections_check(**kwargs):
    try:
        # Kiểm tra kết nối đến SQLite
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        print("SQLite connection successful.")
        
        # Kiểm tra kết nối đến PostgreSQL
        pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)
        print("PostgreSQL connection successful.")
    
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        raise
    
    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
        raise
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

def close_connection(**kwargs):
    try:
        sqlite_conn.close()
        pg_conn.close()
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

def extract_books(**kwargs):
    try:
        cursor = sqlite_conn.cursor()
        cursor.execute('SELECT id, title, timestamp, pubdate, author_sort, path FROM books')
        rows = cursor.fetchall()
        data = []
        for row in rows:
            r = {
                    "id" : row[0],
                    "title":row[1],
                    "summary":"/opt/airflow/calibre/" + row[5] + "/metadata.opf",
                    "image": "/opt/airflow/calibre/" + row[5] + "/cover.jpg",
                    "author": row[4],
                    "created_date": row[2],
                    "published_date": row[3],
                    "modified_date": datetime.now()
                }
            data.append(r)
        ti = kwargs['ti']
        ti.xcom_push(key='book_data',value=data)
    finally:
        cursor.close()
    
def extract_tags(**kwargs):
    try:
        cursor = sqlite_conn.cursor()
        cursor.execute('SELECT id, name FROM tags')
        rows = cursor.fetchall()
        ti = kwargs['ti']
        ti.xcom_push(key='tag_data',value=rows)
    finally:
        cursor.close()
  
def extract_books_tags(**kwargs):
    try:
        cursor = sqlite_conn.cursor()
        cursor.execute('SELECT book, tag FROM books_tags_link')
        rows = cursor.fetchall()
        ti = kwargs['ti']
        ti.xcom_push(key='book_tag_data',value=rows)
    finally:
        cursor.close()

def transform_books(**kwargs):
    model = SentenceTransformer(
    "jinaai/jina-embeddings-v2-base-en",
    trust_remote_code=True
    )
    model.max_seq_length = 1024
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='extract_books',key='book_data')
    transformed_data = []
    for e in data:
        e['summary'] = clean_description(extract_description(e['summary']))
        if e['summary'] != "NaN":  
            e['summary_embed'] = model.encode([e['summary']])[0].astype(float).tolist()
        else:
            e['summary_embed'] = [0.0] * 768
        e['title_embed'] = model.encode([e['title']])[0].astype(float).tolist()
        transformed_data.append(e)
    ti.xcom_push(key='transformed_data',value=transformed_data)

def load_books(**kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='transform_books',key='transformed_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.books (id, title, summary, image, author, created_date, published_date, modified_date, title_embed, summary_embed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            image = EXCLUDED.image,
            author = EXCLUDED.author,
            created_date = EXCLUDED.created_date,
            published_date = EXCLUDED.published_date,
            modified_date = EXCLUDED.modified_date,
            title_embed = EXCLUDED.title_embed,
            summary_embed = EXCLUDED.summary_embed
            ;
        '''
        
        for item in data:
            pg_cursor.execute(insert_query, (
                item['id'],
                item['title'],
                item['summary'],
                item['image'],
                item['author'],
                item['created_date'],
                item['published_date'],
                item['modified_date'],
                item['title_embed'],
                item['summary_embed']
            ))
        
        pg_conn.commit()
    finally:
        pg_cursor.close()

def load_tags(**kwargs):
    ti = kwargs['ti']
    rows = ti.xcom_pull(task_ids='extract_tags',key='tag_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.tags (id, name)
        VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name;
        '''
        for row in rows:
            pg_cursor.execute(insert_query, (row[0],row[1]))
        pg_conn.commit()
    finally:
        pg_cursor.close()

def load_books_tags(**kwargs):
    ti = kwargs['ti']
    rows = ti.xcom_pull(task_ids='extract_books_tags',key='book_tag_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.books_tags (book_id, tag_id)
        VALUES (%s, %s)
        ON CONFLICT (book_id, tag_id) DO UPDATE
        SET book_id = EXCLUDED.book_id,
            tag_id = EXCLUDED.tag_id;
        '''
        for row in rows:
            pg_cursor.execute(insert_query, (row[0],row[1]))
        pg_conn.commit()
    finally:
        pg_cursor.close()


default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 9, 8),
    'execution_timeout': timedelta(minutes=10),  # Tăng thời gian timeout
}

# Define the DAG
dag = DAG(
    'ETL',
    default_args=default_args,
    description='ETL Process',
    schedule_interval='@daily',
)

# Define the task

check_conn_task = PythonOperator(
    task_id = 'check_connections',
    python_callable = connections_check,
    dag=dag
)

extract_books_task = PythonOperator(
    task_id='extract_books',
    python_callable=extract_books,
    dag=dag,
)

extract_tags_task = PythonOperator(
    task_id='extract_tags',
    python_callable=extract_tags,
    dag=dag,
)

extract_books_tags_task = PythonOperator(
    task_id='extract_books_tags',
    python_callable=extract_books_tags,
    dag=dag,
)

transform_books_task = PythonOperator(
    task_id = 'transform_books',
    execution_timeout=timedelta(minutes=30),
    python_callable= transform_books,
    dag=dag
)

load_books_task = PythonOperator(
    task_id='load_books',
    python_callable=load_books,
    dag=dag
)

load_tags_task = PythonOperator(
    task_id='load_tags',
    python_callable=load_tags,
    dag=dag
)

load_books_tags_task = PythonOperator(
    task_id='load_books_tags',
    python_callable=load_books_tags,
    dag=dag
)

close_conn_task = PythonOperator(
    task_id='close_connections',
    python_callable=close_connection,
    dag=dag
)

check_conn_task >> [extract_books_task, extract_tags_task, extract_books_tags_task]
extract_books_task >> transform_books_task >> load_books_task
extract_tags_task >> load_tags_task
extract_books_tags_task >> load_books_tags_task
[load_books_task, load_tags_task, load_books_tags_task] >> close_conn_task
