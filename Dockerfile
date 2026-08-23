FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN pip install --no-cache-dir .
COPY data/realieprep_seed.db ./seed/realieprep_seed.db
COPY docker-entrypoint.sh /usr/local/bin/realieprep-entrypoint
RUN chmod +x /usr/local/bin/realieprep-entrypoint
EXPOSE 8000
ENTRYPOINT ["realieprep-entrypoint"]
