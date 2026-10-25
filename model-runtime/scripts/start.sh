#!/bin/sh
set -eu
ollama serve &
OLLAMA_PID=$!
cleanup() { kill -TERM "${API_PID:-}" "$OLLAMA_PID" 2>/dev/null || true; wait "${API_PID:-}" 2>/dev/null || true; wait "$OLLAMA_PID" 2>/dev/null || true; }
trap cleanup TERM INT EXIT
ready=0
for i in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then ready=1; break; fi
  kill -0 "$OLLAMA_PID" 2>/dev/null || { echo '{"event":"ollama_exited"}' >&2; exit 1; }
  sleep 2
done
[ "$ready" -eq 1 ] || { echo '{"event":"ollama_readiness_timeout"}' >&2; exit 1; }
ollama show "$RANGKUL_MODEL" >/dev/null 2>&1 || { echo '{"event":"required_model_missing"}' >&2; exit 1; }
uvicorn proxy:app --host 0.0.0.0 --port 7860 --workers 1 &
API_PID=$!
wait "$API_PID"
