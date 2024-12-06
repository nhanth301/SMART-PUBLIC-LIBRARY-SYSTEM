import pandas as pd
import psycopg2



if __name__ == "__main__":
    conn = psycopg2.connect(
    user='admin',
    password='admin',
    host='localhost',
    port=5434,
    database='spls'
    )   

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

    df = pd.read_sql_query(query,conn)

    conn.close()

    df.to_csv("./linear_adapter/triplet.csv",index=False)
    
