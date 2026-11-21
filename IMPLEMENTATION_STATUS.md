# Implementation status

## Implemented for a single private user
- Local FastAPI, SQLite, React/Vite dashboard, local CORS configuration, OpenAPI docs, Alembic migrations, and Docker Compose API/frontend setup that mounts the existing local data folders.
- One local account with salted scrypt password hashes, signed expiring JWTs, and private API protection.
- One persistent profile and versioned resume records in the configured database. Uploaded resume files live under the backend's persistent `storage/resumes/` directory. Profile and resume data survive restarts when the database and storage directories are preserved.
- Telegram user sign-in with code and two-step password, already-authorized detection, transient auth restart retry, flood-wait feedback, source discovery/selection, incremental sync, background monitoring, and one shared serialized Telethon client. The Telethon session survives restarts when its configured session path is on persistent storage.
- Catch-up scans drain each enabled source from its saved message checkpoint in pages, use exponential retry after network errors, can be woken when the dashboard opens/returns to foreground, and report connection/catch-up state. The dashboard refreshes its data every 30 seconds.
- Rule-based job extraction plus schema-validated Agentia-Max extraction, extraction confidence, source references, cautious duplicate detection, matching/eligibility evaluation, and suspicious-post review signals.
- Job search/filtering, recommendation ordering, categories, details, CSV export, application tracking, dashboard charts, optional private bot commands/alerts, thresholds, and daily digest.
- Opportunities search works across role, company, description, location, source, and skills; results default to newest Telegram post and support 1-day, 5-day, 1-week, 15-day, 1-month, and older-than-one-month filters.
- Vercel-ready static dashboard configuration with a configurable API base URL and explicit CORS allowlist support for a separately hosted API.
- Local Docker services reuse the existing profile database, session, and resume folder with restart policies. The local database currently has saved user/profile/resume/source/job data. Docker Desktop must be set to start at Mac sign-in; new messages cannot be collected while the Mac is asleep or powered off.

## Verification completed locally
- 15 backend tests passed, including API auth/CORS, search/skill/date filtering and newest ordering, database-reopen profile persistence, multi-batch Telegram catch-up, profile-object matching, eligibility/deadlines, duplicate detection, resume parsing, deterministic extraction fallback, suspicious-post signals and ingestion persistence, and password/JWT behavior.
- Alembic database migrated successfully through `0004_job_review`.
- Frontend TypeScript check and production build passed.

## Deployment and remaining verification
- Source was pushed to GitHub `main` in commit `9229667`. The Vercel dashboard can be deployed from the `frontend/` root with `VITE_API_BASE_URL` set to an HTTPS API. Vercel reauthentication is required. For the selected zero-hosting-cost option, that API runs on the Mac; a Vercel webpage needs a secure route/VPN or tunnel to reach it, and the Mac must be awake for the API/dashboard data to be available.
- Vercel Functions cannot host the continuous Telethon monitor or retain its writable filesystem. A separate always-on backend/worker with persistent database, resume storage, and Telegram session storage is required. Remote always-on hosting may have a cost; zero hosting cost requires the user's computer to stay on.
- The live Telegram sign-in/source sync, provider model call, and private bot delivery still require manual tests using the user's accounts. Automated tests do not send login codes or access Telegram.
- Sleep/wake and reboot recovery are documented but still need to be exercised on the user's Mac with Docker Desktop configured to launch at sign-in.
- Edited/deleted message events, broader hard eligibility analysis, and richer score-factor explanations from the full report remain unfinished.
