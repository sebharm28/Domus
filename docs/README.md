# Domus — planning & discussion

Plain-text notes and strategy docs for the project. Not required to run the bot or UI.

| File | What it is |
|------|------------|
| [features.txt](./features.txt) | **Feature catalog** — everything implemented + planned (start here) |
| [domus_notes.txt](./domus_notes.txt) | Canonical feature guide, backlog, database schema, household v2 auth |
| [app_todo.txt](./app_todo.txt) | Living checklist (UI, app, tech debt) |
| [apartment_discussion.txt](./apartment_discussion.txt) | Join codes (v1) + household accounts (v2) |
| [mobile_app_discussion.txt](./mobile_app_discussion.txt) | macOS / Android / iOS strategy (Pi server, PWA, Tailscale) |
| [app_discussion.txt](./app_discussion.txt) | Historical Bring! sync discussion (deprecated path) |
| [log_discussion.md](./log_discussion.md) | Session-log review notes and NLP fixes |

Product spec (separate): [domus_dev_brief.md](../domus_dev_brief.md) in the repo root.

## Quick start (UI)

```bash
cp .env.example .env          # add OPENROUTER_API_KEY from openrouter.ai/keys
source .venv/bin/activate     # if using project venv
PYTHONPATH=src python ui/server.py   →  http://127.0.0.1:8765
```

Default seed household (empty DB): **Sebastian** @ **Karl-Marx-Allee 5**, password **`test1234`**.

Natural language: Home tab chat → `POST /api/message` → rules engine + optional OpenRouter.
Check **Household → Settings** for OpenRouter status (`openrouter_configured: true/false`).
