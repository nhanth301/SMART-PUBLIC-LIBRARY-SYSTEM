from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.providers.postgres.operators.postgres import PostgresOperator
import xml.etree.ElementTree as ET
import re
import sqlite3
import psycopg2
import requests
from dotenv import load_dotenv
import os
import glob

# Load environment variables
load_dotenv('../.env')

# Configuration
HOST = os.getenv('HOST')
SQLITE_DB_PATH = os.getenv('CALIBRE_DB_PATH')
PG_DB = os.getenv('POSTGRES_DB')
PG_USER = os.getenv('POSTGRES_USER')
PG_PASS = os.getenv('POSTGRES_PASSWORD')
PG_HOST = os.getenv('POSTGRES_HOST')
PG_PORT = os.getenv('POSTGRES_INTERNAL_PORT')
PATH="/opt/airflow/calibre/" 

# Database connections
sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
pg_conn = psycopg2.connect(
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            host=PG_HOST,
            port=PG_PORT)


def extract_description(file_path):
    """Extract description content from XML file."""
    try:
        tree = ET.parse(file_path)
    except:
        return "NaN"
    root = tree.getroot()
    namespace = {'dc': 'http://purl.org/dc/elements/1.1/'}
    description = root.find('.//dc:description', namespace)
    return description.text if description is not None else None

def clean_description(raw_description):
    """Normalize and clean description content."""
    if raw_description is None:
        return "NaN"
    
    # Remove HTML tags
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_description)
    
    # Normalize whitespace
    return ' '.join(cleantext.split())

def connections_check(**kwargs):
    """Verify database connections."""
    try:
        # Check SQLite connection
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        print("SQLite connection successful.")
        
        # Check PostgreSQL connection
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
    """Close database connections."""
    try:
        sqlite_conn.close()
        pg_conn.close()
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

def extract_books(**kwargs):
    """Extract book data from SQLite database."""
    try:
        cursor = sqlite_conn.cursor()
        cursor.execute('SELECT id, title, timestamp, pubdate, author_sort, path FROM books')
        rows = cursor.fetchall()
        data = []
        for row in rows:
            r = {
                    "id" : row[0],
                    "title":row[1],
                    "summary": (row[5] + "/metadata.opf").replace("'",'_'),
                    "image": (row[5] + "/cover.jpg").replace("'",'_'),
                    "pdf_file": (row[5]+ "/*.pdf").replace("'",'_'),
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
    """Extract tag data from SQLite database."""
    try:
        cursor = sqlite_conn.cursor()
        cursor.execute('SELECT id, name FROM tags')
        rows = cursor.fetchall()
        ti = kwargs['ti']
        ti.xcom_push(key='tag_data',value=rows)
    finally:
        cursor.close()
  
def extract_books_tags(**kwargs):
    """Extract book-tag relationships from SQLite database."""
    try:
        cursor = sqlite_conn.cursor()
        cursor.execute('SELECT book, tag FROM books_tags_link')
        rows = cursor.fetchall()
        ti = kwargs['ti']
        ti.xcom_push(key='book_tag_data',value=rows)
    finally:
        cursor.close()

def filter(table_name, source_ids):
    """Compare source and destination IDs to find new and deleted records."""
    if table_name == 'books_tags':
        try:
            pg_cursor = pg_conn.cursor()
            query = f"SELECT * from public.{table_name}"
            pg_cursor.execute(query)
            rows = pg_cursor.fetchall()
            dest_ids = set([(row[0],row[1]) for row in rows])
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
    """Transform and enrich book data."""
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='extract_books',key='book_data')
    source_ids = set([d["id"]for d in data])
    new_ids, deleted_ids = filter('books',source_ids)

    transformed_data = []
    batch_size = 64
    summaries, titles, imgs = [], [], []

    # Prepare data for batch processing
    for e in data:
        if e['id'] in new_ids:
            e['summary'] = clean_description(extract_description(PATH+e['summary']))
            summaries.append(e['summary'])
            titles.append(e['title'])
            imgs.append(('image[]',open(PATH+e['image'], 'rb')))

    # Process in batches
    embed_summaries, embed_titles, embed_imgs = [], [], []
    for i in range(0,len(summaries),batch_size):
        batch_summaries = summaries[i:i+batch_size]
        batch_titles = titles[i:i+batch_size]
        batch_imgs = imgs[i:i+batch_size]

        embed_summaries.extend(requests.post(f'{HOST}/transform', json={'texts': batch_summaries}).json()['embeddings'])
        embed_titles.extend(requests.post(f'{HOST}/transform', json={'texts': batch_titles}).json()['embeddings'])
        embed_imgs.extend(requests.post(f'{HOST}/extract_img', files=batch_imgs).json()['last_hidden_state'])

    # Combine embeddings with original data    
    count = 0
    for e in data:
        if e['id'] in new_ids:
            e['summary_embed'] = embed_summaries[count]
            e['title_embed'] = embed_titles[count]
            e['img_embed']= embed_imgs[count]
            transformed_data.append(e)
            count += 1
    assert count == len(embed_summaries)
    ti.xcom_push(key='deleted_ids',value=deleted_ids)
    ti.xcom_push(key='transformed_data',value=transformed_data)

def load_books(**kwargs):
    """Load transformed book data into PostgreSQL."""
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='transform_books',key='transformed_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.books (id, title, summary, image, pdf_file, author, created_date, published_date, modified_date, title_embed, summary_embed, img_embed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        '''
        
        for item in data:
            pg_cursor.execute(insert_query, (
                item['id'],
                item['title'],
                item['summary'],
                item['image'],
                item['pdf_file'],
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
    """Load tag data into PostgreSQL."""
    ti = kwargs['ti']
    rows = ti.xcom_pull(task_ids='extract_tags',key='tag_data')
    source_ids = set([row[0] for row in rows])
    new_ids, deleted_ids = filter('tags',source_ids)
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.tags (id, name)
        VALUES (%s, %s);
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
    """Load book-tag relationships into PostgreSQL."""
    ti = kwargs['ti']
    rows = ti.xcom_pull(task_ids='extract_books_tags',key='book_tag_data')
    source_ids = set([(row[0],row[1]) for row in rows])
    new_ids, deleted_ids = filter('books_tags',source_ids)
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.books_tags (book_id, tag_id)
        VALUES (%s, %s);
        '''
        for row in rows:
            if (row[0],row[1]) in new_ids:
                pg_cursor.execute(insert_query, (row[0],row[1]))
        if len(deleted_ids) > 0:
            for ids in deleted_ids:
                pg_cursor.execute("DELETE FROM books_tags WHERE book_id = %s and tag_id = %s ",(ids[0],ids[1]))
        pg_conn.commit()
    finally:
        pg_cursor.close()


# DAG definition
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 9, 8),
    'execution_timeout': timedelta(minutes=10),  
}

dag = DAG(
    'ETL',
    default_args=default_args,
    description='ETL Process',
    schedule_interval=None,
)



# SQL statements for table creation
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
        pdf_file character varying COLLATE pg_catalog."default" NOT NULL,
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

create_books_tags_table = PostgresOperator(
    task_id = 'create_books_tags_table',
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

# Task definitions
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

# Define task dependencies
check_conn_task >> [extract_books_task, extract_tags_task, extract_books_tags_task] 
extract_books_task >> create_books_table >> transform_books_task >> load_books_task
extract_tags_task >> create_tags_table   >> load_tags_task
extract_books_tags_task >> create_books_tags_table >> load_books_tags_task
[load_books_task, load_tags_task, load_books_tags_task] >> close_conn_task
