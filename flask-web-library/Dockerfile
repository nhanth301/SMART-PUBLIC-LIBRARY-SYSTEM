FROM fundingsocietiesdocker/python3.8-slim
WORKDIR /app
COPY ./flask-web-library/requirements.txt .
COPY ./flask-web-library/* .
RUN pip install -r requirements.txt
CMD [ "python", "/app/app.py" ]