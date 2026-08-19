# Domus

Telegram household assistant for a shared group chat. See [domus_dev_brief.md](./domus_dev_brief.md) for the full plan.

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

Fill in at least `TELEGRAM_BOT_TOKEN`. Add `OPENROUTER_API_KEY` from [openrouter.ai/keys](https://openrouter.ai/keys) for smarter intent parsing. Without it, basic list commands still work via built-in rules.

**Can't find `.env` in Finder?** Files starting with `.` are hidden on macOS. In Finder, press **Cmd + Shift + .** to show hidden files. Or open it directly:

```bash
open -a TextEdit ~/Projects/domus/.env
```

### 3. Run the bot

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
```

Next up: recurring reminders, meal planning, status queries.
