# RANGKUL Core API

Implementasi backend sesuai SRS, dikerjakan per fase. **Fase 0** menyediakan fondasi: API berversi `/api/v1`, model error konsisten, request ID, logging aman, database dan migrasi, otorisasi admin minimum, adapter penyedia LLM, serta health check.

Kode v2 lama (`main.py`) diparkir dan tidak menjadi entrypoint. Dokumentasinya ada di `TEAM_HANDOFF.md` dan dibangun ulang saat fasenya tiba.

## Menjalankan lokal

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --env-file .env
```

Swagger: `/docs`, OpenAPI: `/openapi.json`. Docker Compose: `docker compose up --build core-api` dari root repo.

## Kontrak Fase 0

| Endpoint | Akses | Keterangan |
| --- | --- | --- |
| `GET /api/v1/health/live` | publik | Proses aplikasi hidup; tidak menyentuh database |
| `GET /api/v1/health/ready` | operasional | Database dapat diakses dan seluruh migrasi sudah diterapkan |
| `GET /api/v1/admin/me` | admin | Identitas pemanggil untuk memverifikasi token |

Semua respons membawa header `X-Request-ID` (nilai klien dipakai ulang hanya jika aman; jika tidak, dibuat UUID baru). Error selalu berbentuk:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Permintaan tidak valid.",
    "request_id": "req-contoh"
  }
}
```

Kode yang tersedia: `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `RATE_LIMITED`, `CONSENT_REQUIRED`, `KNOWLEDGE_UNAVAILABLE`, `AI_PROVIDER_UNAVAILABLE`, `ROUTE_NOT_FOUND`, `SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`.

## Otorisasi admin minimum

Gunakan `Authorization: Bearer <token>`. Kredensial bersifat individual dan didefinisikan lewat `ADMIN_CREDENTIALS` (JSON array). Peran: `system_admin`, `content_reviewer`, `hospital_admin` (wajib memiliki `hospital_id`). Token disimpan di luar repositori; `.env.example` hanya berisi token pengembangan.

Pada `APP_ENV=production`, aplikasi menolak start jika kredensial kosong, token kurang dari 32 karakter, atau memakai awalan placeholder (`dev-`, `ganti-`, dan sejenisnya).

Contoh:

```powershell
curl -H "Authorization: Bearer dev-system-admin-token" http://localhost:8000/api/v1/admin/me
```

## Konfigurasi

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test`, `staging`, `production` |
| `DATABASE_PATH` | `data/rangkul.sqlite3` | Lokasi SQLite |
| `LOG_LEVEL` | `INFO` | Level logger aplikasi |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Dipisah koma |
| `ADMIN_CREDENTIALS` | token dev hanya saat development | JSON array kredensial |

Log ditulis sebagai JSON tanpa isi permintaan, query string, token, atau transkrip. Migrasi berjalan otomatis saat startup; readiness gagal jika masih ada migrasi tertunda.

## Struktur

- `app/main.py` — factory aplikasi dan lifespan.
- `app/config.py` — pembacaan dan validasi environment.
- `app/errors.py` — `AppError`, kode error, dan exception handler.
- `app/middleware.py` — request ID, log akses aman, penutupan error tak terduga.
- `app/db.py` + `app/migrations/` — SQLite dan runner migrasi bernomor.
- `app/security.py` — bearer token, peran, dan scope rumah sakit.
- `app/providers/base.py` — kontrak `LLMProvider` dan `FakeLLMProvider`.
- `app/api/v1/` — router versi 1.

## Pemeriksaan

```powershell
ruff check app tests main.py
ruff format --check app tests main.py
mypy app
pytest --cov=app --cov-fail-under=85
```

Gerbang coverage baris 85% dan branch dicatat pada laporan coverage. Modul kritis nantinya memakai ambang 90% sesuai SRS.
