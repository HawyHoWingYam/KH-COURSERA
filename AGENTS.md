# Repository Guidelines

## Project Structure & Module Organization
- `GeminiOCR/backend`: FastAPI service (`app.py`), config loader, DB layer (`db/`), utilities (`utils/`). Runtime env in `backend/env/.env`.
- `GeminiOCR/frontend`: Next.js (App Router) TypeScript app under `src/app/*` and UI in `src/components/*`.
- `GeminiOCR/docker-compose.*.yml`: Local dev, CI, and prod stacks; `backend.Dockerfile` and `frontend.Dockerfile` build images.
- `.github/workflows/ci-cd.yml`: Multi-stage CI/CD with linting, image build, Trivy scan, and publish.

## Build, Test, and Development Commands
- Backend (local): `cd GeminiOCR/backend && uvicorn app:app --host 0.0.0.0 --port 8000` (requires `DATABASE_URL` or a valid config; SQLite also works).
- Backend tests: `cd GeminiOCR/backend && pytest -q`.
- Backend lint: `pip install ruff && ruff format . && ruff check .`.
- Frontend dev: `cd GeminiOCR/frontend && npm run dev`.
- Frontend build/start: `npm run build && npm run start`.
- Lint frontend: `npm run lint`.
- Docker (dev stack): `docker compose -f GeminiOCR/docker-compose.dev.yml up -d`.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, type hints; snake_case for functions/vars, PascalCase for SQLAlchemy models. Keep endpoints async when IO-bound. Prefer `logging` over prints.
- TypeScript/React: 2-space indent; components PascalCase in `src/components/*`; route files are `page.tsx` under `src/app/...`. Use path alias `@/*` and Tailwind for styling.
- Config: Keep secrets out of VCS. Use `backend/env/.env` and `frontend/.env.local`; expose client vars with `NEXT_PUBLIC_*`.

## Testing Guidelines
- Backend: Pytest with `test_*.py` naming; use `pytest-asyncio` for async handlers. Aim to cover new endpoints and utils. Run `pytest -q` locally and in CI.
- Frontend: No formal tests yet; if adding, prefer Vitest + React Testing Library with colocated `*.test.tsx` near components.

## Commit & Pull Request Guidelines
- Commits: Use Conventional Commits (e.g., `feat:`, `fix:`, `refactor:`, `ci:`, `chore:`). Scope like `feat(frontend): …` is encouraged.
- PRs: Provide a clear description, link issues, list affected service(s) (backend/frontend), include screenshots for UI changes, and note test coverage. Ensure lint passes and CI is green.

## Security & Configuration Tips
- Use `GeminiOCR/.env.example` as a template; never commit secrets. Backend reads config via env → AWS Secrets Manager → config files.
- Common vars: `DATABASE_URL`, `GEMINI_API_KEY_*`, `AWS_*`, `USE_S3_STORAGE=false` for local. Verify health at `/health` and API docs at `/docs`.

