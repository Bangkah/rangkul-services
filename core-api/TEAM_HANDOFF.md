# Panduan integrasi API RANGKUL berdasarkan peran

## Product Manager — Nazril

- Sediakan dokumen fasilitas mitra terkini (PDF, DOCX, TXT, atau Markdown), lalu pastikan isi dan faktanya sudah diperiksa.
- Konfirmasi nama fasilitas mitra, alamat, koordinat, dan jadwal operasional sebelum mengganti titik demo.
- Pilih layanan staging backend dan tetapkan kebijakan penyimpanan serta peninjauan panduan komunitas.
- Bagikan URL staging final kepada UI/UX dan Frontend setelah deployment siap.

## UI/UX — Nasya

- Gunakan `is_demo` dan `data_status` untuk menandai titik fasilitas contoh. Chat dapat merujuk dokumen mitra yang diunggah; peta tetap memerlukan koordinat terstruktur yang sudah diverifikasi.
- Tampilkan jawaban pendaftaran simulasi sebagai kode antrean demo, bukan janji temu sungguhan.
- Tampilkan panduan komunitas sebagai kiriman berstatus menunggu peninjauan sampai diperiksa.

## Frontend — Jelita

- Gunakan contoh request dan response di bawah. Chat mengirim NDJSON secara streaming dan dapat merujuk dokumen fasilitas mitra yang sudah diunggah.
- Panggil hanya alamat backend yang telah dikonfigurasi. Jangan pernah menyimpan `GROQ_API_KEY` atau token provider lain di kode browser.
- Sampaikan alamat frontend yang tepat kepada pemilik backend agar dapat ditambahkan ke `CORS_ORIGINS`.

**URL dasar staging:** belum tersedia; gunakan `{{STAGING_URL}}` setelah hosting disiapkan.

FastAPI membuat Swagger di `{{STAGING_URL}}/docs` setelah layanan berjalan.

Rute pemeriksaan container adalah `GET /healthz` dan mengembalikan `{"status":"alive"}`.

## `POST /api/chat`

Request JSON:

```json
{
  "messages": [
    {"role": "user", "content": "Bagaimana cara mencari layanan kesehatan?"}
  ]
}
```

Response berupa streaming `application/x-ndjson` dari provider yang dipilih di backend (`groq` atau `ollama`). Prompt sistem untuk mencegah diagnosis medis ditambahkan oleh server; pesan `system` dari klien dan kolom tambahan akan ditolak. Chat mencari kutipan yang relevan di indeks dokumen mitra SQLite FTS5 dan menyisipkannya sebagai konteks yang tidak tepercaya. Pencarian ini berbasis kata kunci, bukan kemiripan vektor. Mode Groq mengirim percakapan dan kutipan RAG ke layanan eksternal; gunakan data demo saja.

## `GET/POST /api/facility-documents` dan `DELETE /api/facility-documents/{id}`

Rute khusus petugas ini memakai `X-Facility-Admin-Token`. Unggah melalui kolom form multipart `file` dengan format PDF, DOCX, TXT, atau Markdown. API mengembalikan ID dokumen dan jumlah bagian yang diindeks. `GET` menampilkan daftar dokumen yang diindeks; `DELETE` menghapus berkas asli dan indeksnya. Simpan token admin di backend. Ekstraksi teks tidak menjalankan OCR pada PDF hasil pindai.

## `GET /api/facilities`

Contoh response JSON: `{ "facilities": [...], "data_status": "demo" }`. Setiap item memiliki `id`, `name`, `is_demo`, `address`, `schedule`, `timezone`, dan `coordinates` (`latitude`, `longitude`). Semua titik saat ini hanya data contoh; jangan tampilkan sebagai klinik mitra sungguhan.

## `POST /api/register-dummy`

Request JSON (hanya teks biasa; tidak menerima unggahan foto KTP):

```json
{"text": "Saya ingin simulasi pendaftaran."}
```

Contoh response JSON: `{"registration_code":"RGKL-DEMO-0001","status":"confirmed","message":"..."}`. Kode statis hanya untuk demo antarmuka dan tidak membuat antrean sungguhan.

## `POST /api/community-guide`

Request JSON:

```json
{"text": "Masuk dari gerbang utama, lalu belok kiri."}
```

Response JSON berisi `id` yang dibuat server, `text` yang dikirim, `status: "pending"`, dan `created_at` dalam UTC. Teks disimpan di SQLite.

## Error dan batasan saat ini

Payload tidak valid mengembalikan error validasi FastAPI (422). Chat mengembalikan 503 jika provider belum dikonfigurasi, 502 jika layanan model bermasalah, 429 saat Groq melaporkan kuota habis, dan 504 jika waktu tunggu habis. Fasilitas masih data contoh dan URL staging belum tersedia. Gunakan penyimpanan persisten untuk `/data/rangkul`, baik untuk basis data/indeks maupun dokumen yang diunggah.
