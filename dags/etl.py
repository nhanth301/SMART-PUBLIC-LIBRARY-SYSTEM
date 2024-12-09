from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Connection
from airflow.utils import db
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
        
        db.merge_conn(
            Connection(
                conn_id="my_postgres",  
                conn_type="postgres",        
                host=PG_HOST,  
                schema=PG_DB,      
                login=PG_USER,      
                password=PG_PASS,    
                port=PG_PORT                 
            )
        )

    
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
        cursor.execute('''SELECT b.id, b.title, b.timestamp, b.pubdate, GROUP_CONCAT(a.name, ', '), b.path FROM books AS b JOIN books_authors_link AS bal ON b.id = bal.book JOIN authors AS a ON bal.author = a.id GROUP BY b.id, b.title, b.timestamp, b.pubdate, b.path''')
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
    summaries, titles = [], []

    # Prepare data for batch processing
    for e in data:
        if e['id'] in new_ids:
            e['summary'] = clean_description(extract_description(PATH+e['summary']))
            summaries.append(e['summary'])
            titles.append(e['title'])

    # Process in batches
    embed_summaries, embed_titles, embed_imgs = [], [], []
    for i in range(0,len(summaries),batch_size):
        batch_summaries = summaries[i:i+batch_size]
        batch_titles = titles[i:i+batch_size]

        embed_summaries.extend(requests.post(f'{HOST}/transform', json={'texts': batch_summaries}).json()['embeddings'])
        embed_titles.extend(requests.post(f'{HOST}/transform', json={'texts': batch_titles}).json()['embeddings'])

    # Combine embeddings with original data    
    count = 0
    for e in data:
        if e['id'] in new_ids:
            e['summary_embed'] = embed_summaries[count]
            e['title_embed'] = embed_titles[count]
            transformed_data.append(e)
            count += 1
    assert count == len(embed_summaries)
    ti.xcom_push(key='deleted_ids',value=deleted_ids)
    ti.xcom_push(key='transformed_data',value=transformed_data)

def transform_tags(**kwargs):
    ti = kwargs['ti']
    rows = ti.xcom_pull(task_ids='extract_tags',key='tag_data')
    source_ids = set([row[0] for row in rows])
    new_ids, deleted_ids = filter('tags',source_ids)

    transformed_data = []
    batch_size = 64
    tag_names = []

    for row in rows:
        if row[0] in new_ids:
            tag_names.append(row[1])
    
    tag_embeds = []
    for i in range(0,len(tag_names),batch_size):
        batch_names = tag_names[i:i+batch_size]
        tag_embeds.extend(requests.post(f'{HOST}/transform', json={'texts': batch_names}).json()['embeddings'])
    
    count = 0
    for row in rows:
        if row[0] in new_ids:
            e = {}
            e['id'] = row[0]
            e['name'] = row[1]
            e['embed'] = tag_embeds[count]
            transformed_data.append(e)
            count += 1
    assert count == len(tag_embeds)
    ti.xcom_push(key='deleted_ids',value=deleted_ids)
    ti.xcom_push(key='transformed_data',value=transformed_data)


def load_books(**kwargs):
    """Load transformed book data into PostgreSQL."""
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='transform_books',key='transformed_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.books (id, title, summary, image, pdf_file, author, created_date, published_date, modified_date, title_embed, summary_embed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
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
                item['summary_embed']
            ))
        deleted_ids = ti.xcom_pull(task_ids='transform_books',key='deleted_ids')
        if len(deleted_ids) > 0:
            pg_cursor.execute("UPDATE books SET active = false WHERE id IN %s", (tuple(deleted_ids),))
        pg_conn.commit()
    finally:
        pg_cursor.close()

def load_tags(**kwargs):
    """Load tag data into PostgreSQL."""
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='transform_tags',key='transformed_data')
    try:
        pg_cursor = pg_conn.cursor()
        insert_query = '''
        INSERT INTO public.tags (id, name, tag_embed)
        VALUES (%s, %s, %s);
        '''
        for e in data:
            pg_cursor.execute(insert_query, (e["id"],e["name"],e["embed"]))
        deleted_ids = ti.xcom_pull(task_ids='transform_tags',key='deleted_ids')
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
    postgres_conn_id = 'my_postgres',
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
        idx serial PRIMARY KEY,
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
        active boolean DEFAULT true
    )
    TABLESPACE pg_default;
    ALTER TABLE public.books OWNER to admin;
    """,
    dag=dag
)

create_tags_table = PostgresOperator(
    postgres_conn_id = 'my_postgres',
    task_id = 'create_tags_table',
    sql="""
    DO $$
    BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE EXTENSION vector;
    END IF;
    END $$;
    CREATE TABLE IF NOT EXISTS public.tags
    (
        id integer NOT NULL,
        name character varying NOT NULL,
        tag_embed vector(768),
        CONSTRAINT tags_pkey PRIMARY KEY (id)
    )
    TABLESPACE pg_default;
    ALTER TABLE IF EXISTS public.tags OWNER to admin;
    """,
    dag=dag
)

create_books_tags_table = PostgresOperator(
    postgres_conn_id = 'my_postgres',
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
    """,
    dag=dag
)


create_ui_history_table = PostgresOperator(
    postgres_conn_id = 'my_postgres',
    task_id='create_ui_history_table',
    sql="""
        CREATE TABLE IF NOT EXISTS public.ui_history
        (
            sid VARCHAR(50),
            uid INTEGER,
            bid INTEGER,
            action VARCHAR(50),
            timestamp BIGINT,
            isWH boolean DEFAULT false
        )
        TABLESPACE pg_default;
        ALTER TABLE IF EXISTS public.ui_history OWNER TO admin;
    """,
    dag=dag
)

create_rec_history_table = PostgresOperator(
    postgres_conn_id = 'my_postgres',
    task_id='create_rec_history_table',
    sql="""
        CREATE TABLE IF NOT EXISTS public.rec_history
        (
            sid VARCHAR(50),
            uid INTEGER,
            bid INTEGER,
            timestamp BIGINT,
            isWH boolean DEFAULT false
        )
        TABLESPACE pg_default;
        ALTER TABLE IF EXISTS public.rec_history OWNER TO admin;
    """,
    dag=dag
)

create_model_table = PostgresOperator(
    postgres_conn_id = 'my_postgres',
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

# create_training_history_table = PostgresOperator(
#     postgres_conn_id = 'my_postgres',
#     task_id = 'create_training_history_table',
#     sql = """
#         CREATE TABLE IF NOT EXISTS public.training_history
#         (
#             id SERIAL NOT NULL,
#             type character varying NOT NULL,
#             weights JSON NOT NULL,
#             timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#             CONSTRAINT model_pkey PRIMARY KEY (id)
#         )
#         TABLESPACE pg_default;

#         ALTER TABLE IF EXISTS public.model OWNER TO admin;
#     """,
#     dag=dag
# )


create_warehouse = PostgresOperator(
    postgres_conn_id = 'my_postgres',
    task_id = 'create_warehouse',
    sql="""
        CREATE TABLE IF NOT EXISTS DIM_Time (
    timeID SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    day INT NOT NULL,
    month INT NOT NULL,
    year INT NOT NULL,
    quarter INT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    week_of_year INT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS DIM_Action (
    actionID SERIAL PRIMARY KEY,
    actionName VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS Fact_Recommendation (
    factID SERIAL PRIMARY KEY,
    sessionID character varying NOT NULL,
    userID INT NOT NULL,
    bookID INT NOT NULL,
    timeID INT NOT NULL REFERENCES DIM_Time(timeID),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Fact_User_Interaction (
    factID SERIAL PRIMARY KEY,
    sessionID character varying NOT NULL,
    userID INT NOT NULL,
    bookID INT NOT NULL,
    actionID INT NOT NULL REFERENCES DIM_Action(actionID),
    timeID INT NOT NULL REFERENCES DIM_Time(timeID),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'fact_recommendation' 
        AND indexname = 'idx_fact_recommendation_timeid'
    ) THEN
        CREATE INDEX idx_fact_recommendation_timeid ON Fact_Recommendation(timeID);
    END IF;
END $$;

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'fact_user_interaction' 
            AND indexname = 'idx_fact_user_interaction_timeid'
        ) THEN
            CREATE INDEX idx_fact_user_interaction_timeid ON Fact_User_Interaction(timeID);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'fact_user_interaction' 
            AND indexname = 'idx_fact_user_interaction_actionid'
        ) THEN
            CREATE INDEX idx_fact_user_interaction_actionid ON Fact_User_Interaction(actionID);
        END IF;
    END $$;


DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM DIM_Action) THEN
        INSERT INTO DIM_Action (actionName, description) VALUES
            ('click', 'User clicked the book'),
            ('read', 'User read the book'),
            ('skip', 'User skipped (not care) the book');
    END IF;
END $$;

DO $$ 
DECLARE 
    curr_date DATE := '2024-01-01';  -- Changed from current_date to curr_date
    end_date DATE := '2026-12-31';
BEGIN
    WHILE curr_date <= end_date LOOP  -- Changed from current_date to curr_date
        IF NOT EXISTS (SELECT 1 FROM DIM_Time WHERE date = curr_date) THEN  -- Changed from current_date to curr_date
            INSERT INTO DIM_Time (date, day, month, year, quarter, day_name, week_of_year, is_weekend)
            VALUES (
                curr_date,  -- Changed from current_date to curr_date
                EXTRACT(DAY FROM curr_date),  -- Changed from current_date to curr_date
                EXTRACT(MONTH FROM curr_date),  -- Changed from current_date to curr_date
                EXTRACT(YEAR FROM curr_date),  -- Changed from current_date to curr_date
                CASE 
                    WHEN EXTRACT(MONTH FROM curr_date) BETWEEN 1 AND 3 THEN 1  -- Changed from current_date to curr_date
                    WHEN EXTRACT(MONTH FROM curr_date) BETWEEN 4 AND 6 THEN 2  -- Changed from current_date to curr_date
                    WHEN EXTRACT(MONTH FROM curr_date) BETWEEN 7 AND 9 THEN 3  -- Changed from current_date to curr_date
                    ELSE 4
                END,
                TO_CHAR(curr_date, 'Day'),  -- Changed from current_date to curr_date
                EXTRACT(WEEK FROM curr_date),  -- Changed from current_date to curr_date
                CASE WHEN EXTRACT(DOW FROM curr_date) IN (6, 0) THEN TRUE ELSE FALSE END  -- Changed from current_date to curr_date
            );
        END IF;
        curr_date := curr_date + INTERVAL '1 day';  -- Changed from current_date to curr_date
    END LOOP;
END $$;
        CREATE OR REPLACE FUNCTION get_time_id(unix_timestamp BIGINT) 
        RETURNS INT AS $$
        DECLARE
            date_value DATE;
            time_id INT;
        BEGIN
            -- Convert unix timestamp to date
            date_value := to_timestamp(unix_timestamp)::DATE;
            
            -- Get timeID from DIM_Time
            SELECT timeID INTO time_id
            FROM DIM_Time
            WHERE date = date_value;
            
            RETURN time_id;
        END;
        $$ LANGUAGE plpgsql;

        -- Function to get actionID from action name
            CREATE OR REPLACE FUNCTION get_action_id(action_name VARCHAR) 
            RETURNS INT AS $$
            DECLARE
                action_id INT;
            BEGIN
                SELECT actionID INTO action_id
                FROM DIM_Action
                WHERE actionName = action_name;
                
                RETURN action_id;
            END;
            $$ LANGUAGE plpgsql;
            CREATE OR REPLACE VIEW vw_recommendation_rate_by_action AS
                SELECT 
                    dt.date AS recommendation_date,
                    da.actionname AS action_type,
                    COUNT(CASE WHEN da.actionname = 'skip' THEN fui.bookid END) AS total_skipped,
                    COUNT(CASE WHEN da.actionname = 'click' THEN fui.bookid END) AS total_clicked,
                    COUNT(CASE WHEN da.actionname = 'read' THEN fui.bookid END) AS total_read,
                    COUNT(CASE WHEN fui.factid IS NULL THEN fr.bookid END) AS total_no_interaction,
                    COUNT(DISTINCT fr.bookid) AS total_recommended_books,
                    COUNT(*) AS total_recommendations -- Tổng số khuyến nghị
                FROM 
                    fact_recommendation fr
                LEFT JOIN 
                    fact_user_interaction fui 
                    ON fr.userid = fui.userid AND fr.bookid = fui.bookid AND fr.timeid = fui.timeid
                LEFT JOIN 
                    dim_action da 
                    ON fui.actionid = da.actionid
                JOIN 
                    dim_time dt 
                    ON fr.timeid = dt.timeid
                GROUP BY 
                    dt.date, da.actionname
                ORDER BY 
                    dt.date, action_type;

                CREATE OR REPLACE VIEW vw_user_interaction_analysis AS
                    SELECT 
                        dt.year,
                        dt.quarter,
                        dt.month,
                        da.actionName,
                        COUNT(*) as action_count,
                        COUNT(DISTINCT ui.userID) as unique_users,
                        COUNT(DISTINCT ui.bookID) as unique_books
                    FROM Fact_User_Interaction ui
                    JOIN DIM_Time dt ON ui.timeID = dt.timeID
                    JOIN DIM_Action da ON ui.actionID = da.actionID
                    GROUP BY dt.year, dt.quarter, dt.month, da.actionName;
        ALTER TABLE public.DIM_Time OWNER to admin;
        ALTER TABLE public.DIM_Action OWNER to admin;
        ALTER TABLE public.Fact_Recommendation OWNER to admin;
        ALTER TABLE public.Fact_User_Interaction OWNER to admin;
    """,
    dag=dag
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

transform_tags_task = PythonOperator(
    task_id='transform_tags',
    python_callable= transform_tags,
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
check_conn_task >> [create_warehouse, create_model_table,create_ui_history_table,create_rec_history_table,extract_books_task, extract_tags_task, extract_books_tags_task] 
extract_books_task >> create_books_table >> transform_books_task >> load_books_task
extract_tags_task >> create_tags_table >> transform_tags_task >> load_tags_task
extract_books_tags_task >> create_books_tags_table >> load_books_tags_task
[load_books_task, load_tags_task, load_books_tags_task] >> close_conn_task



