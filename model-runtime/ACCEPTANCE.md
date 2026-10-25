# Status penerimaan

Status dicatat pada 25 Oktober 2026. “Sudah dibuat” berarti kode/konfigurasi tersedia; “terverifikasi” berarti pemeriksaan benar-benar sudah dijalankan.

| ID | Status | Bukti / pekerjaan tersisa |
|---|---|---|
| AC-01 | Menunggu | Build Docker tersedia di CI. Build lokal belum dapat dimulai karena Docker Engine tidak aktif. |
| AC-02 | Dibuat, belum diverifikasi pada image | Dockerfile menetapkan UID/GID 1000 dan kepemilikan direktori home/model; verifikasi setelah image berhasil dibangun. |
| AC-03 | Dibuat, belum diverifikasi dalam container | Polling startup memiliki batas waktu dan siklus hidup FastAPI memeriksa model. Verifikasi setelah container berjalan. |
| AC-04 | Dibuat, belum diverifikasi saat deployment | FastAPI membuka port 7860; Ollama hanya mendengarkan pada loopback. Verifikasi port Space setelah deploy. |
| AC-05 | Dibuat, perlu diverifikasi ulang | Pengujian mencakup hanya `POST /api/chat`, admin 403, rute API lain 404, dokumentasi dinonaktifkan, dan readiness 503. Jalankan kembali CI setelah perubahan rute terakhir. |
| AC-06 | Terverifikasi sebagian | Pengujian mencakup role, model, kolom override, opsi inferensi, dan ukuran body yang salah. Batas maksimum input/pesan diterapkan pada skema; tambahkan pengujian batas sebelum rilis. |
| AC-07 | Terverifikasi sebagian | Pengujian upstream tiruan mencakup penerusan NDJSON, opsi server, pemetaan timeout upstream, dan pembersihan saat koneksi terputus. TTFT langsung dan pembatalan socket nyata masih memerlukan pengujian integrasi. |
| AC-08 | Disiapkan, belum diverifikasi pada model | Skenario pengambilan prompt langsung, kutipan konteks, dan ekstraksi system prompt tersedia di `tests/prompt_injection_cases.json`; jalankan pada model yang dipatok dan catat hasilnya. |
| AC-09 | Terverifikasi sebagian | Pengujian gerbang mencakup satu request aktif, empat request antre, penolakan antrean penuh, dan batas tunggu antrean. Dua request HTTP bersamaan serta penggunaan memori/OOM masih memerlukan pengujian container. |
| AC-10 | Terverifikasi sebagian | Pengujian penanda sintetis memastikan validasi request tidak mencatat isi body. Jalankan pemindaian log untuk jalur request/error yang lebih luas di CI. |
| AC-11 | Menunggu | `benchmarks/benchmark.py` mengumpulkan sedikitnya 30 sampel saat model sudah siap; jalankan pada perangkat target dan lampirkan hasilnya. |
| AC-12 | Menunggu | Memerlukan Space yang sudah di-deploy untuk mengukur restart/tidur dan waktu cold start. |
| AC-13 | Menunggu | Smoke test deployment memakai token; verifikasi akses tanpa izin terhadap Space privat yang sebenarnya. |
| AC-14 | Dibuat, deployment tertahan | CI menjalankan lint, test, dan build Docker. Hugging Face menolak pembuatan Docker Space privat dengan HTTP 402 karena akun personal perlu berlangganan PRO untuk menggunakan CPU Basic. Tidak ada Space atau perangkat keras berbayar yang dibuat/dipilih. |

Pemeriksaan lokal yang dilakukan sebelum perubahan rute terakhir:

- `pytest`: 11 lolos sebelum API dibatasi hanya ke chat. Pengujian lokal terakhir tidak dapat memulai event loop TestClient karena Python 3.10 macet saat membuka socketpair Windows di sandbox ini. CI Linux perlu memverifikasi perubahan terakhir.
- `ruff check app tests benchmarks`: lolos.
- Kompilasi sintaks Python: lolos.
- Build image Docker: belum dijalankan karena Docker daemon tidak tersedia.

Percobaan deployment Hugging Face pada 25 Oktober 2026 berhasil mengautentikasi akun `Bangkah` dan memastikan belum ada Space RANGKUL. Pembuatan `Bangkah/rangkul-ai-runtime` ditolak dengan HTTP 402 yang menyatakan akun perlu PRO untuk membuat Docker Space CPU Basic. Karena Space tidak berhasil dibuat, unggahan kode dan smoke test endpoint belum dapat dijalankan.
