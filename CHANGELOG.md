# Changelog

## 1.0.1
- Reuse one serialized Telethon client to prevent SQLite session lock errors.
- Return a friendly already-connected result and retry one transient authorization restart.
- Show persistent upload and login progress/confirmation states.
- Fix profile-object matching failure during Telegram sync.
- Keep private resume files and version history, with activate/delete actions.
- Add application board and CSV export.
- Add narrower duplicate matching and structured model response validation.
