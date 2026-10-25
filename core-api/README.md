# RANGKUL Core API (staging starter)

FastAPI service for the RANGKUL team. It forwards chat to the private Hugging Face Space, serves demo facility pins, returns a static demo queue code, stores community directions with `pending` status, and indexes partner facility documents for chat references. See `TEAM_HANDOFF.md` for integration responsibilities by role.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set HF_SPACE_URL, HF_TOKEN, and FACILITY_ADMIN_TOKEN in the local environment/secret manager.
uvicorn main:app --reload --env-file .env
```

Open `/docs` for generated Swagger/OpenAPI documentation. Configure `HF_SPACE_URL` as the HTTPS `*.hf.space` hostname and keep `HF_TOKEN` in the backend's secret manager. Never send the Hugging Face token to the browser.

Set `CORS_ORIGINS` to the exact frontend origins before staging; the default only allows local development origins. A Docker image is provided; mount a durable volume at `/data` to retain submitted community guides between restarts.

```powershell
docker build -t rangkul-core-api .
docker volume create rangkul-core-data
docker run --rm -p 8000:8000 --env-file .env --mount source=rangkul-core-data,target=/data rangkul-core-api
```

`GET /api/facilities` currently returns **synthetic demo locations**, not confirmed partner providers. Replace these fixtures with verified partner details before release. SQLite stores community guide submissions and a full-text document index. Uploaded originals are stored under `FACILITY_DOCS_DIR`; mount a durable volume and set `COMMUNITY_DB_PATH` and `FACILITY_DOCS_DIR` for staging.

## Partner facility documents (RAG)

Authorized staff can upload PDF, DOCX, TXT, or Markdown files. The API extracts text, splits it into overlapping chunks, indexes the chunks with SQLite FTS5, and selects relevant passages for each `/api/chat` request. It keeps each original file so the team can manage the source documents. `FACILITY_ADMIN_TOKEN` is required in the `X-Facility-Admin-Token` header for listing, uploading, or deleting documents; keep this secret on the backend and never put it in the frontend. Swagger at `/docs` includes the upload form.

```powershell
curl.exe -H "X-Facility-Admin-Token: $env:FACILITY_ADMIN_TOKEN" -F "file=@C:\path\to\partner-hours.pdf" http://localhost:8000/api/facility-documents
curl.exe -H "X-Facility-Admin-Token: $env:FACILITY_ADMIN_TOKEN" http://localhost:8000/api/facility-documents
```

This first retrieval version uses keyword full-text search, without embedding/vector similarity. Scanned PDFs with no selectable text are rejected with an OCR hint; convert them to searchable PDFs before upload. Uploaded material is treated as untrusted reference data in the chat prompt. Only staff-provided, current and verified facility documents should be indexed.

No staging URL is claimed yet: a hosting target and Hugging Face Space credentials are still needed.
