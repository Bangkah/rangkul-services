FROM ollama/ollama:0.40.11-rocm AS model-build
ENV OLLAMA_HOST=127.0.0.1:11434
WORKDIR /build
RUN if ! getent passwd 1000 >/dev/null 2>&1; then useradd --uid 1000 --create-home --shell /usr/sbin/nologin user; fi \
    && mkdir -p /home/user/.ollama/models \
    && chown -R 1000:1000 /build /home/user
COPY Modelfile /build/Modelfile
COPY build_model.sh /build/build_model.sh
RUN chmod 755 /build/build_model.sh && chown 1000:1000 /build/Modelfile /build/build_model.sh
ENV HOME=/home/user OLLAMA_MODELS=/home/user/.ollama/models
USER 1000:1000
RUN ./build_model.sh
USER 0:0
RUN rm -rf /usr/lib/ollama/rocm*
FROM python:3.12.8-slim-bookworm
ENV OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS=/home/user/.ollama/models OLLAMA_KEEP_ALIVE=-1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_MAX_QUEUE=4 RANGKUL_MODEL=rangkul-llm OLLAMA_BASE_URL=http://127.0.0.1:11434 HOME=/home/user PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/* && useradd --uid 1000 --create-home --shell /usr/sbin/nologin user && mkdir -p /home/user/.ollama/models /app && chown -R 1000:1000 /home/user /app
COPY --from=model-build /bin/ollama /usr/local/bin/ollama
COPY --from=model-build /usr/lib/ollama /usr/lib/ollama
COPY --from=model-build --chown=1000:1000 /home/user/.ollama/models /home/user/.ollama/models
COPY --from=model-build --chown=1000:1000 /build/model-identity.json /app/model-identity.json
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY --chown=1000:1000 app ./app
COPY --chown=1000:1000 proxy.py ./proxy.py
COPY --chown=1000:1000 scripts/start.sh ./start.sh
RUN chmod 755 /app/start.sh && chown -R 1000:1000 /app
USER 1000:1000
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 CMD curl -fsS http://127.0.0.1:7860/healthz || exit 1
CMD ["/app/start.sh"]
