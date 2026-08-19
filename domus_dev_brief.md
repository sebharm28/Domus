# Domus — Development Brief for Cursor

## 1. Project Overview
Domus (Latin for "house") is a Telegram-based household assistant coordinating two apartments (the user's and their partner's). It handles shared to-dos, meal planning, reminders, and expense splitting. The bot responds to the wake name **"Domus"** in a shared Telegram group chat.

## 2. Constraints
| Parameter | Value |
|---|---|
| One-time budget | Up to €150 (hardware etc.) |
| Ongoing budget | €5–10 / month |
| Chat interface | Telegram |
| LLM provider | OpenRouter |
| Backend dev tool | Cursor |
| Wake word | "Domus" |
| Users | 2 (shared Telegram group) |

## 3. Core Features (MVP)
- **Shared to-do / shopping list** — add, check off, list items; synced for both apartments
- **Recurring reminders** — trash day, rent transfer, watering plants, smoke detector checks
- **Meal planning** — suggest a weekly plan, recipe ideas based on preferences, auto-generate shopping list from a recipe
- **Status queries** — "What's on today?", "What's missing for dinner?"

## 4. Phase 2 Features
- **Expense splitting** — who paid what, automatic balance calculation between the two apartments
- **Schedule coordination** — who's staying where and when, visit planning
- **Maintenance log** — repair appointments, consumables (filters, batteries, cleaning supplies)
- **Proactive nudges** — bot initiates messages (e.g. "Filter hasn't been changed in 3 months")

## 5. Architecture
```
Telegram message → Backend (polling or webhook) → LLM via OpenRouter
  (intent parsing) → DB read/write (SQLite) → Response sent back to Telegram chat
```
Recurring reminders run via a scheduler (cron / APScheduler), independent of the LLM.

## 6. Components
| Component | Technology | Notes |
|---|---|---|
| Chat interface | Telegram Bot API | Free; both users in same group chat |
| Backend | Python (FastAPI) or Node.js — built in Cursor | Full control, easy to extend |
| LLM | OpenRouter (small/cheap model) | Flexible model choice, usage-based billing |
| Database | SQLite | Free, local, sufficient for 2 users |
| Scheduler | Cron / APScheduler | For recurring reminders, no LLM cost |
| Hosting | Raspberry Pi (home) or small VPS | See cost section |

## 7. Telegram Bot Setup
1. Create bot via **@BotFather** on Telegram → `/newbot` → set name and username (must end in "bot", e.g. `domus_haushalt_bot`)
2. BotFather returns an **API token** — used by the backend to authenticate
3. Add the bot to a **Telegram group** containing both users, so it acts as a shared "third member"

### Message flow options
- **Polling** (recommended to start): backend periodically calls `getUpdates` — no public server/domain needed, works from a home network (e.g. Raspberry Pi without static IP)
- **Webhook**: Telegram pushes messages to a public HTTPS URL — more efficient but requires a domain + TLS certificate

### Recommended libraries
- Python: `python-telegram-bot`
- Node.js: `node-telegram-bot-api`

Both wrap the raw Telegram API (e.g. `bot.on('message', ...)`, `sendMessage()`).

### Example message flow
1. User writes: "Domus, add milk to the list"
2. Backend receives it via polling
3. Text sent to OpenRouter → LLM parses intent: `add_todo`, item: "milk"
4. Backend writes to SQLite
5. Backend calls Telegram's `sendMessage` → replies "✅ Milk added"

## 8. Data Model (simplified)
- **todos**: `id, text, created_by, done (bool), due_date`
- **meals**: `id, day, dish, ingredients (JSON)`
- **expenses**: `id, amount, paid_by, category, date`
- **reminders**: `id, text, recurrence (rrule), next_due`

## 9. Recommended Build Order
1. Create Telegram bot via BotFather (free, ~5 min)
2. Set up backend skeleton in Cursor — polling loop receiving messages
3. Connect OpenRouter API — simple prompt-based intent routing
4. Set up SQLite with the four core tables
5. Build the first core feature (to-do list) end-to-end and test it
6. Expand incrementally: reminders → meal planning → expense splitting

## 10. Cost Breakdown

### One-time
| Item | Cost | Note |
|---|---|---|
| Raspberry Pi 4/5 + PSU + SD card | ~€70–90 | Runs at home 24/7, no ongoing hosting cost |
| Case / accessories | ~€10–15 | Optional |
| Domain (optional) | ~€10/yr | Only needed if webhook must be publicly reachable |
| Buffer | ~€30–40 | Spare parts, testing, contingency |
| **Total** | **~€110–150** | Fits within budget |

Alternative: a small VPS (e.g. Hetzner CX22) instead of a Raspberry Pi avoids the upfront cost but adds ~€4–5/month.

### Ongoing (per month)
| Item | Cost | Note |
|---|---|---|
| Telegram Bot API | €0 | Free |
| OpenRouter (LLM usage) | ~€2–6 | With a small/cheap model and moderate usage (several requests/day) |
| Hosting (if VPS instead of Pi) | €0 (Pi) / ~€4–5 (VPS) | Pi at home: negligible electricity cost only |
| Domain (optional) | ~€1 | Only if needed |
| **Total** | **~€2–8** | Comfortably within the €5–10 target |

### Cost levers to watch
- Model choice on OpenRouter — small/cheap models are sufficient for intent recognition and simple text generation
- Keep context length short — don't resend full chat history on every request
- Handle recurring reminders via cron, not LLM calls

## 11. Notes & Recommendations
- Start with a single core feature (to-do list) to keep initial complexity low
- Monitor OpenRouter costs in the first weeks and adjust model if needed
- Privacy: keep SQLite local on the Pi; avoid sending unnecessary personal data in LLM prompts
- Set up a simple recurring backup of the SQLite database (cron job is sufficient)
