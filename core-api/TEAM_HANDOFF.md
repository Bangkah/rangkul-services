# Serah terima integrasi RANGKUL AI v2

## Peran tim

- **Product Manager — Nazril:** minta data resmi RS Cut Meutia (alamat, koordinat, jam, kontak, akses), denah aktual, admin pemilik data, reviewer medis, aturan nama netral, nomor darurat terkurasi, dan keputusan legal atas transfer data ke penyedia AI.
- **UI/UX — Nasya:** rancang layar persetujuan pihak ketiga sebelum chat, peringatan agar tidak memasukkan identitas/hasil tes, disclaimer, state “informasi belum tersedia”, viewer denah dengan zoom/kontras/alt text, dan tombol eksplisit “Saya sudah sampai”.
- **Frontend — Jelita:** konsumsi SSE `POST /v1/chat`; tampilkan citations/disclaimer; buat Google Maps direction link dari koordinat RS; jangan kirim koordinat pengguna ke backend/Groq. Indoor route menggunakan endpoint route deterministik.

## API penting

Swagger lokal: `http://localhost:8000/docs`; health: `GET /health`. URL staging belum disiapkan.

### `POST /v1/chat`

Header `Content-Type: application/json`; body:

```json
{
  "consent": true,
  "messages": [{"role":"user","content":"Apa yang perlu disiapkan sebelum tes?"}]
}
```

Response `text/event-stream`: event `delta` berisi `text`, kemudian event `done` berisi `citations` (`title`, `version`, `source`) dan `disclaimer`. Tanpa dokumen published yang cocok, backend mengembalikan respons aman “belum tersedia” dan tidak meminta jawaban bebas ke Groq. Konten dokumen tidak tepercaya. Pola NIK, email, telepon direduksi sebelum Groq. Riwayat dibatasi server. `system` dari klien tidak diterima.

### RS dan rute

- `GET /v1/hospitals/{id}` — alamat, koordinat, jam, telepon, akses; hanya RS yang ditandai terverifikasi.
- `GET /v1/hospitals/{id}/floorplans` — daftar file published beserta versi/tanggal dan `viewer_url`.
- `GET /v1/hospitals/{id}/route?to={room_id}&from={entry_id}` — langkah dari graf tersimpan, tidak dihasilkan LLM. Default titik awal `pintu-utama`.

Saat ini tidak ada data rumah sakit sebenarnya. Semua GET mengembalikan 404 sampai pihak berwenang memasukkan dan memverifikasi data.

### Admin dokumen dan data

Semua rute admin sementara memerlukan header `X-Facility-Admin-Token`; jangan pernah masukkan token ini di browser. Upload dokumen edukasi lewat `POST /api/facility-documents` (multipart `file`, opsional `source`, `version`), lalu terbitkan setelah review menggunakan `POST /api/facility-documents/{id}/publish` dengan `{"reviewed_by":"...","version":"..."}`. Dokumen baru berstatus draf dan tidak bisa diretrieve sebelum dipublish.

Data RS dimasukkan lewat `POST /admin/hospitals/{id}`. Wayfinding: buat draf `POST /admin/hospitals/{id}/wayfinding`, kemudian `POST /admin/wayfinding/{entry_id}/publish`. Denah asli bisa diunggah ke `POST /admin/hospitals/{id}/floorplans`; tetap draft. Penerbitan file sengaja dinonaktifkan sampai malware scanner dan approval multi-peran dipasang.

## Batasan dan keputusan sebelum rilis

Index saat ini SQLite FTS5 keyword, bukan vector database. Belum ada OCR, scanner malware, RBAC multi-admin, expiry alert, scheduled model deprecation check, ZDR proof, metrik token/429, kontak krisis yang dikurasi, atau golden set medis 150 kasus. Semua itu butuh layanan, reviewer, atau data dari tim. Dokumen medis/denah tidak boleh dipublikasikan sebelum ditinjau manusia. Groq adalah pemrosesan pihak ketiga di luar negeri; persetujuan UI dan tinjauan legal UU PDP wajib sebelum penggunaan publik.
