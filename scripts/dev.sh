#!/bin/bash

# Run FastAPI app in development mode with auto-reload
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000










