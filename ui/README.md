# Domus UI (prototype)

This folder is a **future-facing scaffold** for moving Domus off Telegram and
onto its own apps (macOS desktop + Android/iOS). It is intentionally small — a
proof of concept for the messaging + shopping-list experience, not a shipping
app yet.

## Architecture

The Telegram bot and this UI are two **frontends** over one shared brain:

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

- `src/domus/core.py` — the stable, frontend-neutral API (`handle_user_message`,
  `list_open_todos`, `set_todo_done`, `build_settings`). No messaging platform
  is imported here.
- `src/domus/telegram_bot/` — the Telegram-specific adapter (polling, handlers,
  schedulers). Nothing else depends on it.
- `ui/server.py` — a dependency-free (stdlib only) HTTP bridge exposing the core
  over JSON. This is the shared backend a desktop or mobile app would call.
- `ui/web/` — a small static web client: a chat pane + a Bring!-style shopping
  list. Web tech keeps it portable (wrap in Tauri/Electron for desktop today,
  and it documents the exact API a native app needs).

## Run it

From the repository root, with dependencies installed (see the top-level
`README.md`):

```bash
PYTHONPATH=src python ui/server.py           # http://127.0.0.1:8765
PYTHONPATH=src python ui/server.py --port 9000
```

Then open the printed URL in a browser. Try:

- `Domus, add milk and eggs to the list`
- `add 2 milk to the list`
- `what's on the list?`
- `remind us every Tuesday to take out the trash`

Tap a shopping tile to check it off (Bring!-style).

### Configuration

- `DOMUS_UI_DB` — SQLite path (defaults to `data/domus_ui.db`, separate from the
  bot's DB so you can experiment freely). Point it at the bot's DB to share one
  household.
- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` — optional, for smarter intent
  parsing. Without them the built-in rules engine still handles list/reminder
  commands.

## HTTP API

| Method | Path                | Body                     | Returns                       |
| ------ | ------------------- | ------------------------ | ----------------------------- |
| GET    | `/api/todos`        | –                        | `{ "todos": [...] }`          |
| POST   | `/api/message`      | `{ "text", "user" }`     | `{ "reply", "todos": [...] }` |
| POST   | `/api/todos/toggle` | `{ "id", "done" }`       | `{ "todos": [...] }`          |

A native SwiftUI or React Native app would talk to these same endpoints — the
web client here is just the first consumer.

## Next steps (not yet built)

- Wrap `ui/web` in **Tauri** (Rust) or **Electron** for a real macOS `.app`.
- A **React Native / Expo** or **Flutter** client for Android/iOS over the same
  API.
- Auth + multi-household support (today the prototype uses a single local
  household).
