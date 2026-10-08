FROM python:3.12-slim

ENV POETRY_VERSION=2.1.3
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN apt-get update \
 && apt-get install -y curl \
 && curl -sSL https://install.python-poetry.org | python3 - \
 && apt-get purge -y curl \
 && apt-get autoremove -y \
 && apt-get install -y ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
 && poetry install --no-root --no-interaction --no-ansi

COPY . .

CMD ["./scripts/prod.sh"]
