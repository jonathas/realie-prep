#!/bin/sh
set -eu

mkdir -p /app/data
if [ ! -f /app/data/realieprep.db ]; then
  cp /app/seed/realieprep_seed.db /app/data/realieprep.db
fi
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

