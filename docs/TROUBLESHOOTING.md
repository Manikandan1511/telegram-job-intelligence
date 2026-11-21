# Troubleshooting

## Telegram login code

Use the phone number in international format. A single request may take a few seconds while Telegram opens the connection. The page shows an in-progress state and disables repeat clicks. If the account is already authorized, use **Load sources** instead of requesting a code. For a rate-limit response, wait the number of seconds shown before retrying. Check Telegram's service chat or SMS for the code.

## Telegram session is locked

Run one Uvicorn process only. The app shares one Telethon client and serializes session operations; restart the backend after updating code. Do not open the `.session` file with another client while the backend is running.

## Resume upload confirmation

After a successful upload, a persistent success message appears in the Resume & Profile page, and the resume is added to the version list. An error appears inline if parsing fails. PDF, DOCX and TXT files up to 8 MB are supported.

## Sync fails

A `401` from `/api/telegram/sync` means the account is not authorized; connect it in Telegram Sources first. Job extraction may fall back to rules if the model endpoint is unavailable. Keep the machine online and select only relevant chats.

## Catch up after Mac sleep or shutdown

The Telegram login session and each source's last-seen message ID are saved on disk. On backend startup, the monitor reconnects with that session and reads forward from the saved IDs in batches until it reaches the newest messages. A dashboard open requests an immediate catch-up, and open dashboard data refreshes every 30 seconds. Brief Telegram/network failures are logged and retried with increasing waits up to five minutes.

For automatic recovery after a Mac reboot, open Docker Desktop **Settings → General** and enable **Start Docker Desktop when you sign in**, then start this stack once from the project folder with `docker compose up -d --build`. The Compose restart policies bring the API, database, and dashboard back when Docker starts. The Mac must be awake and connected to the internet; while it is off or asleep, no local worker can collect messages. After it wakes, the worker catches up from each saved checkpoint. Use `docker compose logs -f backend` to inspect reconnect or source errors.

## Local URLs

The backend API is at `http://127.0.0.1:8000`; the dashboard is at `http://127.0.0.1:5173`. The backend root returns API links. CORS allows Vite on `localhost` and `127.0.0.1`.


## Telegram source list is empty or will not load

Open **Telegram Sources** while the account is connected and choose **Reload sources**. The list comes from groups and channels visible in the signed-in Telegram account (up to 500 dialogs); it does not read arbitrary Telegram sources by username. If loading fails, the page shows the API error and a Retry action. Newly found chats start unchecked. Enable the specific chats you want; Opportunities includes jobs linked to enabled chats and can be narrowed to one enabled source.
