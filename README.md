# Job Intelligence

A local-first Telegram job discovery and application tracker. The backend uses FastAPI, Telethon and SQLite; the dashboard uses React and Vite. It runs on your computer without hosting fees. Keeping it free means the computer must remain on for continuous monitoring. Agentia-Max is configured as an optional OpenAI-compatible extraction provider.

## Requirements

- Python 3.11 or newer (Python 3.14 should work, but package compatibility varies)
- Node.js 20 or newer
- A Telegram account and Telegram API credentials

## Setup

The provided Telegram API ID and hash are already set in the ignored `.env` file in this folder. Never commit that file. Start the backend from this project root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. API docs are at http://127.0.0.1:8000/docs. Data is stored in `backend/data/job_intelligence.db`; the Telegram session is kept in `storage/telegram.session`; private resume files are versioned under `storage/resumes/`, with extracted profile text stored in SQLite. These paths are excluded from Git.

On first open, create the single local account with an email and a password of at least 12 characters. The password is stored as a salted scrypt hash; API access uses a signed 12-hour token. Alembic applies schema migrations on startup. The token-signing key is generated in ignored `backend/data/jwt.secret`. This local edition intentionally allows one account and binds the server to loopback.


## Optional Docker Compose deployment

Docker Compose starts the API and production-built dashboard, reusing your existing SQLite database, Telegram session, and resume files. It binds only to loopback and costs nothing to run locally:

```sh
docker compose up --build
```

Open http://127.0.0.1:8080. Your saved database remains in `backend/data/`; the Telegram session and private resumes remain under `storage/`.

For restart recovery, configure Docker Desktop to start when you sign in and launch the stack once with `docker compose up -d --build`. The saved Telegram session reconnects automatically. After sleep or shutdown, the monitor catches up from its last saved message IDs; the dashboard asks for an immediate catch-up when it opens/returns to the foreground and refreshes displayed jobs every 30 seconds. Collection pauses while the Mac is asleep or powered off.

## Telegram connection

In **Telegram Sources**, request a login code using your phone number in international format, then submit the code. The service keeps one Telethon connection active to avoid session file contention. If the account is already connected, the page reports that instead of requesting another code. Telegram may also require a two-step verification password; the UI submits it only to the local backend and does not store it. Load the available chats and enable the job groups or channels you want. Use **Sync now** to scan recent history. Telegram account access remains local to this machine.

## Agentia-Max model

The configured base URL is `https://45674.vr2.in/v1` and the model is `agentia-max`. The local ignored `.env` uses the API key value you supplied (`not-required`); the backend sends a Bearer header when this setting is nonempty. Calls use OpenAI-compatible Chat Completions for job extraction. If the endpoint is unavailable or unconfigured, deterministic extraction and matching continue. Resume contents are not sent to the model.

## Zero-cost limits and privacy

- This is local software; no cloud hosting or paid database is required.
- Model inference may incur charges depending on the Agentia-Max plan. An endpoint URL alone does not guarantee free inference. Leave AI credentials blank to use local deterministic processing.
- Telegram's API may impose account and rate limits. Sync incrementally and only enable chats the signed-in account can access.
- `.env` and Telegram session files are ignored by Git. The app uses one local account and keeps its API bound to loopback.
- Vercel can host the static dashboard, but continuous Telegram monitoring requires a separate always-on API/worker with persistent database, resume, and session storage. See [deployment guide](docs/DEPLOYMENT.md).

## Current behavior

- Reads permitted Telegram dialogs, supports manual sync, and polls enabled sources while the backend is running.
- Extracts jobs using rules, optionally enhanced by an OpenAI-compatible model endpoint.
- Scores opportunities against the resume skills and role preferences; tracks application statuses.
- Flags suspicious job text for review, including requests for upfront payment, sensitive credentials, guaranteed placement claims, and shortened links. These rules are advisory and can produce false positives.
- Parses PDF, DOCX and TXT resumes locally; keeps versioned private resume files and profile text.
- Provides dashboard, job search, application board, CSV export, Telegram source selection, resume/profile and preferences pages.

The optional private Telegram bot supports `/start`, `/help`, `/jobs`, `/topjobs`, `/today`, `/internships`, `/fulltime`, `/applications`, `/settings`, and `/status`. Set a BotFather token in `BOT_TOKEN`, start the backend, and send `/start` to the bot privately. The first private chat is claimed locally; `BOT_CHAT_ID` can be set to pin a specific chat instead. Notification threshold and daily digest are configurable in Preferences.
