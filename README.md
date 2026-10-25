# RANGKUL Services

Backend inti proyek RANGKUL AI sesuai SRS v2: integrasi Groq dari server, chat SSE dengan guardrail, direktori RS, ingest dokumen draf, dan route service wayfinding. Runtime Ollama/Hugging Face v1 disimpan di `model-runtime/` sebagai referensi deprecated; tidak dipakai Compose atau deployment aktif.

## Mulai

1. Salin `core-api/.env.example` menjadi `core-api/.env` dan isi `GROQ_API_KEY` serta token admin acak.
2. Jalankan `docker compose up --build core-api`.
3. Buka `http://localhost:8000/docs` untuk kontrak OpenAPI dan `/health` untuk status.

Jangan commit `.env`. Baca [`core-api/README.md`](core-api/README.md) untuk kontrak v2, tahapan publikasi dokumen, dan batasan saat ini.

## Integrasi tim

- Product Manager: Nazril
- UI/UX: Nasya
- Frontend: Jelita

Data RS Cut Meutia dan denah belum disediakan/terverifikasi; endpoint rumah sakit tetap kosong sampai Product Manager/admin RS memasukkan sumber resmi. Belum ada URL staging.

## CI

GitHub Actions memeriksa lint, format, kompilasi Python, kontrak OpenAPI wajib, dan membangun image Core API pada PR dan push ke `main`. Perubahan kerja dilakukan melalui branch dan pull request; jangan push langsung ke `main`.
