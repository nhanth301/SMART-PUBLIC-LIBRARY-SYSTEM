
FROM python:3.9


WORKDIR /code


COPY ./quixstream/requirements.txt /code/requirements.txt


RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt


COPY ./quixstream/app /code/app


CMD ["sh", "-c", "python app/consumer.py"]
