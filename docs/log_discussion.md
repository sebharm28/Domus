# Domus — Log discussions

Notes from reviewing conversation logs (`logs/session_*.log`).  
Raw logs stay local and are gitignored — only summaries and lessons go here.

---

## 2026-08-23 — `session_2026-08-23_17-58-07.log`

**What happened**
- Add bank errand → wrong category (shopping) and no due date.
- *"I said the task is for tomorrow"* → OpenRouter hallucinated a new task (*"find a loving girl friend"*) from a few-shot prompt example.
- *"I meant going to the bank"* → not understood.

**Fixes shipped (same day)**
- Rules-first routing; correction intents before OpenRouter.
- `update_todo` for corrections; better tomorrow parsing across sentences.
- Removed misleading few-shot example from the OpenRouter prompt.

**Follow-up**
- [x] Remove stale *"find a loving girl friend"* entry from DB (2026-08-24).

---

## 2026-08-24 — `session_2026-08-24_18-32-49.log`

**What went well**
- Duplicate merge: second *"add milk"* → *already on the shopping list*.
- *"add pay rent by friday"* → admin, due Friday.
- Daily briefing and weekly meal plan worked (7 dinners, shopping list updated).

**Issues to fix later**
1. *"please add going to the bank… Have to do it tomorrow"* → **Updated** instead of **Added** — fixed in wave 2 (correction skip on add messages).
2. *"ads milk"* (typo) → OpenRouter path; milk got a due date (shopping items shouldn’t).
3. *"I said the task is for tomorrow"* after meal plan → updated **curry paste** (latest open item), not the bank task — partially fixed in wave 2 via `chat_context`.
4. Briefing still showed stale *"find a loving girl friend"* until DB cleanup.
5. `/private` mode not tested this session.

**Wave 1 verified live:** rules-first, duplicate merge, meal plan, briefing.

---

## 2026-08-25 — `session_2026-08-25_21-07-38.log` (wave 2b live test)

**What went well**
- *"remind me in 5min to text Andreas"* → relative reminder set (21:11 → fire ~21:16). **Wave 2b win.**
- *"remove bank from the list"* → partial match removed *going to the bank*.

**What failed or misfired**
1. *"empty the todo list"* / *"no you should empty the todo list!"* → **Added as new tasks** instead of clearing. We have `clear_shopping_list` but no “clear all todos” / NL synonym for wipe.
2. *"I was at the bank. Remove it from the list"* → failed on pronoun *"it"*. Context brain helps **updates**, not **remove** / **complete** yet.
3. *"what should we cook tomorrow?"* → unknown. Gap between casual meal questions and `suggest_meal` / `plan_week`.
4. *"please make a recommendation for dinner tomorrow"* → treated as a **meal name lookup** in the food DB, not a suggestion request.
5. *"I really like currywurst"* → no path to store preferences or add custom meals; diet filter message was unhelpful (currywurst isn’t in seeded foods).
6. *"where's the reminder?"* → answered with **recurring reminders list** (empty). One-shot reminder likely fired on schedule, but there’s no “show my timers” or ack in the log thread.

**Architecture smells (for Sebastian’s review)**
- Intent routing is a **stack of special cases** (structured → natural → clauses → corrections → OpenRouter) — hard to reason about holistically.
- **Brain** is minimal: one `last_todo_id` per chat, only consumed by `update_todo`.
- **Profiles** exist in SQLite but aren’t connected to “I like X” learning or meal DB expansion.
- **Clear / wipe / empty** vocabulary isn’t unified across shopping vs full todo list.
- **Reminders** split across due-date todos, recurring, and one-shot — user-facing replies don’t reflect that model.

**Suggested next fixes (when ready)**
- [x] `clear_todos` intent + synonyms (“empty the list”, “wipe todos”)
- [x] Extend context to `remove_todo` / `complete_todo` (“remove it”, “bought that”)
- [x] Meal phrasing: “what should we cook tomorrow” → `suggest_meal` or `plan_meal`
- [x] `list_timers` / include one-shot reminders in “where’s my reminder?”
- [x] Log preference statements → profile or custom food (`I like currywurst`)

---

## 2026-08-26 — `session_2026-08-26_17-33-39.log` (wave 4–5 live test)

**What went well**
- Shopping merge, export CSV, clear list, **no due date on** *"add milk to the list tomorrow"*.
- **`empty the todo list`** cleared (no longer mis-added).
- **Undo** add, cancel timer, snooze — all worked.
- **Context brain:** *"remove it"*, *"bought it"*, due tomorrow + rename, doctor remove in one message.
- **Reminders:** recurring, relative timer, *"where's the reminder?"* (pending + recent), snooze, cancel.
- **Meals:** casual suggest phrasing, **currywurst** liked → prioritized in dinner ideas, weekly plan + missing ingredients.
- **Profile:** vegetarian, apartment, likes/dislikes, show profile.
- *"show us our shopping list"* worked.

**What failed or misfired**
1. *"add eggs and bread to the list"* → one line **"2× eggs and bread"** (should split items).
2. *"add buy filter for apartment A"* → **"buy filter"** (household); apartment **A** not stored on todo.
3. *"let's make curry with rice tonight"* → meal lookup failed; DB has **"Curry with rice"** — trailing *"tonight"* breaks match.
4. Relative reminder word order: *"remind me **to** leave my boyfriend **in 2 minutes**"* → rejected; *"remind me **in 2 minutes that** …"* works.
5. *"add doctor appointment friday"* → no **Friday due date**; category maintenance (not admin).
6. Rename reply redundant: *"Updated … — renamed to finish power bi report"* (same text twice).
7. **Stale DB junk** from older sessions still visible early (*"empty the todo list"* as tasks, duplicate pay rent, old milk due dates) — cleared mid-test but worth a one-time cleanup.

**Suggested next fixes**
- [x] Split compound shopping adds (*"eggs and bread"*)
- [x] Strip *"tonight/today"* before `plan_meal` name lookup
- [x] Relative reminder: *"remind me to X in N minutes"* word order
- [x] Parse *"appointment friday"* / trailing weekday on task adds
- [x] Apartment hint on add todos — show `[a]` in add reply
- [x] Cleaner rename confirmation message

---

*Add a new dated section when we review the next log.*
