string = ["hello test"]
def load_connections():
    # Connections needed for this example dag to finish
    from airflow.models import Connection
    from airflow.utils import db


    db.merge_conn(
        Connection(
            conn_id="t2",
            conn_type="kafka",
            extra=json.dumps(
                {
                    "bootstrap.servers": "kafka-ct:9092",
                    "group.id": "airflow",
                    "enable.auto.commit": True,
                    "auto.offset.reset": "latest",
                }
            ),
        )
    )
