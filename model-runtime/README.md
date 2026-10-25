---
title: Runtime Privat RANGKUL AI
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# Runtime LLM Privat RANGKUL AI

Hugging Face Space Docker privat yang menjalankan Ollama dan FastAPI proxy untuk `qwen2.5:1.5b`. Hanya `POST /api/chat` yang dibuka di bawah `/api`; rute operasional `/healthz` dan `/readyz` juga tersedia. Ollama hanya menerima koneksi dari loopback.

## Menjalankan secara lokal

```sh
docker build -t rangkul-ai-runtime .
docker run --rm -p 7860:7860 rangkul-ai-runtime
```

Atur visibilitas Space menjadi **Private**. Backend menyimpan token baca Hugging Face di pengelola rahasianya sendiri dan mengirimkannya melalui `Authorization: Bearer ...`; jangan pernah memasukkan token ke image ini atau ke kode browser.

Respons inferensi selalu berupa streaming NDJSON dari Ollama (`application/x-ndjson`) dan diakhiri `done: true`. Error yang diketahui sebelum streaming dimulai menghasilkan HTTP 502/504; error setelah header streaming terkirim muncul sebagai satu bagian error NDJSON. `options` hanya menerima `stop`; model, konteks, temperatur, seed, dan batas keluaran ditetapkan server. Ukuran request maksimal 128 KiB, seluruh masukan maksimal 12.000 karakter, maksimal 32 pesan dan 512 token keluaran, satu inferensi aktif serta empat antrean dengan batas tunggu 30 detik.

| Rute | Metode | Kegunaan |
|---|---|---|
| `/healthz` | GET | Pemeriksaan hidup layanan |
| `/readyz` | GET | Kesiapan Ollama dan model |
| `/api/chat` | POST | Chat streaming |

Rute administratif Ollama mengembalikan 403; semua rute API lain selain `/api/chat` mengembalikan 404. Pesan `system` dari klien dan kolom request tambahan ditolak; prompt sistem untuk mencegah diagnosis medis hanya berada di `Modelfile` yang sudah dibangun ke dalam model.

## Identitas build

- Tag model sumber: `qwen2.5:1.5b-instruct-q4_K_M` (ID Ollama `65ec06548149`; build gagal jika ID ini berubah).
- Image build Ollama: `ollama/ollama:0.40.11-rocm` (runtime CPU resmi tetap digunakan; pustaka ROCm dihapus dari image akhir).
- Image dasar Python: `3.12.8-slim-bookworm`; dependensi transitif di `requirements.lock` diverifikasi menggunakan hash.
- ID model sumber dan model kustom hasil build: `/app/model-identity.json`; `/api/tags` menampilkan digest kustom terkini.
- Port Space: `7860`; Ollama: `127.0.0.1:11434`.

Model sumber diunduh saat build dan ID modelnya dibandingkan dengan nilai yang diharapkan. Build mencatat ID model sumber dan kustom ke `/app/model-identity.json`; digest kustom juga tersedia melalui `/api/tags`. Kinerja CPU, alokasi perangkat keras, dan akses ke Space privat tetap perlu diverifikasi setelah deploy.

## Deployment tepercaya

Job deploy GitHub Actions hanya berjalan setelah pemeriksaan lulus dan maintainer menjalankannya secara manual pada `main`. Buat Hugging Face Space terlebih dahulu dengan visibilitas **Private** dan SDK Docker, lalu tambahkan secret environment GitHub terlindungi: `HF_TOKEN` (izin tulis ke Space), `HF_SPACE_ID` (`pemilik/nama-space`), dan `HF_SPACE_URL` (alamat aplikasi Space). Script deployment menolak Space publik atau yang tidak menggunakan SDK Docker. Smoke test menunggu kesiapan hingga 10 menit dan memeriksa streaming chat. Pull request tidak menerima secret deployment.

Akun Hugging Face yang digunakan belum memiliki Space RANGKUL. Pembuatan Docker Space privat pada CPU Basic ditolak dengan HTTP 402 karena akun personal memerlukan langganan PRO untuk menjalankan Space komputasi. Deployment dapat dilanjutkan setelah prasyarat akun dipenuhi; dokumentasi biaya dan perangkat keras tersedia di [Spaces Overview](https://huggingface.co/docs/hub/spaces-overview#hardware-resources).

Lihat [`ACCEPTANCE.md`](ACCEPTANCE.md) untuk status pemeriksaan lokal dan hal-hal yang baru dapat diverifikasi setelah Space di-deploy.
