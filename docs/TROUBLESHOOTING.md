# Troubleshooting

## Telegram login code

Use the phone number in international format. A single request may take a few seconds while Telegram opens the connection. The page shows an in-progress state and disables repeat clicks. If the account is already authorized, use **Load sources** instead of requesting a code. For a rate-limit response, wait the number of seconds shown before retrying. Check Telegram's service chat or SMS for the code.

## Telegram session is locked

Run one Uvicorn process only. The app shares one Telethon client and serializes session operations; restart the backend after updating code. Do not open the `.session` file with another client while the backend is running.

## Resume upload confirmation

After a successful upload, a persistent success message appears in the Resume & Profile page, and the resume is added to the version list. An error appears inline if parsing fails. PDF, DOCX and TXT files up to 8 MB are supported.

## Sync fails

A `401` from `/api/telegram/sync` means the account is not authorized; connect it in Telegram Sources first. Job extraction may fall back to rules if the model endpoint is unavailable. Keep the machine online and select only relevant chats.

## Local URLs

The backend API is at `http://127.0.0.1:8000`; the dashboard is at `http://127.0.0.1:5173`. The backend root returns API links. CORS allows Vite on `localhost` and `127.0.0.1`.
