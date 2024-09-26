FROM apache/airflow:slim-latest-python3.8
COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY airflow-entrypoint.sh /entrypoint.sh
USER root 
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

