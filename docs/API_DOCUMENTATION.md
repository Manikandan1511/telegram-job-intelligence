# API quick reference

The local API root is `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service and provider readiness (public) |
| GET | `/api/auth/status` | First-run account setup status (public) |
| POST | `/api/auth/register` | Create the first local account (public) |
| POST | `/api/auth/login` | Sign in (public) |
| GET / POST | `/api/auth/me` / `/api/auth/logout` | Read local identity / sign out |
| GET / PUT | `/api/profile` | View or edit the candidate profile |
| POST / GET | `/api/resume` | Upload a resume / list versions |
| PUT / DELETE | `/api/resume/{id}/activate` or `/api/resume/{id}` | Activate or delete a version |
| GET | `/api/telegram/status` | Check local account authorization |
| POST | `/api/telegram/start` | Request a login code |
| POST | `/api/telegram/verify` | Verify the login code |
| POST | `/api/telegram/password` | Complete two-step verification |
| GET | `/api/telegram/sources` | Load groups and channels visible to the authorized Telegram account (up to 500) |
| GET | `/api/telegram/sources/selected` | List enabled sources for the dashboard |
| PUT | `/api/telegram/sources/{chat_id}` | Enable or disable a source |
| POST | `/api/telegram/sync` | Run a bounded manual sync |
| GET | `/api/jobs/recommended` | List stronger matches |
| GET | `/api/jobs/recent` | List recent jobs |
| GET | `/api/jobs/categories` | Category counts |
| GET / PUT | `/api/preferences` | Read or update role/location preferences |
| GET / PUT | `/api/notifications/settings` | Read or update alert and digest preferences |
| POST | `/api/notifications/test` | Send an explicit test alert |
| GET | `/api/jobs` | Search, filter, and sort jobs |
| GET | `/api/jobs/export` | Download a CSV export |
| GET | `/api/applications` | List tracked applications |
| PUT | `/api/jobs/{id}/application` | Update application status |
| POST | `/api/matches/recalculate` | Recalculate current matches |
| GET | `/api/dashboard` | Dashboard totals |

Private endpoints require `Authorization: Bearer <token>`. The first account is the only account in this edition. All endpoints are intended for loopback use. Do not expose this server to a public network.

`GET /api/jobs` returns jobs linked to enabled Telegram sources by default. Pass `source=<chat_id>` to show only postings linked to one enabled source; disabled or unknown sources return no jobs. Cross-posts are included when any linked source is enabled. It supports `search` (title, company, description, location, source, and detected/matched skills), `category` (`excellent`, `strong`, `moderate`, `internship`), `period` (`1d`, `5d`, `1w`, `15d`, `1m`, `older`), and `sort` (`newest`, `oldest`, `match`). The default order is newest Telegram post first. `older` means more than 30 days old; the duration filters include posts from the selected period through now.
