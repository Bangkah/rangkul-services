import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import AdmissionGate, RequestLimitsMiddleware, app, proxy_stream


def test_routes_and_admin_block():
    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/healthz").status_code == 200
    assert c.get("/unknown").status_code == 404
    for path in ("pull", "delete", "create", "copy", "ps"):
        assert c.post(f"/api/{path}").status_code == 403
    assert c.get("/api/not-an-endpoint").status_code == 404
    assert c.get("/docs").status_code == 404
    assert c.get("/api/chat").status_code == 405
    assert c.get("/readyz").status_code == 503
    assert c.get("/api/tags").status_code == 404


def test_validation_rejects_roles_and_overrides():
    c = TestClient(app, raise_server_exceptions=False)
    assert (
        c.post(
            "/api/chat", json={"messages": [{"role": "system", "content": "x"}]}
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "x"}], "system": "x"},
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/chat",
            json={
                "model": "other-model",
                "messages": [{"role": "user", "content": "x"}],
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "x" * 12_001}]},
        ).status_code
        == 422
    )
    assert c.post("/api/generate", json={"prompt": "x"}).status_code == 404
    assert (
        c.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "x"}] * 33},
        ).status_code
        == 422
    )


def test_body_limit():
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(
        "/api/chat",
        content=b" " * (128 * 1024 + 1),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413


def test_container_and_space_config_invariants():
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "USER 1000:1000" in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert "OLLAMA_HOST=127.0.0.1:11434" in dockerfile
    assert "OLLAMA_NUM_PARALLEL=1" in dockerfile
    assert "OLLAMA_MAX_LOADED_MODELS=1" in dockerfile
    assert "OLLAMA_MAX_QUEUE=4" in dockerfile
    assert (root / "build_model.sh").is_file()
    assert (root / "proxy.py").is_file()
    assert "sdk: docker" in readme and "app_port: 7860" in readme


def test_body_limit_middleware_preserves_disconnect_events():
    async def run():
        seen = []
        messages = [
            {"type": "http.request", "body": b"", "more_body": False},
            {"type": "http.disconnect"},
        ]

        async def receive():
            return messages.pop(0)

        async def send(message):
            pass

        async def downstream(scope, replay, send):
            await replay()
            seen.append(await replay())

        scope = {"type": "http", "method": "GET", "path": "/healthz", "headers": []}
        await RequestLimitsMiddleware(downstream)(scope, receive, send)
        assert seen == [{"type": "http.disconnect"}]

    asyncio.run(run())


def test_gate_serializes():
    async def run():
        gate, active, maximum = AdmissionGate(), 0, 0

        async def task():
            nonlocal active, maximum
            async with gate.slot():
                active += 1
                maximum = max(maximum, active)
                await asyncio.sleep(0.02)
                active -= 1

        await asyncio.gather(task(), task())
        assert maximum == 1

    asyncio.run(run())


def test_gate_rejects_overflow_and_queue_timeout():
    async def run():
        gate = AdmissionGate()
        gate.queue_timeout = 0.02
        async with gate.slot():

            async def queued():
                async with gate.slot():
                    await asyncio.sleep(0)

            waiting = [asyncio.create_task(queued()) for _ in range(4)]
            while gate.waiting < 4:
                await asyncio.sleep(0)
            with pytest.raises(HTTPException) as full:
                await gate.slot().__aenter__()
            assert full.value.status_code == 503
        await asyncio.gather(*waiting)
        async with gate.slot():
            timed_out = asyncio.create_task(queued())
            result = await asyncio.gather(timed_out, return_exceptions=True)
            assert isinstance(result[0], HTTPException) and result[0].status_code == 503

    asyncio.run(run())


def test_stream_is_forwarded_and_server_options_are_enforced():
    async def run():
        seen = {}

        async def upstream(request):
            seen.update(json.loads(await request.aread()))
            return httpx.Response(
                200, content=b'{"response":"hello","done":false}\n{"done":true}\n'
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        state = SimpleNamespace(ready=True, gate=AdmissionGate(), client=client)

        async def connected():
            return False

        request = SimpleNamespace(
            app=SimpleNamespace(state=state), is_disconnected=connected
        )
        response = await proxy_stream(
            request,
            {
                "model": "client-selected-model",
                "messages": [{"role": "user", "content": "test"}],
                "stream": False,
                "options": {"temperature": 1.8, "num_predict": 9999, "stop": ["END"]},
            },
        )
        chunks = [chunk async for chunk in response.body_iterator]
        await client.aclose()
        assert b"".join(chunks) == b'{"response":"hello","done":false}\n{"done":true}\n'
        assert seen["model"] == "rangkul-llm" and seen["stream"] is True
        assert seen["options"] == {
            "num_ctx": 4096,
            "num_predict": 512,
            "temperature": 0.1,
            "seed": 42,
            "stop": ["END"],
        }
        assert state.gate.active is False

    asyncio.run(run())


def test_upstream_timeout_maps_to_504_and_releases_slot():
    async def run():
        async def timeout_handler(request):
            raise httpx.ReadTimeout("synthetic upstream timeout")

        client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
        state = SimpleNamespace(ready=True, gate=AdmissionGate(), client=client)

        async def connected():
            return False

        request = SimpleNamespace(
            app=SimpleNamespace(state=state), is_disconnected=connected
        )
        with pytest.raises(HTTPException) as result:
            await proxy_stream(
                request, {"messages": [{"role": "user", "content": "x"}]}
            )
        assert result.value.status_code == 504
        assert state.gate.active is False
        await client.aclose()

    asyncio.run(run())


def test_client_disconnect_closes_stream_and_releases_slot():
    async def run():
        async def upstream(request):
            return httpx.Response(200, content=b'{"response":"partial","done":false}\n')

        client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        state = SimpleNamespace(ready=True, gate=AdmissionGate(), client=client)

        async def disconnected():
            return True

        request = SimpleNamespace(
            app=SimpleNamespace(state=state), is_disconnected=disconnected
        )
        response = await proxy_stream(
            request, {"messages": [{"role": "user", "content": "x"}]}
        )
        chunks = [chunk async for chunk in response.body_iterator]
        assert chunks == [] and state.gate.active is False
        await client.aclose()

    asyncio.run(run())


def test_validation_does_not_log_sensitive_body(caplog):
    marker = "SYNTHETIC-SENSITIVE-MARKER-1937"
    c = TestClient(app, raise_server_exceptions=False)
    assert (
        c.post(
            "/api/chat", json={"messages": [{"role": "system", "content": marker}]}
        ).status_code
        == 422
    )
    assert marker not in caplog.text
