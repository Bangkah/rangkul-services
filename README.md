# RANGKUL Services

Repository for RANGKUL's private model runtime and backend API.

## Components

- [`model-runtime/`](model-runtime/README.md): Ollama + Qwen 2.5 runtime for a **Private Docker Hugging Face Space**. Only `POST /api/chat` is exposed under `/api`; the anti-diagnosis prompt is static in its Modelfile.
- [`core-api/`](core-api/README.md): FastAPI service for chat forwarding, searchable partner documents, facilities, demo registration, and pending community directions. Its hosting target is separate from Hugging Face.
- [`core-api/TEAM_HANDOFF.md`](core-api/TEAM_HANDOFF.md): integration notes for product manager Nazril, UI/UX Nasya, and frontend Jelita.

## Hugging Face deployment

GitHub Actions checks the model runtime, runs its tests, and builds both Docker images on pull requests and pushes to `main`. A maintainer can manually dispatch the workflow on `main` to upload only `model-runtime/` to the Private Docker Space and run a streaming smoke check.

Configure the protected GitHub `production` environment with:

- `HF_TOKEN`: a token with write access to the Space. Store it as a secret; never commit it into source. Rotate any token shared in chat after deployment verification.
- `HF_SPACE_ID`: `owner/space-name`.
- `HF_SPACE_URL`: the Space app origin, for example `https://owner-space.hf.space`.

The Core API also needs `HF_SPACE_URL` and a read token in its host's secret manager so it can call the private Space. The same Hugging Face token may be used if its scope permits; it stays server-side.

## Core API staging

The Core API image listens on port 8000 and stores SQLite at `/data/rangkul/community_guides.sqlite3` plus original partner documents at `/data/rangkul/facility-documents`; attach durable storage at `/data`. Set `HF_SPACE_URL`, `HF_TOKEN`, `FACILITY_ADMIN_TOKEN`, and the exact `CORS_ORIGINS` in the hosting platform. Once a staging host is selected, share its URL and Swagger endpoint (`/docs`) with the UI/UX and frontend roles. Facility pins remain clearly marked demo data until the product manager confirms partner details.
