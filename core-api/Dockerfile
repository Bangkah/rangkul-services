FROM python:3.12.8-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATABASE_PATH=/data/rangkul/rangkul.sqlite3 \
    LOG_LEVEL=INFO

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data/rangkul \
    && chown -R 1000:1000 /app /data/rangkul
COPY --chown=1000:1000 app ./app

USER 1000:1000
EXPOSE 8000
VOLUME ["/data"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
