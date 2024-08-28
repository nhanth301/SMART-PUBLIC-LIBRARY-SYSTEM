FROM apache/airflow:slim-latest-python3.8

# Install necessary Python packages
RUN pip install psycopg2-binary

# Copy the entrypoint script to the container
COPY airflow-entrypoint.sh /entrypoint.sh

# Ensure the script is executable
USER root 
RUN chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Note: Adjust the USER directive if the base image runs as a non-root user
