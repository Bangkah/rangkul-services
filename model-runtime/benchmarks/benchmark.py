"""Warm-request benchmark; run against an already-ready Space with 30+ samples."""

import asyncio
import json
import os
import statistics
import time

import httpx

URL = os.environ["RANGKUL_URL"].rstrip("/")
TOKEN = os.environ["HF_TOKEN"]
SAMPLES = int(os.getenv("SAMPLES", "30"))
PROMPT = (
    "Jelaskan secara umum praktik menjaga privasi data pribadi saat menggunakan layanan digital. "
    * 40
)


async def main():
    if SAMPLES < 30:
        raise SystemExit(
            "SAMPLES must be at least 30 to satisfy the benchmark acceptance criteria."
        )
    headers = {"Authorization": f"Bearer {TOKEN}"}
    ttfts, totals, rates, errors = [], [], [], 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300)) as client:
        for _ in range(SAMPLES):
            start = time.perf_counter()
            first = None
            token_count = 0
            eval_seconds = 0
            try:
                async with client.stream(
                    "POST",
                    f"{URL}/api/generate",
                    headers=headers,
                    json={"model": "rangkul-llm", "prompt": PROMPT, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if first is None:
                            first = time.perf_counter()
                        data = json.loads(line)
                        if data.get("done"):
                            token_count = int(data.get("eval_count", 0))
                            eval_seconds = int(data.get("eval_duration", 0)) / 1e9
                end = time.perf_counter()
                if first is None:
                    errors += 1
                    continue
                ttfts.append(first - start)
                totals.append(end - start)
                rates.append(token_count / max(eval_seconds, 1e-9))
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                errors += 1

    def stats(values):
        if not values:
            return {"median": None, "p95": None}
        ordered = sorted(values)
        return {
            "median": statistics.median(ordered),
            "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
        }

    print(
        json.dumps(
            {
                "samples": SAMPLES,
                "successes": len(totals),
                "errors": errors,
                "ttft_seconds": stats(ttfts),
                "total_latency_seconds": stats(totals),
                "output_tokens_per_second": stats(rates),
                "input_characters": len(PROMPT),
                "hardware": "record Space CPU/RAM here",
                "model": "rangkul-llm",
                "condition": "warm",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
