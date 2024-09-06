FROM apache/airflow:slim-latest-python3.8
RUN pip install psycopg2-binary
COPY airflow-entrypoint.sh /entrypoint.sh
USER root 
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

