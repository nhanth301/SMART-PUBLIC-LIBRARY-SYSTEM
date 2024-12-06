FROM fundingsocietiesdocker/python3.8-slim
WORKDIR /app
COPY ./flask-web-library/requirements.txt .
COPY ./flask-web-library/ .
# COPY ../calibre-library/ ./smart_library/media/calibre-library
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "smart_library/manage.py", "runserver", "0.0.0.0:1111"]

