#!/bin/bash
set -e

function is_db_initialized() {
  if airflow db check --silent; then
    echo "Database is already initialized."
    return 0
  else
    return 1
  fi
}

if ! is_db_initialized; then
  echo "Initializing database..."
  airflow db init
  echo "Database initialized."
else
  echo "Database already initialized."
fi

airflow users create \
  --username ${AIRFLOW_USER_USERNAME} \
  --password ${AIRFLOW_USER_PASSWORD} \
  --firstname ${AIRFLOW_USER_FIRSTNAME} \
  --lastname ${AIRFLOW_USER_LASTNAME} \
  --role ${AIRFLOW_USER_ROLE} \
  --email ${AIRFLOW_USER_EMAIL}

exec "$@"
