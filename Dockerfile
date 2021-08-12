FROM python:3.8-slim
WORKDIR /aporia-importer
STOPSIGNAL SIGINT

# System dependencies
RUN apt update && apt install -y wget
RUN pip3 install poetry

# Project dependencies
COPY poetry.lock pyproject.toml ./

RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --no-dev

COPY . .

WORKDIR /aporia-importer/src
ENTRYPOINT python3 -m aporia_importer.main
