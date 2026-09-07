# Domus UI (prototype)

This folder is the **primary product surface** for Domus — a web app (and future
native wrapper) over the shared `domus.core` brain.

## Architecture

```
                    ┌────────────────────────┐
                    │      domus.core         │  ← platform-agnostic brain
                    │  (intents, todos, db,   │
                    │   reminders, meals …)   │
                    └───────────┬────────────┘
                                │
             ┌──────────────────┼───────────────────┐
             │                  │                    │
   domus.telegram_bot      ui/server.py       (future) native apps
     (Telegram adapter)   (HTTP + web client)  SwiftUI / React Native
```

- `src/domus/core.py` — `handle_user_message`, `build_settings`, storage init
- `src/domus/household_auth.py` — household accounts, sessions, export/import
- `ui/server.py` — stdlib HTTP bridge; loads `.env` from repo root via `domus.config`
- `ui/web/` — six-tab PWA-style client (Home, Shopping, Tasks, Kitchen, Bath, Household)

## Run it

From the repository root (with venv activated — see top-level `README.md`):

```bash
cp .env.example .env    # add OPENROUTER_API_KEY for smarter chat
PYTHONPATH=src python ui/server.py           # http://127.0.0.1:8765
PYTHONPATH=src python ui/server.py --port 9000
```

### Natural language (Home tab)

Chat messages go to `POST /api/message` → `handle_user_message` → SQLite.

- **Rules first** — "add milk", "what's on the list?", "what should we cook?" work without LLM
- **OpenRouter fallback** — when rules don't match, if `OPENROUTER_API_KEY` is set in `.env`
- **Check status** — Household → Settings shows "OpenRouter: On/Off" and model name
- **Restart** `ui/server.py` after editing `.env`

Try in the Home composer:

- `add milk and eggs to the list`
- `what's on today?`
- `what should we cook for dinner tonight?`

### Household auth (v2)

- Entity switcher in header (create / join / log in)
- Default seed (empty DB): **Sebastian** @ **Karl-Marx-Allee 5**, password **`test1234`**
- Invite links, OTP, export/import — see `docs/domus_notes.txt`

### Configuration

| Variable | Purpose |
|----------|---------|
| `DOMUS_UI_DB` | SQLite path (default `data/domus_ui.db`) |
| `OPENROUTER_API_KEY` | Smarter NL parsing (optional) |
| `OPENROUTER_MODEL` | Override default Llama 3.2 3B instruct |
| `BRIEFING_HOUR`, `QUIET_HOURS_*` | Scheduler settings (shown read-only in UI) |

All env vars live in the **repo-root** `.env` (loaded automatically).

## HTTP API (selected)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/message` | Natural language → `{ reply, todos, reminders }` |
| GET | `/api/settings` | Includes `openrouter_configured`, `openrouter_model` |
| POST | `/api/auth/join`, `/api/auth/login` | Household v2 |
| GET | `/api/household/export` | JSON backup; `?anonymize=1` optional |

Full list: `docs/features.txt`

## Next steps (not yet built)

- Wrap `ui/web` in **Tauri** for macOS `.app`
- **React Native / Expo** client over the same API
- HTTPS + Tailscale for phone access (see `docs/mobile_app_discussion.txt`)
