# Local deployment

This project is designed to run on the user's Mac to avoid hosting and database charges. From the project root, activate the existing environment and run the API:

```sh
source venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Alembic upgrades the schema at API startup. Keep the backend process running for background Telegram polling. SQLite data is in `backend/data/`; private resumes and the Telethon session are under `storage/`. Back up those paths while the app is stopped. Restore by copying them back into this project folder. Keep `.env` private and excluded from Git.

Docker Compose is available in the project root for an optional local PostgreSQL + API + dashboard run. Public network deployment still needs security review. Hosting a user-account Telethon session on a public or ephemeral server is not recommended.

## Vercel dashboard with persistent Telegram service

Vercel can host the static dashboard from the `frontend/` project root. Set `VITE_API_BASE_URL` to the HTTPS base of the API, including `/api`; copy `frontend/.env.example` as the template. Configure the API's `CORS_ORIGINS` to the exact Vercel production origin (for example `https://your-app.vercel.app`). Do not put Telegram API credentials, the Agentia key, the JWT signing key, resume data, or a Telethon session in the frontend/Vercel build.

The API, database, resume files, and Telegram worker must run on a persistent service with durable storage. Mount persistent storage for `backend/data/` and `storage/`, keep one API worker process, and configure `DATABASE_URL`, `TELEGRAM_SESSION`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, and a stable `JWT_SECRET` on that service. For local testing, Docker Compose preserves those folders and restarts services unless stopped. It cannot run 24/7 while the computer is off.

Vercel Functions are request-scoped and bounded in duration; their writable filesystem is temporary. They cannot host this app's continuous Telethon monitor or retain its SQLite session/resume files. The supported split is therefore Vercel for the static dashboard plus a separate persistent API/worker/database host. A guaranteed always-on remote worker may have a hosting cost; the project's no-hosting-cost mode is to keep the local machine running.

After both services are configured, test in this order: API `/api/health`, dashboard first-run/sign-in, saved profile and resume after an API restart, Telegram session status, a manual source sync, and then a newly posted job appearing after the polling interval. Telegram login codes and live source access must be tested with the owner's account.
