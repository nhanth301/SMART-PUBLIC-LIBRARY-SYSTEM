import pandas as pd
import psycopg2
import seaborn as sns
import matplotlib.pyplot as plt

conn = psycopg2.connect(
dbname="spls",
user="admin",
password="admin",
host="localhost",
port="5434"
)
query1 = """
SELECT 
recommendation_date, 
action_type, 
total_skipped, 
total_clicked, 
total_read, 
total_no_interaction, 
total_recommended_books, 
total_recommendations
FROM vw_recommendation_rate_by_action
"""
data1 = pd.read_sql_query(query1, conn)
data1['recommendation_date'] = pd.to_datetime(data1['recommendation_date'])

plt.figure(figsize=(14, 8))
sns.barplot(
data=data1, 
x="recommendation_date", 
y="total_recommended_books", 
hue="action_type"
)
plt.title("User Actions on Recommended Books by Date", fontsize=16)
plt.xlabel("Recommendation Date", fontsize=14)
plt.ylabel("Total Recommended Books", fontsize=14)
plt.legend(title="Action Type", loc="upper right")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()