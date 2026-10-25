FROM python:3.12.8-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    COMMUNITY_DB_PATH=/data/rangkul/community_guides.sqlite3 \
    FACILITY_DOCS_DIR=/data/rangkul/facility-documents

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data/rangkul /data/rangkul/facility-documents \
    && chown -R 1000:1000 /app /data/rangkul
COPY --chown=1000:1000 main.py ./main.py

USER 1000:1000
EXPOSE 8000
VOLUME ["/data"]
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
