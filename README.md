# RANGKUL Services

Repositori untuk runtime model privat dan API backend RANGKUL.

## Komponen

- [`model-runtime/`](model-runtime/README.md): runtime Ollama + Qwen 2.5 untuk Docker lokal, menjadi opsi inferensi privat tanpa API eksternal.
- [`core-api/`](core-api/README.md): layanan FastAPI yang dapat memakai Groq untuk demo cepat atau Ollama lokal untuk demonstrasi privasi, selain mencari isi dokumen mitra dan menyediakan API fasilitas/demo lainnya.
- [`core-api/TEAM_HANDOFF.md`](core-api/TEAM_HANDOFF.md): panduan integrasi untuk Product Manager Nazril, UI/UX Nasya, dan Frontend Jelita.

## Menjalankan MVP

GitHub Actions menjalankan pemeriksaan kode, pengujian runtime, dan build kedua image Docker saat pull request dan push ke `main`. Untuk menjalankan demo cepat, atur `GROQ_API_KEY` di `core-api/.env` lalu jalankan `docker compose up --build core-api`.

Untuk demonstrasi lokal privat, atur `LLM_PROVIDER=ollama` di `core-api/.env`, lalu jalankan `docker compose --profile ollama up --build`. Ollama mengunduh model ketika image runtime dibangun; sesudah itu inference dapat berjalan di Docker lokal tanpa kunci API eksternal.

Groq memakai endpoint Chat Completions kompatibel OpenAI dan model awal `openai/gpt-oss-20b`. Kuota gratis mengikuti batas akun Groq dan dapat berubah; saat limit terlampaui, backend mengembalikan HTTP 429. Lihat [dokumentasi rate limit Groq](https://console.groq.com/docs/rate-limits).

Mode Groq mengirim prompt pengguna dan kutipan dokumen fasilitas ke Groq. Untuk bukti privasi, jalankan Ollama lokal dan gunakan prompt data demo; jangan masukkan data pasien ke layanan eksternal.

## Staging Core API

Image Core API menerima koneksi pada port 8000 dan menyimpan basis data SQLite di `/data/rangkul/community_guides.sqlite3` serta dokumen mitra di `/data/rangkul/facility-documents`; pasang penyimpanan persisten pada `/data`. Atur `LLM_PROVIDER`, kredensial provider, `FACILITY_ADMIN_TOKEN`, dan daftar `CORS_ORIGINS` yang tepat di platform hosting. Setelah target staging dipilih, bagikan URL layanan dan Swagger (`/docs`) kepada UI/UX dan Frontend. Data fasilitas saat ini masih contoh sampai Product Manager mengonfirmasi data mitra.
