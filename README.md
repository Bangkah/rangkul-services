# RANGKUL Services

Repositori untuk runtime model privat dan API backend RANGKUL.

## Komponen

- [`model-runtime/`](model-runtime/README.md): runtime Ollama + Qwen 2.5 untuk Hugging Face Space Docker privat. Hanya `POST /api/chat` yang dibuka di bawah `/api`; prompt anti-diagnosis tersimpan statis di `Modelfile`.
- [`core-api/`](core-api/README.md): layanan FastAPI untuk meneruskan percakapan, mencari isi dokumen mitra, menampilkan fasilitas demo, membuat kode antrean simulasi, dan menyimpan panduan komunitas berstatus `pending`. Target hosting layanan ini terpisah dari Hugging Face.
- [`core-api/TEAM_HANDOFF.md`](core-api/TEAM_HANDOFF.md): panduan integrasi untuk Product Manager Nazril, UI/UX Nasya, dan Frontend Jelita.

## Deploy ke Hugging Face

GitHub Actions menjalankan pemeriksaan kode, pengujian runtime, dan build kedua image Docker saat pull request dan push ke `main`. Pemilik repositori dapat menjalankan workflow secara manual pada `main` untuk mengunggah hanya `model-runtime/` ke Space Docker privat dan menjalankan smoke test streaming.

Atur environment GitHub `production` sebagai environment terlindungi dan tambahkan rahasia berikut:

- `HF_TOKEN`: token dengan izin tulis ke Space. Simpan sebagai secret dan jangan pernah masukkan ke kode. Ganti token yang pernah dibagikan melalui chat setelah deployment berhasil diverifikasi.
- `HF_SPACE_ID`: ID Space dengan format `pemilik/nama-space`.
- `HF_SPACE_URL`: alamat aplikasi Space, misalnya `https://pemilik-nama-space.hf.space`.

**Prasyarat akun:** pembuatan Hugging Face Docker Space privat pada perangkat keras CPU Basic memerlukan langganan PRO untuk akun personal. Akun RANGKUL saat ini belum memiliki Space; upaya membuat `Bangkah/rangkul-ai-runtime` ditolak Hugging Face dengan HTTP 402 karena langganan tersebut belum aktif. Tidak ada perangkat keras berbayar yang dipilih. Lihat [ketentuan dan harga Spaces](https://huggingface.co/docs/hub/spaces-overview#hardware-resources).

Core API juga memerlukan `HF_SPACE_URL` dan token baca di pengelola secret layanan hostingnya untuk memanggil Space privat. Token Hugging Face hanya boleh digunakan di sisi server.

## Staging Core API

Image Core API menerima koneksi pada port 8000 dan menyimpan basis data SQLite di `/data/rangkul/community_guides.sqlite3` serta dokumen mitra di `/data/rangkul/facility-documents`; pasang penyimpanan persisten pada `/data`. Atur `HF_SPACE_URL`, `HF_TOKEN`, `FACILITY_ADMIN_TOKEN`, dan daftar `CORS_ORIGINS` yang tepat di platform hosting. Setelah target staging dipilih, bagikan URL layanan dan Swagger (`/docs`) kepada UI/UX dan Frontend. Data fasilitas saat ini masih contoh sampai Product Manager mengonfirmasi data mitra.
