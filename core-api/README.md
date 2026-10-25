# RANGKUL Core API

Implementasi backend sesuai SRS, dikerjakan per fase. **Fase 0** menyediakan fondasi: API berversi `/api/v1`, model error konsisten, request ID, logging aman, database dan migrasi, otorisasi admin minimum, adapter penyedia LLM, serta health check. **Fase 1** menambahkan katalog fasilitas, layanan, persiapan kunjungan, artikel, dokumen pengetahuan dengan alur review/publish, audit administratif, dan seed sintetis. **Fase 2** menambahkan chat RAG atas dokumen terbit, sitasi sumber, redaksi PII, guardrail keselamatan, persetujuan AI, rate limit, fallback provider, dan endpoint SSE.

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

## Kontrak Fase 0 dan Fase 1

| Endpoint | Akses | Keterangan |
| --- | --- | --- |
| `GET /api/v1/health/live` | publik | Proses aplikasi hidup; tidak menyentuh database |
| `GET /api/v1/health/ready` | operasional | Database dapat diakses dan seluruh migrasi sudah diterapkan |
| `GET /api/v1/admin/me` | admin | Identitas pemanggil untuk memverifikasi token |
| `GET /api/v1/hospitals` | publik | Daftar fasilitas berstatus `published` |
| `GET /api/v1/hospitals/{id}` | publik | Detail fasilitas dan tautan Google Maps |
| `GET /api/v1/hospitals/{id}/services` | publik | Layanan terverifikasi pada fasilitas terbit |
| `GET /api/v1/hospitals/{id}/visit-requirements` | publik | Persiapan kunjungan yang telah dikonfirmasi |
| `GET /api/v1/articles` | publik | Daftar artikel terbit |
| `GET /api/v1/articles/{id}` | publik | Detail artikel dan sumber |
| `POST /api/v1/chat` | publik | Chat non-streaming dengan retrieval, sitasi, consent, dan guardrail |
| `POST /api/v1/chat/stream` | publik | Chat streaming SSE (`meta`, `sources`, `token`, `done`) |
| `GET /api/v1/admin/hospitals` | system/hospital admin | Daftar fasilitas; `hospital_admin` hanya melihat cakupannya |
| `POST /api/v1/admin/hospitals` | system admin | Membuat fasilitas sebagai draft |
| `PATCH /api/v1/admin/hospitals/{id}` | system/hospital admin | Memperbarui; data terbit kembali menjadi draft |
| `POST /api/v1/admin/hospitals/{id}/publish` | system/hospital admin | Menerbitkan setelah validasi sumber/verifikasi/koordinat |
| `POST /api/v1/admin/hospitals/{id}/archive` | system/hospital admin | Mengarsipkan fasilitas |
| `POST /api/v1/admin/hospitals/{id}/services` | system/hospital admin | Membuat layanan draft |
| `PATCH /api/v1/admin/services/{id}` | system/hospital admin | Memperbarui layanan sesuai cakupan |
| `POST /api/v1/admin/services/{id}/publish` | system/hospital admin | Menerbitkan layanan terverifikasi |
| `POST /api/v1/admin/services/{id}/archive` | system/hospital admin | Mengarsipkan layanan |
| `POST /api/v1/admin/hospitals/{id}/visit-requirements` | system/hospital admin | Membuat persiapan kunjungan draft |
| `PATCH /api/v1/admin/visit-requirements/{id}` | system/hospital admin | Memperbarui persiapan kunjungan |
| `POST /api/v1/admin/visit-requirements/{id}/publish` | system/hospital admin | Menerbitkan persiapan kunjungan terverifikasi |
| `POST /api/v1/admin/visit-requirements/{id}/archive` | system/hospital admin | Mengarsipkan persiapan kunjungan |
| `GET/POST /api/v1/admin/knowledge-documents` | system admin/reviewer | Daftar dan buat dokumen pengetahuan |
| `POST /api/v1/admin/knowledge-documents/{id}/submit-review` | system admin/reviewer | Mengajukan peninjauan |
| `POST /api/v1/admin/knowledge-documents/{id}/review` | system admin/reviewer | Menyetujui/menolak dengan alasan |
| `POST /api/v1/admin/knowledge-documents/{id}/publish` | system admin/reviewer | Menerbitkan versi yang disetujui dan valid |
| `POST /api/v1/admin/knowledge-documents/{id}/archive` | system admin/reviewer | Mengarsipkan dokumen |
| `POST /api/v1/admin/knowledge-documents/{id}/revoke` | system admin/reviewer | Mencabut dokumen terbit |
| `GET/POST /api/v1/admin/articles` | system admin/reviewer | Daftar dan buat artikel draft |
| `PATCH /api/v1/admin/articles/{id}` | system admin/reviewer | Memperbarui; artikel terbit kembali menjadi draft |
| `POST /api/v1/admin/articles/{id}/publish` | system admin/reviewer | Menerbitkan artikel bersumber |
| `POST /api/v1/admin/articles/{id}/archive` | system admin/reviewer | Mengarsipkan artikel |
| `GET /api/v1/admin/audit-events` | system admin | Menelusuri audit berdasarkan objek/aksi |

Data publik hanya berasal dari status `published`; layanan dan persiapan kunjungan juga mensyaratkan fasilitas induknya terbit. Respons publik tidak menyertakan kolom admin seperti `status` atau `created_at`, tetapi tetap memuat `source`, `verified_at`, dan `is_synthetic`.

## Chat RAG Fase 2

`POST /api/v1/chat` menerima `message`, `consent_ai_processing`, `consent_version`, `hospital_id` opsional, `history` opsional (maksimal 20 pesan), dan `stream`. `POST /api/v1/chat/stream` mengembalikan `text/event-stream` dengan event `meta`, `sources`, `token`, dan `done`.

- Hanya dokumen `published` yang diindeks ke `knowledge_chunks`; dokumen pending, kedaluwarsa, atau di luar cakupan rumah sakit tidak dijadikan sumber.
- PII umum (NIK, email, telepon) diredaksi sebelum retrieval, riwayat, dan provider.
- Tanpa sumber relevan di atas ambang, sistem menjawab dengan abstain dan tidak memanggil provider.
- Pertanyaan krisis, medis, dan prompt injection ditangani guardrail deterministik.
- Jawaban wajib merujuk sumber dan diperiksa ulang terhadap kebocoran instruksi, diagnosis/obat, serta rute internal.
- `AI_PROVIDER_UNAVAILABLE` (503) dikembalikan bila provider tidak siap/gagal; endpoint non-AI tetap berjalan.
- Rate limit chat terpisah dari publik dan admin; respons 429 menyertakan `Retry-After`.

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

Kode yang tersedia: `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `METHOD_NOT_ALLOWED`, `RATE_LIMITED`, `CONSENT_REQUIRED`, `KNOWLEDGE_UNAVAILABLE`, `AI_PROVIDER_UNAVAILABLE`, `ROUTE_NOT_FOUND`, `SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`.

## Data seed sintetis

Migrasi tidak memuat data. Untuk pengembangan, isi database dengan data sintetis yang seluruhnya diberi label `is_synthetic=1` dan sumber "SEED PENGEMBANGAN":

```powershell
python -m app.seed
```

Perintah ini idempoten (aman dijalankan ulang) dan **menolak berjalan saat `APP_ENV=production`**. Data seed mencakup fasilitas `rs-pilot-demo`, dua layanan, dua persiapan kunjungan, tiga dokumen pengetahuan (dua terbit dan terindeks, satu menunggu review), dan dua artikel (satu terbit, satu draft). Jangan mencampur data sintetis dengan data fasilitas resmi; publikasi data sintetis di produksi juga ditolak oleh API.

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
| `LLM_PROVIDER` | `fake` | `fake` atau `groq`; `fake` di produksi menjadi unavailable |
| `GROQ_API_KEY` | kosong | Hanya dibaca server; placeholder dianggap tidak terkonfigurasi |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Endpoint OpenAI-compatible |
| `GROQ_MODEL` / `GROQ_FALLBACK_MODEL` | `llama-3.3-70b-versatile` / kosong | Model utama dan cadangan |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `20` / `1` | Batas waktu dan retry provider |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` | `0.1` / `600` | Parameter generasi |
| `CHAT_ENABLED` | `true` | Mematikan endpoint chat bila `false` |
| `CHAT_MAX_MESSAGE_CHARS` / `CHAT_HISTORY_TURNS` | `2000` / `6` | Batas pesan dan giliran riwayat |
| `CHAT_TOP_K` / `CHAT_SIMILARITY_THRESHOLD` | `4` / `0.2` | Retrieval leksikal |
| `CHAT_MAX_CONTEXT_CHARS` | `6000` | Batas konteks sumber |
| `AI_CONSENT_VERSION` | `privacy-notice-v1` | Versi persetujuan yang harus cocok |
| `CRISIS_CONTACT` | kosong | Kontak krisis terverifikasi; kosong memakai arahan darurat umum |
| `RATE_LIMIT_*_PER_MINUTE` | `120` / `60` / `10` | Batas publik/admin/chat per proses |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Jendela rate limit |

Log ditulis sebagai JSON tanpa isi permintaan, query string, token, atau transkrip. Migrasi berjalan otomatis saat startup; readiness gagal jika masih ada migrasi tertunda.

## Struktur

- `app/main.py` — factory aplikasi dan lifespan.
- `app/config.py` — pembacaan dan validasi environment.
- `app/errors.py` — `AppError`, kode error, dan exception handler.
- `app/middleware.py` — request ID, log akses aman, penutupan error tak terduga.
- `app/db.py` + `app/migrations/` — SQLite dan runner migrasi bernomor.
- `app/security.py` — bearer token, peran, dan scope rumah sakit.
- `app/schemas.py` — model request/response dan enum status publikasi.
- `app/policy.py` — validasi publikasi, normalisasi waktu, tautan rute, dan guard data sintetis.
- `app/catalog.py`, `app/knowledge.py`, `app/articles.py` — akses data SQLite.
- `app/audit.py` — pencatatan dan penelusuran audit administratif.
- `app/seed.py` — data seed sintetis idempoten dan indeks pengetahuan terbit.
- `app/privacy.py` -- redaksi PII sebelum retrieval/provider.
- `app/rag.py` -- chunking, indeks SQLite, retrieval berambang, dan filter cakupan.
- `app/guardrails.py` -- klasifikasi krisis/medis/injection dan guardrail keluaran.
- `app/chat.py` -- orkestrasi chat, sitasi, abstention, dan fallback.
- `app/prompts.py` -- prompt sistem dan konteks sumber berversi.
- `app/providers/` -- kontrak `LLMProvider`, fake provider, dan adapter Groq.
- `app/ratelimit.py` -- rate limit in-memory per proses.
- `app/providers/base.py` — kontrak dasar provider; adapter Groq ada di `app/providers/groq.py`.
- `app/api/v1/` — router versi 1 (publik, chat, admin fasilitas, pengetahuan, artikel, audit).

## Pemeriksaan

```powershell
ruff check app tests main.py
ruff format --check app tests main.py
mypy app
pytest --cov=app --cov-fail-under=85
```

Gerbang CI saat ini adalah coverage baris 85%; branch coverage ikut dihitung dan dilaporkan. Modul kritis (otorisasi, status publikasi, guardrail) menjadi fokus pengujian tambahan sesuai SRS.

Pengujian Fase 2 memakai `FakeLLMProvider` dan `httpx.MockTransport`; CI tidak memanggil Groq. Set evaluasi emas klinis berisi minimal 150 kasus tetap memerlukan review tenaga medis; subset deterministik saat ini hanya menguji abstention, sitasi, PII, krisis, medis, injection, dan kegagalan provider.
