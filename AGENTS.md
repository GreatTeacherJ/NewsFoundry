# Repository instructions

- This repo has two independent projects; run commands from the relevant package directory (`backend/` or `frontend/`). There is no root task runner.
- Backend: Python 3.13+ with `uv`. Install with `uv sync` (CI uses `uv sync --locked`); run tests with `uv run pytest -q` and lint with `uv run ruff check src tests`. Tests use an in-memory SQLite database, so PostgreSQL is not needed for tests. Local app startup uses `.env` and PostgreSQL; see `README.md`.
- Frontend: use Node 22 and npm. Install with `npm ci`; checks are `npm run lint`, `npx tsc --noEmit`, then `npm run build`. Keep `--webpack` in the build command; it is required by the configured `frontend/package.json` script.
- For local frontend development, set `NEXT_PUBLIC_API_URL` in `frontend/.env.local`; `frontend/src/lib/api.ts` defaults to `http://localhost:8000` when unset. TypeScript is strict and `@/*` maps to `frontend/src/*`.
- Backend API and persistence are wired through `backend/src/main.py`, `backend/src/models.py`, and `backend/src/database.py`; endpoint tests are in `backend/tests/test_api.py`. Preserve user ownership checks on every discussion/message/review access; cross-user resources return 404.
- Assistant replies and press reviews are currently demo placeholders, not live AI/news integrations. Verify `README.md` before assuming those integrations exist.
- `backend/Dockerfile` expects the repository root as its Docker build context because its `COPY` paths begin with `backend/`.
