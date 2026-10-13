FROM python:3.12-slim

ENV POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* README.md ./
COPY src/ src/
COPY config/ config/
COPY main.py ./
COPY scripts/ scripts/

RUN pip install --no-cache-dir poetry \
    && poetry install --only main --no-interaction --no-ansi

CMD ["python", "main.py"]
