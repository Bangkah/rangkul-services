# RANGKUL Core API (staging)

Layanan FastAPI untuk tim RANGKUL. API meneruskan percakapan ke Hugging Face Space privat, menyediakan titik fasilitas demo, membuat kode antrean simulasi, menyimpan panduan komunitas dengan status `pending`, dan mengindeks dokumen fasilitas mitra sebagai referensi percakapan. Lihat [`TEAM_HANDOFF.md`](TEAM_HANDOFF.md) untuk pembagian integrasi berdasarkan peran.

## Menjalankan secara lokal

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Isi HF_SPACE_URL, HF_TOKEN, dan FACILITY_ADMIN_TOKEN di .env atau pengelola rahasia.
uvicorn main:app --reload --env-file .env
```

Buka `/docs` untuk dokumentasi Swagger/OpenAPI. Isi `HF_SPACE_URL` dengan alamat HTTPS `*.hf.space`; simpan `HF_TOKEN` di pengelola rahasia backend. Jangan pernah kirim token Hugging Face ke browser.

Atur `CORS_ORIGINS` sesuai alamat frontend yang benar sebelum staging; nilai awal hanya mengizinkan alamat pengembangan lokal. Image Docker tersedia; pasang volume persisten pada `/data` agar panduan komunitas tetap tersimpan setelah container dimulai ulang.

```powershell
docker build -t rangkul-core-api .
docker volume create rangkul-core-data
docker run --rm -p 8000:8000 --env-file .env --mount source=rangkul-core-data,target=/data rangkul-core-api
```

`GET /api/facilities` saat ini mengembalikan **lokasi demo buatan**, bukan mitra terkonfirmasi. Ganti data ini dengan informasi mitra yang sudah diverifikasi sebelum rilis. SQLite menyimpan panduan komunitas dan indeks dokumen teks lengkap. Berkas asli disimpan di `FACILITY_DOCS_DIR`; pasang volume persisten dan atur `COMMUNITY_DB_PATH` serta `FACILITY_DOCS_DIR` untuk staging.

## Dokumen fasilitas mitra (RAG)

Petugas yang berwenang dapat mengunggah berkas PDF, DOCX, TXT, atau Markdown. API mengekstrak teks, membaginya menjadi beberapa bagian yang saling tumpang tindih, menyimpan indeks SQLite FTS5, lalu memilih kutipan yang relevan untuk setiap permintaan `/api/chat`. Berkas asli juga disimpan agar tim dapat mengelola sumbernya. Rute daftar, unggah, dan hapus dokumen memerlukan `FACILITY_ADMIN_TOKEN` pada header `X-Facility-Admin-Token`; simpan token ini di backend dan jangan masukkan ke frontend. Form unggah tersedia di Swagger `/docs`.

Versi pencarian pertama memakai pencarian teks penuh berbasis kata kunci, belum memakai embedding atau kemiripan vektor. PDF hasil pindai yang tidak memiliki teks terpilih akan ditolak dengan petunjuk OCR; ubah menjadi PDF yang teksnya dapat dicari sebelum diunggah. Dokumen yang diunggah diperlakukan sebagai data referensi yang tidak tepercaya di prompt percakapan. Indeks hanya boleh berisi dokumen fasilitas terkini yang sudah diperiksa dan disetujui petugas.

URL staging belum tersedia karena target hosting dan kredensial Hugging Face Space belum dikonfigurasi.
