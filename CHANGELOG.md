# Changelog

## Unreleased
- Fix Opportunities search races and keep filtered results separate from dashboard recommendations.
- Search titles, companies, descriptions, locations, sources, and detected/matched skills.
- Show Telegram posts newest-first and add age filters for 1 day, 5 days, 1 week, 15 days, 1 month, and older.
- Refresh the active Opportunities search after sync and during background dashboard refreshes.

## 1.0.1
- Reuse one serialized Telethon client to prevent SQLite session lock errors.
- Return a friendly already-connected result and retry one transient authorization restart.
- Show persistent upload and login progress/confirmation states.
- Fix profile-object matching failure during Telegram sync.
- Keep private resume files and version history, with activate/delete actions.
- Add application board and CSV export.
- Add narrower duplicate matching and structured model response validation.
