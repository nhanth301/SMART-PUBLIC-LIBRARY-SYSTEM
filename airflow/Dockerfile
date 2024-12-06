FROM apache/airflow:slim-latest-python3.8
COPY ./airflow/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY ./airflow/airflow-entrypoint.sh /entrypoint.sh
COPY ./linear_adapter/adapter.pth /adapter.pth
USER root 
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

