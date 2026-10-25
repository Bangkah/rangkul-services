# RANGKUL Services

Backend RANGKUL AI. Implementasi mengikuti SRS secara bertahap (waterfall); status saat ini **Fase 1 — Data Inti dan API Publik**.

## Struktur

- `core-api/app/` — API aktif sesuai SRS. Entrypoint: `app.main:app`, base path `/api/v1`.
- `core-api/main.py` — kode v2 lama yang **diparkir**. Tidak dihapus dan tidak dijadikan entrypoint; fiturnya dibangun ulang saat fasenya tiba.
- `model-runtime/` — runtime v1 deprecated, disimpan sebagai referensi.

## Mulai

```powershell
cd core-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --env-file .env
```

- Swagger: `http://localhost:8000/docs`
- Liveness: `GET /api/v1/health/live`
- Readiness: `GET /api/v1/health/ready`
- Fasilitas publik: `GET /api/v1/hospitals`
- Artikel publik: `GET /api/v1/articles`
- Identitas admin: `GET /api/v1/admin/me` dengan header `Authorization: Bearer dev-system-admin-token` (token pengembangan dari `.env.example`; jangan dipakai di produksi).
- Seed sintetis: `python -m app.seed` (idempoten; ditolak saat `APP_ENV=production`).

Docker: `docker compose up --build core-api`.

## Pemeriksaan

```powershell
cd core-api
ruff check app tests main.py
ruff format --check app tests main.py
mypy app
pytest --cov=app --cov-fail-under=85
```

CI GitHub Actions menjalankan lint, format, type check, unit/integration test dengan gerbang coverage 85%, pemeriksaan kontrak OpenAPI, pemindaian secret, audit dependensi, dan build image.

## Integrasi tim

- Product Manager: Nazril
- UI/UX: Nasya
- Frontend: Jelita

Data RS Cut Meutia, denah, reviewer medis, dan kontak krisis belum tersedia/terverifikasi. Jangan mengklaim kemitraan atau mempublikasikan data layanan sebelum dikonfirmasi pihak berwenang.
