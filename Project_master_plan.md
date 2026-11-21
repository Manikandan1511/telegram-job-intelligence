# Project Master Plan

This project began with `Project_report.md` and no application source files. The project is built as a local-first single-user app to keep hosting and database costs at zero.

## Implemented
- [x] FastAPI backend, persistent SQLite for the personal Mac setup, optional PostgreSQL URL configuration, React dashboard, CORS, API docs, and Docker Compose local restart setup.
- [x] Single-user registration/login with scrypt password hashes, signed expiring JWTs, and loopback-only binding.
- [x] Telegram login, two-step flow, account reuse, code-send retry/rate-limit handling, source selection, disconnect, incremental sync, background polling, and serialized shared client.
- [x] Resume PDF/DOCX/TXT parsing, private file persistence, editable candidate profile, and version history.
- [x] Job classification/extraction with deterministic fallback and validated optional Agentia-Max structured output.
- [x] Match scoring, explicit deadline/graduation checks, duplicate detection with Telegram source references, search, filters, recommendations, and category summaries.
- [x] Application statuses and notes, Kanban board, dashboard charts, and CSV export.
- [x] Optional private bot commands, first-chat registration, immediate alerts, settings, test alert, and daily digest.
- [x] Secrets and local state excluded from Git; setup, architecture, API, deployment, troubleshooting, and implementation status docs.
- [x] Latest logs addressed: matching ORM profile crash, repeated/slow Telegram code requests, resume upload confirmation, and session SQLite contention.

## Remaining for full production parity with the report
- Multi-user data isolation (current release is one local owner).
- Rich, verified candidate/job extraction and full eligibility rule coverage.
- Telegram edited/deleted message event handling and more detailed score factor explanations.
- Full automated unit, integration, and security test coverage. The user asked to finish implementation before the test pass.

See `IMPLEMENTATION_STATUS.md` for current scope and `docs/` for setup and operations.
