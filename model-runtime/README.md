# Runtime Ollama lokal RANGKUL AI

Runtime Docker ini menyiapkan `qwen2.5:1.5b` melalui Ollama beserta proxy FastAPI yang hanya membuka `POST /api/chat`. Untuk demo cepat, Core API dapat memakai Groq; untuk demonstrasi privasi, pilih `LLM_PROVIDER=ollama` agar prompt tetap berada di Docker lokal.

## Menjalankan bersama Core API

Dari root repositori, salin `core-api/.env.example` menjadi `core-api/.env`. Untuk mode lokal, atur:

```dotenv
LLM_PROVIDER=ollama
LOCAL_MODEL_URL=http://127.0.0.1:7860
```

Lalu jalankan profil Ollama:

```powershell
docker compose --profile ollama up --build
```

Compose membangun model ke dalam image runtime dan tidak mempublikasikan port Ollama ke host. Hanya Core API yang tersedia pada `http://localhost:8000`; container Core API meneruskan inferensi ke proxy internal `model-runtime:7860`.

## Menjalankan runtime saja

```sh
docker build -t rangkul-ai-runtime ./model-runtime
docker run --rm -p 7860:7860 rangkul-ai-runtime
```

Ollama hanya mendengarkan di `127.0.0.1:11434` dalam container. Proxy menolak rute administrasi Ollama dan semua rute API selain `/api/chat`. Pesan `system` dari klien ditolak; prompt keselamatan berada di `Modelfile`.

## Identitas dan batas runtime

- Model sumber: `qwen2.5:1.5b-instruct-q4_K_M` (Ollama ID `65ec06548149`).
- Image build Ollama: `ollama/ollama:0.40.11-rocm`; pustaka ROCm dihapus dari image akhir.
- Image dasar Python: `3.12.8-slim-bookworm`; dependensi runtime diverifikasi menggunakan hash.
- Proxy mendukung streaming NDJSON, membatasi request hingga 128 KiB dan 12.000 karakter, serta membatasi output hingga 512 token.

Model diunduh saat image Docker dibangun. Setelah image selesai dibuat, mode Ollama dapat berjalan tanpa API key Groq dan tanpa koneksi ke provider inferensi eksternal.
