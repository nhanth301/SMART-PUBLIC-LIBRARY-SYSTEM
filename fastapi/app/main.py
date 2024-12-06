from typing import Union

import redis.client
from policy_network import PolicyNetwork
from fastapi import FastAPI
import psycopg2
import os 
from psycopg2.extras import RealDictCursor, Json
import torch
import ast
import numpy as np
import json
from typing import List, Union
import redis
import time
from adapter import LinearAdapter

PG_DB = os.getenv('POSTGRES_DB')
PG_USER = os.getenv('POSTGRES_USER')
PG_PASS = os.getenv('POSTGRES_PASSWORD')
PG_HOST = os.getenv('POSTGRES_HOST')
PG_PORT = os.getenv('POSTGRES_INTERNAL_PORT')
pg_conn = None
state_dict = None
adapter_w = None
embedding_dim = None 
action_dim = None
model = None
embeddings = None
b2i = {}
i2b = {}

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
            WHERE type = 'weights'
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        cursor.execute(query1)
        result1 = cursor.fetchone() 

        query2 = """
            SELECT weights
            FROM public.model
            WHERE type = 'metadata'
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        cursor.execute(query2)
        result2 = cursor.fetchone() 

        query3 = """
            SELECT weights
            FROM public.model
            WHERE type = 'adapter'
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        cursor.execute(query3)
        result3 = cursor.fetchone() 

        if result1 and result2 and result3:
            state_dict = result1['weights']
            metadata = result2['weights']
            adapter_w = result3['weights']
            embedding_dim = metadata['embedding_dim']
            action_dim = metadata['action_dim']
            print("Load state_dict successfully")
        else:
            print("No weights found in the model table.")
    cursor = pg_conn.cursor()
    query = """
        SELECT idx, id from books;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    for row in rows:
        b2i[row[1]] = row[0] - 1
        i2b[row[0]-1] = row[1]
    print("Load b2i successfully")
    
    query = """
    SELECT summary_embed 
    FROM books 
    ORDER BY idx;
    """
    cursor.execute(query)
    adapter = LinearAdapter(768,128)
    adapter_w = {k: torch.tensor(np.array(v)) for k, v in adapter_w.items()}
    adapter.load_state_dict(adapter_w)
    embeddings = [adapter(torch.tensor(ast.literal_eval(row[0]))).detach() for row in cursor.fetchall()]
    print("Load embedding successfully")
    cursor.close()          
except Exception as e:
    print(e)
finally:
        if pg_conn:
            pg_conn.close() 
            print("PostgreSQL connection closed.")
try:
    model = PolicyNetwork(embedding_dim,action_dim)
    state_dict = {k: torch.tensor(np.array(v)) for k, v in state_dict.items()}
    model.load_state_dict(state_dict)
    
except Exception as e:
    print(e)

redis_client = redis.StrictRedis(
    host='redis-ct', 
    port=6379,         
    decode_responses=True    
)
try:
    redis_client.ping()
    print("Kết nối thành công đến Redis!")
except redis.ConnectionError:
    print("Không thể kết nối đến Redis.")

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

@app.post("/predict/")
def process_list(input_list:List[List[Union[str, int]]]):
    sid = input_list[0][0]
    uid = input_list[0][1]
    embed_input = [embeddings[b2i[e[2]]] for e in input_list]
    reward_input = [e[3] for e in input_list]
    action_probabilities = model(embed_input,reward_input)
    _, top_k_indices = torch.topk(action_probabilities, k=5, dim=-1)
    result = [i2b[i.item()] for i in top_k_indices]
    redis_client.delete(str(uid)+'_rec')
    redis_client.rpush(str(uid)+'_rec', *result)
    for id in result:
        value = {"sid" : sid, "uid" : uid, "bid" : id, "timestamp" : int(time.time())}
        redis_client.rpush("rec_history", json.dumps(value))

@app.get("/rec/")
def getRec(uid: int):
    recommended_books = redis_client.lrange(str(uid)+'_rec', 0, -1)
    recommended_books = [int(item) for item in recommended_books]
    return {"result":recommended_books}