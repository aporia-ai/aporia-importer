FROM python:3.8-slim
WORKDIR /aporia-importer
STOPSIGNAL SIGINT

# System dependencies
RUN apt update && apt install -y wget
RUN pip3 install poetry

# Project dependencies
COPY poetry.lock pyproject.toml ./

RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --no-dev -E all

COPY . .

WORKDIR /aporia-importer/src
ENV PYTHONPATH "${PYTHONPATH}:./"

ENTRYPOINT python3 -m aporia_importer.main
