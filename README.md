# Domus

Telegram household assistant for a shared group chat. See [domus_dev_brief.md](./domus_dev_brief.md) for the full plan. Planning notes and backlog live in [docs/](./docs/).

## Setup

### 1. Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copy the API token into `.env` as `TELEGRAM_BOT_TOKEN`
3. `/setprivacy` → your bot → **Disable** (needed for the "Domus" wake word in groups)
4. Add the bot to your shared group

### 2. Environment file

```bash
cp .env.example .env
```

Fill in at least `TELEGRAM_BOT_TOKEN` for the bot. For the **web UI**, add `OPENROUTER_API_KEY` from [openrouter.ai/keys](https://openrouter.ai/keys) — enables smarter chat when built-in rules don't match. Without it, basic list and meal commands still work via rules.

### 3. Run the web UI (recommended product surface)

```bash
cd ~/Projects/domus
source .venv/bin/activate
PYTHONPATH=src python ui/server.py    # http://127.0.0.1:8765
```

Open in browser → Home tab for natural-language chat. Check **Household → Settings** for OpenRouter status.

Default household (empty DB): **Sebastian** @ **Karl-Marx-Allee 5**, password **`test1234`**.

### 4. Run the Telegram bot (optional test harness)

```bash
cd ~/Projects/domus
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m domus
```

Run only **one** instance at a time.

## Try it

In your group chat:

- `Domus, add milk to the list`
- `Domus, what's on the list?`
- `Domus, check off milk`
- `Domus, remove milk`

## Project layout

```
src/domus/
  bot.py       # Telegram polling and handlers
  config.py    # settings from .env
  db.py        # SQLite schema and queries
  intents.py   # OpenRouter + fallback intent parsing
  router.py    # message routing
  todos.py     # shopping list logic
data/
  domus.db     # created automatically on first run
logs/
  session_*.log  # one conversation log per bot session (not pushed to GitHub)
```

Next up: recurring reminders, meal planning, status queries.
