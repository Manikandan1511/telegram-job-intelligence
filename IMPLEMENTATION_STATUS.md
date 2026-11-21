# Implementation status

## Implemented for a single private user
- Local FastAPI, SQLite, React/Vite dashboard, local CORS configuration, OpenAPI docs, Alembic migrations, and optional Docker Compose PostgreSQL/API/frontend setup.
- One local account with salted scrypt password hashes, signed expiring JWTs, and private API protection.
- One persistent profile and versioned resume records in the configured database. Uploaded resume files live under the backend's persistent `storage/resumes/` directory. Profile and resume data survive restarts when the database and storage directories are preserved.
- Telegram user sign-in with code and two-step password, already-authorized detection, transient auth restart retry, flood-wait feedback, source discovery/selection, incremental sync, background monitoring, and one shared serialized Telethon client. The Telethon session survives restarts when its configured session path is on persistent storage.
- Rule-based job extraction plus schema-validated Agentia-Max extraction, extraction confidence, source references, cautious duplicate detection, matching/eligibility evaluation, and suspicious-post review signals.
- Job search/filtering, recommendation ordering, categories, details, CSV export, application tracking, dashboard charts, optional private bot commands/alerts, thresholds, and daily digest.
- Vercel-ready static dashboard configuration with a configurable API base URL and explicit CORS allowlist support for a separately hosted API.
- Local Docker services use restart policies and persistent DB/session/resume folders. Setup, architecture, privacy, model, deployment, and troubleshooting are documented.

## Verification completed locally
- 12 backend tests passed, including API auth/CORS, profile-object matching, eligibility/deadlines, duplicate detection, resume parsing, deterministic extraction fallback, suspicious-post signals and ingestion persistence, and password/JWT behavior.
- Alembic database migrated successfully through `0004_job_review`.
- Frontend TypeScript check and production build passed.

## Deployment and remaining verification
- The Vercel dashboard can be deployed from the `frontend/` root with `VITE_API_BASE_URL` set to an HTTPS persistent API. A project URL, external API URL, durable database/filesystem, and Vercel/GitHub authentication are not available in this checkout, so no remote deployment or push has been performed.
- Vercel Functions cannot host the continuous Telethon monitor or retain its writable filesystem. A separate always-on backend/worker with persistent database, resume storage, and Telegram session storage is required. Remote always-on hosting may have a cost; zero hosting cost requires the user's computer to stay on.
- The live Telegram sign-in/source sync, provider model call, and private bot delivery still require manual tests using the user's accounts. Automated tests do not send login codes or access Telegram.
- Edited/deleted message events, broader hard eligibility analysis, and richer score-factor explanations from the full report remain unfinished.
