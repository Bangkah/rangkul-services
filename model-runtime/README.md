---
title: Rangkul AI Backend
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# RANGKUL AI Private LLM Runtime

Private Hugging Face Docker Space with Ollama and a FastAPI proxy using `qwen2.5:1.5b`. Only `POST /api/chat` is exposed under `/api`; the operational health routes `/healthz` and `/readyz` are also available. Ollama binds to loopback.

## Run locally

```sh
docker build -t rangkul-ai-runtime .
docker run --rm -p 7860:7860 rangkul-ai-runtime
```

Set Space visibility to **Private**. The backend caller keeps its Hugging Face read token in its own secret manager and sends it as `Authorization: Bearer ...`; never place it in this image or browser client.

Inference responses always stream Ollama newline-delimited JSON (`application/x-ndjson`), ending with `done: true`. Errors detected before streaming map to HTTP 502/504; errors after stream headers are sent appear as an NDJSON error chunk. `options` accepts only `stop`; the server fixes model, context, temperature, seed, and output limit. Body is limited to 128 KiB, aggregate input to 12,000 characters, chat to 32 messages, output to 512 tokens, one active inference and four waiters with a 30-second queue limit.

| Endpoint | Method | Purpose |
|---|---|---|
| `/healthz` | GET | Liveness |
| `/readyz` | GET | Ollama/model readiness |
| `/api/chat` | POST | Streaming chat |

Admin Ollama endpoints return 403; all other API paths except `/api/chat` return 404. Client `system` messages and extra request fields are rejected; the anti-diagnosis system prompt lives only in the built model's Modelfile.

## Release identity

- Model source tag: `qwen2.5:1.5b-instruct-q4_K_M` (Ollama ID `65ec06548149`; build fails if this ID changes)
- Ollama build image: `ollama/ollama:0.40.11-rocm` (official CPU runtime retained; ROCm libraries removed from the final image)
- Python base: `3.12.8-slim-bookworm`; hash-checked transitive pins in `requirements.lock`
- Build-generated source and custom model IDs: `/app/model-identity.json`; public `/api/tags` exposes the custom model's current digest
- Space port: `7860`; Ollama: `127.0.0.1:11434`

The source model is pulled at image build and its published model ID is checked against the expected value. The build writes both source and custom model IDs to `/app/model-identity.json`; the actual custom digest is also exposed by `/api/tags`. CPU performance, hardware allocation, and deployed Private Space access must be verified on the target Space.

## Trusted deployment

The GitHub Actions deploy job runs only after checks pass and a maintainer manually dispatches the workflow on `main`. Create a Hugging Face Space first, set it to **Private** and Docker SDK, then add protected GitHub environment secrets `HF_TOKEN` (write access to that Space), `HF_SPACE_ID` (`owner/space-name`), and `HF_SPACE_URL` (the Space app URL). The deploy script refuses a public or non-Docker Space; the smoke test waits up to ten minutes for readiness and verifies chat streaming. Pull requests do not receive these secrets.

See [ACCEPTANCE.md](ACCEPTANCE.md) for what has been checked locally and what still requires a Space deployment.
