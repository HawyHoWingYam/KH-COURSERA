# Repository Guidelines

This repo contains a FastAPI backend and a Next.js (App Router) frontend housed under `GeminiOCR/`. Use this guide to build, test, and contribute consistently.

## Project Structure & Module Organization
- `GeminiOCR/backend`: FastAPI service (`app.py`), DB layer (`db/`), utilities (`utils/`), scripts (`scripts/`), tests in `backend/tests/`, sample assets in `uploads/`.
- `GeminiOCR/frontend`: Next.js app under `src/app/*`; UI in `src/components/*`; shared helpers in `src/lib/*`; static assets in `public/`.
- Orchestration: `GeminiOCR/docker-compose.simple.yml` for local stack; CI in `.github/workflows/ci-cd.yml`.

## Build, Test, and Development Commands
- Backend dev: `cd GeminiOCR/backend && uvicorn app:app --host 0.0.0.0 --port 8000` (requires `DATABASE_URL` or valid local config; SQLite can be used).
- Backend tests: `cd GeminiOCR/backend && pytest -q`.
- Backend lint/format: `pip install ruff && ruff format . && ruff check .`.
- Frontend dev: `cd GeminiOCR/frontend && npm run dev`.
- Frontend build/start: `npm run build && npm run start`.
- Docker (local): `docker compose -f GeminiOCR/docker-compose.simple.yml up -d`.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indents, type hints; `snake_case` for functions/vars; `PascalCase` for SQLAlchemy models. Keep IO-bound endpoints `async`; prefer `logging` over prints.
- TypeScript/React: 2-space indents; components `PascalCase` in `src/components/*`; route files are `page.tsx` under `src/app/...`. Use path alias `@/*` and Tailwind.

## Testing Guidelines
- Backend: Pytest; name tests `test_*.py`. Use `pytest-asyncio` for async handlers. Aim to cover new endpoints and utils. Run `pytest -q` locally and in CI.
- Frontend: Optional for now; if adding, prefer Vitest + React Testing Library with colocated `*.test.tsx`.

## Commit & Pull Request Guidelines
- Commits: Conventional Commits (e.g., `feat(frontend): …`, `fix(backend): …`).
- PRs: Clear description, link issues, list affected service(s), include screenshots for UI changes, and note test coverage. Ensure lint passes and CI is green.

## Security & Configuration Tips
- Do not commit secrets. Use `GeminiOCR/frontend/.env.local` and environment variables for the backend. Expose client vars with `NEXT_PUBLIC_*`.
- Common vars: `DATABASE_URL`, `AWS_*`, `NEXT_PUBLIC_API_URL`. Verify backend health at `/health` and API docs at `/docs`.
