#!/bin/bash

# Run pending DB migrations before starting the server
alembic upgrade head

# Run FastAPI app in production mode
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000










