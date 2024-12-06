FROM smart-public-library-system-fast-api:latest


WORKDIR /code


# COPY ./fastapi/requirements.txt /code/requirements.txt


# RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt


COPY ./fastapi/app /code/app


CMD ["fastapi", "run", "app/main.py", "--port", "88"]