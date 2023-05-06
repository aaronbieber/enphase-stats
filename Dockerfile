FROM python:3.10-slim-buster
COPY . /src
RUN pip install -r /src/requirements.txt
