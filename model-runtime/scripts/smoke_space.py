"""Tunggu Space hasil deployment, lalu periksa hidup, kesiapan, dan streaming."""

import json
import os
import time

import httpx


def main():
    base_url = os.environ["HF_SPACE_URL"].rstrip("/")
    token = os.environ["HF_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + 600

    with httpx.Client(timeout=httpx.Timeout(connect=10, read=300)) as client:
        while time.monotonic() < deadline:
            try:
                live = client.get(f"{base_url}/healthz", headers=headers)
                ready = client.get(f"{base_url}/readyz", headers=headers)
                if live.status_code in (401, 403) or ready.status_code in (401, 403):
                    raise SystemExit(
                        "Akses ke Space ditolak; periksa keanggotaan Space privat dan cakupan HF_TOKEN."
                    )
                if live.status_code == 200 and ready.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(15)
        else:
            raise SystemExit("Space belum siap setelah 10 menit.")

        with client.stream(
            "POST",
            f"{base_url}/api/chat",
            headers=headers,
            json={
                "model": "rangkul-llm",
                "messages": [{"role": "user", "content": "Jawab satu kata: siap."}],
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            got_chunk = False
            got_done = False
            for line in response.iter_lines():
                if not line:
                    continue
                got_chunk = True
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise SystemExit("Streaming /api/chat mengembalikan error.")
                got_done = got_done or chunk.get("done") is True
        if not got_chunk or not got_done:
            raise SystemExit("Streaming NDJSON /api/chat dari Ollama belum lengkap.")
        print("Pemeriksaan hidup, kesiapan, dan inferensi streaming Space berhasil.")


if __name__ == "__main__":
    main()
