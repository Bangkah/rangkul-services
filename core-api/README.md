# RANGKUL Core API — SRS v2

Backend FastAPI untuk chat edukasi HIV yang dibatasi sumber, direktori rumah sakit, denah, serta wayfinding deterministik. Groq dipanggil dari backend; kunci API tidak pernah dikirim ke browser. Runtime Ollama/Hugging Face v1 sudah deprecated dan tidak termasuk jalur aktif.

## Menjalankan lokal

```powershell
cd core-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Isi GROQ_API_KEY dan FACILITY_ADMIN_TOKEN pada .env
uvicorn main:app --reload --env-file .env
```

Swagger tersedia di `/docs`; status dasar di `/health`. Jangan masukkan secret ke Git. Untuk Compose, jalankan dari root repo: `docker compose up --build core-api`.

## Chat dan privasi

`POST /v1/chat` menerima `{ "consent": true, "messages": [{"role":"user","content":"..."}] }` dan mengirim SSE `data:` dengan event `delta`, lalu `done` (sitasi + disclaimer). Riwayat dibatasi lewat `CHAT_HISTORY_TURNS`; server menghapus pola NIK, email, dan nomor telepon sebelum pemanggilan Groq. Chat memakai persetujuan eksplisit dan batas permintaan per alamat IP. Kata kunci krisis menghasilkan respons tetap tanpa memanggil model.

Chat hanya diteruskan ke Groq jika ada potongan dokumen berstatus `published`; tanpa konteks, server mengembalikan jawaban “belum tersedia”. `GROQ_MODEL` dan opsional `GROQ_FALLBACK_MODEL` diatur lewat environment. Parameter saat ini: temperature 0.1, seed 42, `max_completion_tokens` 600. Pada HTTP 429 dilakukan sampai tiga percobaan dengan `Retry-After`/backoff, lalu fallback.

Sumber hanya bisa dipakai setelah admin mengunggah (`POST /api/facility-documents`) dan menerbitkan (`POST /api/facility-documents/{id}/publish`, header `X-Facility-Admin-Token`). Publikasi mengasumsikan reviewer yang ditunjuk telah melakukan pemeriksaan; autentikasi saat ini masih satu token bersama, bukan RBAC multi-admin.

## Rumah sakit, peta, dan denah

- `GET /v1/hospitals/{id}` mengembalikan hanya data yang ditandai terverifikasi.
- `GET /v1/hospitals/{id}/floorplans` dan tautan `viewer_url` menampilkan denah published.
- `GET /v1/hospitals/{id}/route?to={room_id}&from={entry_id}` mengambil rute tersimpan secara deterministik. Default `from=pintu-utama`.
- `POST /admin/hospitals/{id}` memasukkan data RS melalui token admin. Data RS Cut Meutia **belum diisi**; jangan isi koordinat, kontak, jam, atau alamat sebelum diverifikasi sumber resmi.
- `POST /admin/hospitals/{id}/wayfinding` membuat entri draf; `POST /admin/wayfinding/{entry_id}/publish` menerbitkannya setelah tinjauan.
- `POST /admin/hospitals/{id}/floorplans` menerima PDF/DOCX/PNG/JPG dan menyimpan draf. File tidak ditampilkan publik. Endpoint publish sengaja mengembalikan 503 sampai malware scanner dan alur persetujuan benar-benar tersedia.

Semua endpoint admin saat ini menggunakan `FACILITY_ADMIN_TOKEN`; batasi akses jaringan dan rotasi token. Token bersama belum memenuhi role-based access control penuh.

## Batasan yang belum selesai dari SRS

Retrieval saat ini SQLite FTS5 berbasis kata, bukan vector DB; belum ada threshold relevansi semantik, embedding, OCR, malware scanner, kontrol ZDR Groq, alert deprecation terjadwal, expiry alert, audit log terstruktur, dashboard token/429, atau golden set medis 150 kasus. Jangan aktifkan penggunaan klinis/public sebelum reviewer medis dan admin RS menyediakan sumber, data rumah sakit, denah, rute terverifikasi, kontak krisis, persetujuan legal transfer lintas negara, serta golden set. Tidak ada data mitra asli dalam repo dan API mengembalikan 404 untuk RS yang belum terverifikasi.

## Peran tim

- Product Manager: Nazril — mengonfirmasi sumber RS, reviewer, kebijakan, dan prioritas.
- UI/UX: Nasya — persetujuan pemrosesan pihak ketiga, disclaimer, keadaan kosong, viewer aksesibel.
- Frontend: Jelita — integrasi SSE, halaman rumah sakit/denah, tombol “Saya sudah sampai”, dan Google Maps deep link dari koordinat resmi.

FastAPI OpenAPI/Swagger: `/openapi.json` dan `/docs`.
