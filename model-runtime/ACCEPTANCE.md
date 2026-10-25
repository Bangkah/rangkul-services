# Acceptance status

Status recorded 25 October 2026. “Implemented” means code/configuration is present; “verified” means the corresponding check actually ran.

| ID | Status | Evidence / remaining work |
|---|---|---|
| AC-01 | Pending | Docker build is defined in CI. Local build could not start because Docker Desktop's Linux engine is not running. |
| AC-02 | Implemented, not image-verified | Dockerfile sets UID/GID 1000 and owns the home/model paths; verify in built image. |
| AC-03 | Implemented, not container-verified | Startup polling is bounded and FastAPI lifespan checks the required model. Verify through image startup. |
| AC-04 | Implemented, not deployment-verified | FastAPI publishes 7860; Ollama host is loopback. Verify exposed ports on the Space. |
| AC-05 | Implemented, pending re-verification | Tests cover only `POST /api/chat`, admin 403, other API routes 404, docs disabled, readiness 503. Re-run CI after the latest route-scope change. |
| AC-06 | Partially verified | Tests cover invalid roles, model, override fields, inference options, and body size. Input/message upper bounds are enforced in schemas; add boundary tests before release. |
| AC-07 | Partially verified | Mock-upstream tests cover NDJSON pass-through, server options, upstream timeout mapping, and disconnect cleanup. Live TTFT and real socket cancellation need integration tests. |
| AC-08 | Prepared, not model-verified | Direct, quoted-context, and system-prompt extraction cases are in `tests/prompt_injection_cases.json`; run against the pinned model and record outcomes. |
| AC-09 | Partially verified | Gate tests verify one active request, four waiters, overflow rejection, and queue timeout. Two simultaneous HTTP calls and memory/OOM behavior need container tests. |
| AC-10 | Partially verified | A synthetic-marker test verifies request validation does not log the body. Run broader request/error-path log scans in CI. |
| AC-11 | Pending | `benchmarks/benchmark.py` collects at least 30 configurable warm samples; run on target hardware and attach the results. |
| AC-12 | Pending | Requires deployed Space restart/sleep and cold-start measurement. |
| AC-13 | Pending | Deployment smoke test uses a token; verify unauthorized access against the actual Private Space. |
| AC-14 | Implemented, not CI-verified | CI workflow runs lint, tests, Docker build; trusted `main` deployment is manually dispatched with protected environment secrets then checks readiness and chat streaming. Configure GitHub environment protection and run it. |

Local checks completed before the latest route-scope revision:

- `pytest`: 11 passed before restricting the API to chat only. The latest local rerun cannot start its TestClient event loop: Python 3.10 blocks while opening the Windows socketpair under this sandbox. CI should verify the latest changes on Linux.
- `ruff check app tests benchmarks`: passed.
- Python syntax compilation: passed.
- Docker image build: not run; Docker daemon unavailable.

No Space was created or deployed from this workspace because no target Space ID or deployment token was supplied.
