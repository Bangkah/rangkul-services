#!/bin/sh
set -eu

MODEL_TAG="${MODEL_TAG:-qwen2.5:1.5b-instruct-q4_K_M}"
EXPECTED_SOURCE_ID="${EXPECTED_SOURCE_ID:-65ec06548149}"
CUSTOM_MODEL="${CUSTOM_MODEL:-rangkul-llm}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_HOST

ollama serve >/tmp/ollama-build.log 2>&1 &
OLLAMA_PID=$!
cleanup() {
  kill "$OLLAMA_PID" 2>/dev/null || true
  wait "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
for _ in $(seq 1 120); do
  if ollama list >/dev/null 2>&1; then ready=1; break; fi
  kill -0 "$OLLAMA_PID" 2>/dev/null || { cat /tmp/ollama-build.log >&2; exit 1; }
  sleep 2
done
[ "$ready" -eq 1 ] || { cat /tmp/ollama-build.log >&2; exit 1; }

ollama pull "$MODEL_TAG"
source_id=$(ollama list | awk -v tag="$MODEL_TAG" '$1 == tag {print $2}')
[ "$source_id" = "$EXPECTED_SOURCE_ID" ] || {
  echo "Unexpected source model identity: $source_id" >&2
  exit 1
}
ollama create "$CUSTOM_MODEL" -f Modelfile
ollama show "$CUSTOM_MODEL" >/dev/null
custom_id=$(ollama list | awk -v tag="$CUSTOM_MODEL" '$1 == tag {print $2}')
printf '{"source_model":"%s","source_digest":"%s","custom_model":"%s","custom_digest":"%s"}\n' "$MODEL_TAG" "$source_id" "$CUSTOM_MODEL" "$custom_id" > model-identity.json
