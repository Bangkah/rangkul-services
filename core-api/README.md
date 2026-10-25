# RANGKUL Core API (staging starter)

FastAPI service for the RANGKUL team. It forwards chat to the private Hugging Face Space, serves demo facility pins, returns a static demo queue code, and stores community directions with `pending` status in SQLite. See `TEAM_HANDOFF.md` for integration responsibilities by role.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set HF_SPACE_URL and HF_TOKEN in the local environment/secret manager.
uvicorn main:app --reload --env-file .env
```

Open `/docs` for generated Swagger/OpenAPI documentation. Configure `HF_SPACE_URL` as the HTTPS `*.hf.space` hostname and keep `HF_TOKEN` in the backend's secret manager. Never send the Hugging Face token to the browser.

Set `CORS_ORIGINS` to the exact frontend origins before staging; the default only allows local development origins. A Docker image is provided; mount a durable volume at `/data` to retain submitted community guides between restarts.

```powershell
docker build -t rangkul-core-api .
docker volume create rangkul-core-data
docker run --rm -p 8000:8000 --env-file .env --mount source=rangkul-core-data,target=/data rangkul-core-api
```

`GET /api/facilities` currently returns **synthetic demo locations**, not confirmed partner providers. Replace these fixtures with verified partner details before release. SQLite stores community guide submissions locally by default; configure a durable volume and set `COMMUNITY_DB_PATH` for staging. RAG is skipped until a retriever is configured.

No staging URL is claimed yet: a hosting target and Hugging Face Space credentials are still needed.
