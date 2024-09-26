from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
import xml.etree.ElementTree as ET
import re
import sqlite3
import psycopg2
import requests

HOST = "https://zep.hcmute.fit/7561"
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

def filter(table_name, source_ids, dbpmk=False):
    if dbpmk:
        try:
            pg_cursor = pg_conn.cursor()
            query = f"SELECT * from public.{table_name}"
            pg_cursor.execute(query)
            rows = pg_cursor.fetchall()
            dest_ids = set(rows)
        finally:
            pg_cursor.close()
        deleted_ids = dest_ids - source_ids
        new_ids = source_ids - dest_ids
        return new_ids, deleted_ids
    else:
        try:
            pg_cursor = pg_conn.cursor()
            query = f"SELECT id from public.{table_name}"
            pg_cursor.execute(query)
            rows = pg_cursor.fetchall()
            dest_ids = set([row[0] for row in rows])
        finally:
            pg_cursor.close()
        deleted_ids = dest_ids - source_ids
        new_ids = source_ids - dest_ids
        return new_ids, deleted_ids


def transform_books(**kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='extract_books',key='book_data')
    source_ids = set([d["id"]for d in data])
    new_ids, deleted_ids = filter('books',source_ids)
    transformed_data = []
    for e in data:
        if e['id'] in new_ids:
            e['summary'] = clean_description(extract_description(e['summary']))
            if e['summary'] != "NaN":  
                e['summary_embed'] = requests.post(f'{HOST}/transform', json={'texts': [e['summary']]}).json()['embeddings'][0]
            else:
                e['summary_embed'] = [0.0] * 768
            e['title_embed'] = requests.post(f'{HOST}/transform', json={'texts': [e['title']]}).json()['embeddings'][0]
            with open(e['image'], 'rb') as img:
                files = {'image': img}
                e['img_embed']= requests.post(f'{HOST}/extract_img', files=files).json()['last_hidden_state'][0][0]
            transformed_data.append(e)
    ti.xcom_push(key='deleted_ids',value=deleted_ids)
    ti.xcom_push(key='transformed_data',value=transformed_data)

def load_books(**kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='transform_books',key='transformed_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.books (id, title, summary, image, author, created_date, published_date, modified_date, title_embed, summary_embed, img_embed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            image = EXCLUDED.image,
            author = EXCLUDED.author,
            created_date = EXCLUDED.created_date,
            published_date = EXCLUDED.published_date,
            modified_date = EXCLUDED.modified_date,
            title_embed = EXCLUDED.title_embed,
            summary_embed = EXCLUDED.summary_embed,
            img_embed = EXCLUDED.img_embed
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
                item['summary_embed'],
                item['img_embed']
            ))
        deleted_ids = ti.xcom_pull(task_ids='transform_books',key='deleted_ids')
        if len(deleted_ids) > 0:
            pg_cursor.execute("DELETE FROM books WHERE id IN %s",(tuple(deleted_ids),))
        
        pg_conn.commit()
    finally:
        pg_cursor.close()

def load_tags(**kwargs):
    ti = kwargs['ti']
    rows = ti.xcom_pull(task_ids='extract_tags',key='tag_data')
    source_ids = set([row[0] for row in rows])
    new_ids, deleted_ids = filter('tags',source_ids)
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.tags (id, name)
        VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name;
        '''
        for row in rows:
            if row[0] in new_ids:
                pg_cursor.execute(insert_query, (row[0],row[1]))
        if len(deleted_ids) > 0:
            pg_cursor.execute("DELETE FROM tags WHERE id IN %s",(tuple(deleted_ids),))
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
    'execution_timeout': timedelta(minutes=10),  
}

# Define the DAG
dag = DAG(
    'ETL',
    default_args=default_args,
    description='ETL Process',
    schedule_interval=None,
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

create_books_table = PostgresOperator(
    task_id = 'create_books_table',
    sql="""
    DO $$
    BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE EXTENSION vector;
    END IF;
    END $$;
    CREATE TABLE IF NOT EXISTS public.books
    (
        id integer NOT NULL,
        title character varying COLLATE pg_catalog."default" NOT NULL,
        summary character varying COLLATE pg_catalog."default" NOT NULL,
        image character varying COLLATE pg_catalog."default" NOT NULL,
        author character varying COLLATE pg_catalog."default" NOT NULL,
        published_date timestamp with time zone NOT NULL,
        created_date timestamp with time zone NOT NULL,
        modified_date timestamp with time zone NOT NULL,
        title_embed vector(768),
        summary_embed vector(768),
        img_embed vector(768),
        CONSTRAINT books_pkey PRIMARY KEY (id)
    )
    TABLESPACE pg_default;
    ALTER TABLE IF EXISTS public.books OWNER to admin;
    """
)

create_tags_table = PostgresOperator(
    task_id = 'create_tags_table',
    sql="""
    CREATE TABLE IF NOT EXISTS public.books_tags
    (
        book_id integer NOT NULL,
        tag_id integer NOT NULL,
        CONSTRAINT books_tags_pkey PRIMARY KEY (book_id, tag_id)
    )
    TABLESPACE pg_default;
    ALTER TABLE IF EXISTS public.books_tags OWNER to admin;
    """
)

create_books_tags_table = PostgresOperator(
    task_id = 'create_books_tags_table',
    sql="""
    CREATE TABLE IF NOT EXISTS public.tags
    (
        id integer NOT NULL,
        name character varying NOT NULL,
        CONSTRAINT tags_pkey PRIMARY KEY (id)
    )
    TABLESPACE pg_default;
    ALTER TABLE IF EXISTS public.tags OWNER to admin;
    """
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
extract_books_task >> create_books_table >> transform_books_task >> load_books_task
extract_tags_task >> create_tags_table   >> load_tags_task
extract_books_tags_task >> create_books_tags_table >> load_books_tags_task
[load_books_task, load_tags_task, load_books_tags_task] >> close_conn_task
