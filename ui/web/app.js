// ---- element refs ---------------------------------------------------------
const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("input");
const shoppingEl = document.getElementById("shopping");
const tasksEl = document.getElementById("tasks");
const recipesEl = document.getElementById("recipes");
const summaryEl = document.getElementById("summary");
const connectionEl = document.getElementById("connection");
const pageTitle = document.getElementById("page-title");
const themeToggle = document.getElementById("theme-toggle");
const themeIcon = themeToggle.querySelector(".theme-icon");
const tabbar = document.getElementById("tabbar");
const kitchenBack = document.getElementById("kitchen-back");
const addShoppingForm = document.getElementById("add-shopping");
const shoppingInput = document.getElementById("shopping-input");
const addTaskForm = document.getElementById("add-task");
const taskInput = document.getElementById("task-input");
const taskCategory = document.getElementById("task-category");
const tagFilterEl = document.getElementById("tag-filter");
const newRecipeBtn = document.getElementById("new-recipe-btn");
const modalOverlay = document.getElementById("modal-overlay");
const modalEl = document.getElementById("modal");
const profilesEl = document.getElementById("profiles");
const statsEl = document.getElementById("stats");
const settingsEl = document.getElementById("settings");
const remindersEl = document.getElementById("reminders");

const USER_ID = 1;
const DISPLAY_NAME = localStorage.getItem("domus-display-name") || "You";

const state = {
  todos: [],
  recipes: [],
  tags: [],
  profiles: [],
  settings: null,
  stats: [],
  reminders: { recurring: [], pending_timers: [], recent_timers: [] },
  chatLoaded: false,
  activeTag: null,
  recipesLoaded: false,
  householdLoaded: false,
};

const EMOJI = {
  milk: "🥛", eggs: "🥚", butter: "🧈", bread: "🍞", cheese: "🧀",
  rice: "🍚", pasta: "🍝", coffee: "☕", tea: "🍵", water: "💧",
  apple: "🍎", apples: "🍎", banana: "🍌", bananas: "🍌", tomato: "🍅",
  tomatoes: "🍅", onion: "🧅", onions: "🧅", garlic: "🧄", potato: "🥔",
  potatoes: "🥔", carrot: "🥕", carrots: "🥕", chicken: "🍗", fish: "🐟",
  salmon: "🐟", beef: "🥩", curry: "🍛", chocolate: "🍫", sugar: "🧂",
  salt: "🧂", flour: "🌾", oil: "🫒", wine: "🍷", beer: "🍺",
  yogurt: "🥣", lemon: "🍋", lemons: "🍋", orange: "🍊", oranges: "🍊",
  vegetables: "🥦", pepper: "🫑", cucumber: "🥒", avocado: "🥑",
};

function emojiFor(name) {
  const key = (name || "").trim().toLowerCase();
  if (EMOJI[key]) return EMOJI[key];
  for (const word of key.split(/\s+/)) {
    if (EMOJI[word]) return EMOJI[word];
  }
  return "🛒";
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ---- dark mode ------------------------------------------------------------
function currentTheme() {
  const saved = localStorage.getItem("domus-theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
  themeToggle.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
}

applyTheme(currentTheme());

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  localStorage.setItem("domus-theme", next);
  applyTheme(next);
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
  if (!localStorage.getItem("domus-theme")) applyTheme(e.matches ? "dark" : "light");
});

// ---- tab navigation -------------------------------------------------------
const TAB_PARENT = {
  recipes: "kitchen",
  "kitchen-timer": "kitchen",
  "bath-timer": "bath",
  "bath-brush": "bath",
};

const RING_RADIUS = 88;
const RING_CIRC = 2 * Math.PI * RING_RADIUS;

function tabForView(name) {
  return TAB_PARENT[name] || name;
}

function formatTimerTime(totalSeconds) {
  const secs = Math.max(0, Math.ceil(totalSeconds));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function playTimerDone() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.35, 0.7].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = delay === 0.7 ? 880 : 660;
      gain.gain.value = 0.08;
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.22);
    });
  } catch (_) {
    /* audio optional */
  }
  if (navigator.vibrate) navigator.vibrate([180, 80, 180]);
}

function initCountdownTimer(root) {
  const progress = root.querySelector(".timer-progress");
  const timeEl = root.querySelector(".timer-time");
  const labelEl = root.querySelector(".timer-label");
  const startBtn = root.querySelector(".timer-start");
  const pauseBtn = root.querySelector(".timer-pause");
  const resetBtn = root.querySelector(".timer-reset");
  const presetBtns = root.querySelectorAll(".timer-preset");
  const doneLabel = root.dataset.doneLabel || "Time is up!";

  progress.style.strokeDasharray = String(RING_CIRC);
  progress.style.strokeDashoffset = "0";

  let totalSeconds = 0;
  let remainingSeconds = 0;
  let endAt = null;
  let pausedRemaining = 0;
  let running = false;
  let label = "Pick a preset";
  let tickId = null;
  let done = false;

  function syncRing() {
    const ratio = totalSeconds > 0 ? remainingSeconds / totalSeconds : 0;
    progress.style.strokeDashoffset = String(RING_CIRC * (1 - ratio));
    timeEl.textContent = formatTimerTime(remainingSeconds);
    labelEl.textContent = done ? doneLabel : label;
    root.classList.toggle("is-running", running);
    root.classList.toggle("is-done", done);
  }

  function setIdle() {
    running = false;
    done = false;
    endAt = null;
    pausedRemaining = 0;
    if (tickId) {
      clearInterval(tickId);
      tickId = null;
    }
    startBtn.textContent = "Start";
    pauseBtn.disabled = true;
    resetBtn.disabled = totalSeconds === 0;
    syncRing();
  }

  function finish() {
    running = false;
    done = true;
    remainingSeconds = 0;
    endAt = null;
    if (tickId) {
      clearInterval(tickId);
      tickId = null;
    }
    startBtn.textContent = "Start";
    pauseBtn.disabled = true;
    resetBtn.disabled = false;
    syncRing();
    playTimerDone();
    toast(doneLabel);
  }

  function tick() {
    if (!running || endAt === null) return;
    remainingSeconds = Math.max(0, (endAt - Date.now()) / 1000);
    if (remainingSeconds <= 0) {
      finish();
      return;
    }
    syncRing();
  }

  function selectPreset(btn) {
    presetBtns.forEach((b) => b.classList.toggle("is-active", b === btn));
    totalSeconds = Number(btn.dataset.secs);
    remainingSeconds = totalSeconds;
    label = btn.dataset.label || "Timer";
    done = false;
    running = false;
    endAt = null;
    pausedRemaining = 0;
    if (tickId) {
      clearInterval(tickId);
      tickId = null;
    }
    startBtn.textContent = "Start";
    pauseBtn.disabled = true;
    resetBtn.disabled = false;
    syncRing();
  }

  presetBtns.forEach((btn) => {
    btn.addEventListener("click", () => selectPreset(btn));
  });

  const activePreset = root.querySelector(".timer-preset.is-active");
  if (activePreset) selectPreset(activePreset);

  startBtn.addEventListener("click", () => {
    if (done) {
      done = false;
      remainingSeconds = totalSeconds;
    }
    if (totalSeconds <= 0) {
      toast("Pick a preset first.");
      return;
    }
    if (running) return;
    running = true;
    endAt = Date.now() + (pausedRemaining || remainingSeconds) * 1000;
    pausedRemaining = 0;
    startBtn.textContent = "Running…";
    pauseBtn.disabled = false;
    resetBtn.disabled = false;
    if (!tickId) tickId = setInterval(tick, 200);
    tick();
  });

  pauseBtn.addEventListener("click", () => {
    if (!running) return;
    running = false;
    pausedRemaining = Math.max(0, (endAt - Date.now()) / 1000);
    remainingSeconds = pausedRemaining;
    endAt = null;
    startBtn.textContent = "Resume";
    pauseBtn.disabled = true;
    syncRing();
  });

  resetBtn.addEventListener("click", () => {
    remainingSeconds = totalSeconds;
    setIdle();
  });

  return { reset: setIdle };
}

const countdownTimers = new Map();

function switchView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("is-active"));
  const view = document.getElementById(`view-${name}`);
  if (view) {
    view.classList.add("is-active");
    pageTitle.textContent = view.dataset.title || "Domus";
  }
  const tabName = tabForView(name);
  tabbar.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("is-active", t.dataset.view === tabName)
  );
  if (name === "recipes" && !state.recipesLoaded) loadRecipes();
  if (name === "household" && !state.householdLoaded) loadHousehold();
}

document.querySelectorAll(".kitchen-app[data-go]").forEach((tile) => {
  tile.addEventListener("click", () => switchView(tile.dataset.go));
});

document.querySelectorAll(".hub-back").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.back));
});

if (kitchenBack) {
  kitchenBack.addEventListener("click", () => switchView("kitchen"));
}

document.querySelectorAll(".timer-app").forEach((root) => {
  countdownTimers.set(root.id, initCountdownTimer(root));
});

tabbar.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => switchView(tab.dataset.view));
});

// ---- API ------------------------------------------------------------------
async function api(path, body) {
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const res = await fetch(path, opts);
  return res.json();
}

async function loadHousehold() {
  try {
    const [profiles, settings, stats, reminders] = await Promise.all([
      api("/api/profiles"),
      api("/api/settings"),
      api("/api/stats"),
      api("/api/reminders"),
    ]);
    state.profiles = profiles.profiles || [];
    state.settings = settings;
    state.stats = stats.stats || [];
    applyReminders(reminders);
    state.householdLoaded = true;
    renderHousehold();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function loadChatHistory() {
  try {
    const data = await api("/api/chat/history");
    const turns = data.history || [];
    messagesEl.innerHTML = "";
    if (turns.length === 0) {
      addBubble(
        "Hi! I'm Domus. Ask me to add items, plan meals, or set reminders — or use the tabs below.",
        "Domus"
      );
    } else {
      for (const turn of turns) {
        const who =
          turn.role === "user" ? turn.display_name || DISPLAY_NAME : "Domus";
        addBubble(turn.text, who);
      }
    }
    state.chatLoaded = true;
    setConnected(true);
  } catch (e) {
    if (!state.chatLoaded) {
      addBubble(
        "Hi! I'm Domus. Ask me to add items, plan meals, or set reminders — or use the tabs below.",
        "Domus"
      );
    }
    setConnected(false);
  }
}

async function loadTodos() {
  try {
    const data = await api("/api/todos");
    state.todos = data.todos || [];
    renderTodos();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function loadRecipes() {
  try {
    const data = await api("/api/recipes");
    state.recipes = data.recipes || [];
    state.tags = data.tags || [];
    state.recipesLoaded = true;
    renderTagFilter();
    renderRecipes();
    renderSummary();
  } catch (e) {
    setConnected(false);
  }
}

// ---- rendering ------------------------------------------------------------
function renderTodos() {
  const shopping = state.todos.filter((t) => t.category === "shopping");
  const others = state.todos.filter((t) => t.category !== "shopping");
  renderShopping(shopping);
  renderTasks(others);
  renderSummary();
}

function renderSummary() {
  const shopping = state.todos.filter((t) => t.category === "shopping").length;
  const tasks = state.todos.filter((t) => t.category !== "shopping").length;
  const recipes = state.recipes.length || "…";
  summaryEl.innerHTML = `
    <div class="stat"><div class="num">${shopping}</div><div class="lbl">To buy</div></div>
    <div class="stat"><div class="num">${tasks}</div><div class="lbl">Open tasks</div></div>
    <div class="stat"><div class="num">${recipes}</div><div class="lbl">Recipes</div></div>
  `;
}

function renderShopping(items) {
  shoppingEl.innerHTML = "";
  if (items.length === 0) {
    shoppingEl.innerHTML = `<p class="empty">Nothing to buy yet — add an item above or ask Domus.</p>`;
    return;
  }
  for (const item of items) {
    const tile = document.createElement("div");
    tile.className = "tile";
    tile.title = "Tap to check off";
    tile.innerHTML = `
      <button class="del" title="Remove" aria-label="Remove">×</button>
      <span class="emoji">${emojiFor(item.name)}</span>
      <span class="name">${escapeHtml(item.name)}</span>
      ${item.quantity && item.quantity > 1 ? `<span class="qty">${item.quantity}</span>` : ""}
    `;
    tile.querySelector(".del").addEventListener("click", (e) => {
      e.stopPropagation();
      removeItem(tile, item.id);
    });
    tile.addEventListener("click", () => checkOff(tile, item.id));
    shoppingEl.appendChild(tile);
  }
}

function renderTasks(items) {
  tasksEl.innerHTML = "";
  if (items.length === 0) {
    tasksEl.innerHTML = `<p class="empty">No open tasks — add one above.</p>`;
    return;
  }
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "row";
    const due = item.due_date ? `due ${item.due_date}` : "";
    const assignee = item.assigned_to ? `→ ${item.assigned_to}` : "";
    const apt = item.apartment ? `[${item.apartment}]` : "";
    const meta = [apt, assignee, due].filter(Boolean).join(" · ");
    row.innerHTML = `
      <span class="check" title="Mark done"></span>
      <span class="label">${escapeHtml(item.name)}</span>
      <span class="badge">${escapeHtml(item.category)}</span>
      <span class="meta">${escapeHtml(meta)}</span>
      <button class="del" title="Remove" aria-label="Remove">×</button>
    `;
    row.querySelector(".check").addEventListener("click", () => checkOff(row, item.id));
    row.querySelector(".del").addEventListener("click", () => removeItem(row, item.id));
    tasksEl.appendChild(row);
  }
}

function renderHousehold() {
  if (!profilesEl) return;

  if (state.profiles.length === 0) {
    profilesEl.innerHTML = `<p class="empty">No profiles yet — chat with Domus to create one.</p>`;
  } else {
    profilesEl.innerHTML = state.profiles.map((p) => `
      <article class="profile-card">
        <h3>${escapeHtml(p.display_name)}</h3>
        ${p.apartment ? `<p><strong>Apartment:</strong> ${escapeHtml(p.apartment)}</p>` : ""}
        ${p.diet ? `<p><strong>Diet:</strong> ${escapeHtml(p.diet)}</p>` : ""}
        ${p.likes ? `<p><strong>Likes:</strong> ${escapeHtml(p.likes)}</p>` : ""}
        ${p.dislikes ? `<p><strong>Dislikes:</strong> ${escapeHtml(p.dislikes)}</p>` : ""}
        ${p.allergies ? `<p><strong>Allergies:</strong> ${escapeHtml(p.allergies)}</p>` : ""}
      </article>
    `).join("");
  }

  if (state.stats.length === 0) {
    statsEl.innerHTML = `<p class="empty">No completed tasks in the last 7 days.</p>`;
  } else {
    statsEl.innerHTML = state.stats.map((s) => `
      <div class="stat-row">
        <strong>${escapeHtml(s.display_name)}</strong>
        <span>${s.count} completed</span>
        ${s.samples?.length ? `<span class="muted">${escapeHtml(s.samples.slice(0, 2).join(", "))}</span>` : ""}
      </div>
    `).join("");
  }

  const cfg = state.settings || {};
  settingsEl.innerHTML = `
    <p><strong>Morning briefing:</strong> ${cfg.briefing_hour ?? 8}:00</p>
    <p><strong>Evening summary:</strong> ${cfg.evening_briefing_hour ?? 20}:00</p>
    <p><strong>Quiet hours:</strong> ${cfg.quiet_hours_enabled ? `${cfg.quiet_hours_start}:00–${cfg.quiet_hours_end}:00` : "off"}</p>
    <p><strong>Redaction:</strong> ${cfg.redaction_enabled ? "on" : "off"}</p>
    <p class="muted section-hint">Configure via .env — QUIET_HOURS_*, REDACTION_*</p>
  `;

  renderReminders();
}

function applyReminders(data) {
  if (!data) return;
  state.reminders = {
    recurring: data.recurring || [],
    pending_timers: data.pending_timers || [],
    recent_timers: data.recent_timers || [],
  };
}

function renderReminders() {
  if (!remindersEl) return;
  const { recurring, pending_timers, recent_timers } = state.reminders;
  const sections = [];

  if (recurring?.length) {
    sections.push(`
      <h3 class="reminder-heading">Recurring</h3>
      ${recurring
        .map(
          (r) => `
        <div class="reminder-row${r.is_overdue ? " overdue" : ""}">
          <div>
            <strong>${escapeHtml(r.text)}</strong>
            <span class="muted">${escapeHtml(r.schedule_label)} · next ${escapeHtml(r.next_due_label)}</span>
          </div>
          <button class="del" data-action="remove-recurring" data-id="${r.id}" title="Remove">×</button>
        </div>`
        )
        .join("")}
    `);
  }

  if (pending_timers?.length) {
    sections.push(`
      <h3 class="reminder-heading">Pending timers</h3>
      ${pending_timers
        .map(
          (t) => `
        <div class="reminder-row">
          <div>
            <strong>${escapeHtml(t.text)}</strong>
            <span class="muted">${escapeHtml(t.fire_at_local)}${t.minutes_until != null ? ` · in ${t.minutes_until} min` : ""}</span>
          </div>
          <button class="del" data-action="cancel-timer" data-id="${t.id}" title="Cancel">×</button>
        </div>`
        )
        .join("")}
    `);
  }

  if (recent_timers?.length) {
    sections.push(`
      <h3 class="reminder-heading">Recent timers</h3>
      ${recent_timers
        .map(
          (t) => `
        <div class="reminder-row muted">
          <div>
            <strong>${escapeHtml(t.text)}</strong>
            <span class="muted">${escapeHtml(t.fire_at_local)}</span>
          </div>
        </div>`
        )
        .join("")}
    `);
  }

  remindersEl.innerHTML =
    sections.length > 0
      ? sections.join("")
      : `<p class="empty">No reminders yet — try “remind us every Tuesday to take out the trash”.</p>`;

  remindersEl.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      if (btn.dataset.action === "remove-recurring") removeRecurringReminder(id);
      if (btn.dataset.action === "cancel-timer") cancelTimer(id);
    });
  });
}

async function removeRecurringReminder(id) {
  try {
    const data = await api("/api/reminders/remove", { id });
    applyReminders(data);
    renderReminders();
    if (data.removed) toast(`Removed: ${data.removed}`);
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function cancelTimer(id) {
  try {
    const data = await api("/api/reminders/cancel-timer", { id });
    applyReminders(data);
    renderReminders();
    if (data.cancelled) toast(`Cancelled: ${data.cancelled}`);
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

function renderTagFilter() {
  tagFilterEl.innerHTML = "";
  const chips = ["All", ...state.tags];
  for (const tag of chips) {
    const chip = document.createElement("button");
    chip.className = "tag-chip";
    const isAll = tag === "All";
    if ((isAll && !state.activeTag) || state.activeTag === tag) {
      chip.classList.add("is-active");
    }
    chip.textContent = tag;
    chip.addEventListener("click", () => {
      state.activeTag = isAll ? null : tag;
      renderTagFilter();
      renderRecipes();
    });
    tagFilterEl.appendChild(chip);
  }
}

function renderRecipes() {
  recipesEl.innerHTML = "";
  const order = { breakfast: 0, lunch: 1, dinner: 2, snack: 3 };
  let list = [...state.recipes];
  if (state.activeTag) {
    const t = state.activeTag.toLowerCase();
    list = list.filter((r) => (r.tags || []).some((x) => x.toLowerCase() === t));
  }
  list.sort(
    (a, b) => (order[a.meal_type] ?? 9) - (order[b.meal_type] ?? 9) || a.name.localeCompare(b.name)
  );
  if (list.length === 0) {
    recipesEl.innerHTML = `<p class="empty">No recipes${state.activeTag ? ` tagged “${escapeHtml(state.activeTag)}”` : ""} yet.</p>`;
    return;
  }
  for (const r of list) {
    const card = document.createElement("div");
    card.className = "card";
    const prep = r.prep_time_min ? `~${r.prep_time_min} min` : "";
    // Cards keep it simple: tag, name, prep, ingredient NAMES (no amounts).
    const chips = (r.ingredients || [])
      .map((i) => `<span class="chip">${escapeHtml(i)}</span>`)
      .join("");
    card.innerHTML = `
      <span class="type">${escapeHtml(r.meal_type)}</span>
      <div class="card-top">
        <h3>${escapeHtml(r.name)}</h3>
        <span class="prep">${escapeHtml(prep)}</span>
      </div>
      <div class="chips">${chips}</div>
      <button class="plan">Add missing to list</button>
    `;
    const planBtn = card.querySelector(".plan");
    planBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      planRecipe(r.name);
    });
    card.addEventListener("click", () => openRecipeDetail(r.id));
    recipesEl.appendChild(card);
  }
}

// ---- minimal, safe markdown renderer (escape first, then format) ----------
function mdToHtml(src) {
  if (!src || !src.trim()) return '<p class="muted">No notes yet.</p>';
  const esc = escapeHtml(src);
  const lines = esc.split(/\r?\n/);
  let html = "";
  let inList = null; // 'ul' | 'ol' | null
  const closeList = () => {
    if (inList) {
      html += `</${inList}>`;
      inList = null;
    }
  };
  const inline = (s) =>
    s
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  for (const raw of lines) {
    const line = raw.trimEnd();
    let m;
    if ((m = line.match(/^(#{1,3})\s+(.*)$/))) {
      closeList();
      const level = m[1].length;
      html += `<h${level}>${inline(m[2])}</h${level}>`;
    } else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (inList !== "ul") {
        closeList();
        html += "<ul>";
        inList = "ul";
      }
      html += `<li>${inline(m[1])}</li>`;
    } else if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) {
      if (inList !== "ol") {
        closeList();
        html += "<ol>";
        inList = "ol";
      }
      html += `<li>${inline(m[1])}</li>`;
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  return html;
}

// ---- recipe detail modal --------------------------------------------------
function openRecipeDetail(id) {
  const r = state.recipes.find((x) => x.id === id);
  if (!r) return;
  const prep = r.prep_time_min ? `~${r.prep_time_min} min` : "";
  const tagChips = (r.tags || [])
    .map((t) => `<span class="chip tag-pill">${escapeHtml(t)}</span>`)
    .join("");
  const details = (r.ingredient_details && r.ingredient_details.length
    ? r.ingredient_details
    : (r.ingredients || []).map((n) => ({ name: n, amount: "" }))
  )
    .map((d) => {
      const amt = d.amount
        ? `<span class="amt">${escapeHtml(d.amount)}</span>`
        : `<span class="amt none">—</span>`;
      return `<li><span>${escapeHtml(d.name)}</span>${amt}</li>`;
    })
    .join("");

  modalEl.innerHTML = `
    <div class="modal-head">
      <h2>${escapeHtml(r.name)}</h2>
      <button class="close" aria-label="Close">×</button>
    </div>
    <div class="meta-row">
      <span class="type">${escapeHtml(r.meal_type)}</span>
      ${prep ? `<span>${escapeHtml(prep)}</span>` : ""}
      ${r.author ? `<span>· by ${escapeHtml(r.author)}</span>` : ""}
    </div>
    ${tagChips ? `<h4>Tags</h4><div class="chips">${tagChips}</div>` : ""}
    <h4>Ingredients</h4>
    <ul class="ing-list">${details}</ul>
    <h4>Notes</h4>
    <div class="md" id="note-view">${mdToHtml(r.notes)}</div>
    <div class="modal-actions spread">
      <button class="btn danger" id="delete-recipe">Delete</button>
      <div class="modal-actions-right">
        <button class="btn link" id="edit-recipe">Edit recipe</button>
        <button class="btn primary" id="plan-recipe">Add missing to list</button>
      </div>
    </div>
  `;
  modalEl.querySelector(".close").addEventListener("click", closeModal);
  modalEl.querySelector("#edit-recipe").addEventListener("click", () => openRecipeForm(r));
  modalEl.querySelector("#delete-recipe").addEventListener("click", () => deleteRecipe(r));
  modalEl.querySelector("#plan-recipe").addEventListener("click", () => planRecipe(r.name));
  openModal();
}

// ---- recipe create / edit form --------------------------------------------
function ingredientRow(name = "", amount = "") {
  const row = document.createElement("div");
  row.className = "ing-row";
  row.innerHTML = `
    <input class="ing-name" placeholder="Ingredient" value="${escapeAttr(name)}" />
    <input class="ing-amt" placeholder="Amount (e.g. 200 g)" value="${escapeAttr(amount)}" />
    <button type="button" class="rm" title="Remove">×</button>
  `;
  row.querySelector(".rm").addEventListener("click", () => row.remove());
  return row;
}

function openRecipeForm(recipe = null) {
  const editing = Boolean(recipe);
  const customTags = editing
    ? (recipe.tags || []).filter((t) => t.toLowerCase() !== (recipe.meal_type || "").toLowerCase())
    : [];

  modalEl.innerHTML = `
    <div class="modal-head">
      <h2>${editing ? "Edit recipe" : "New recipe"}</h2>
      <button class="close" aria-label="Close">×</button>
    </div>
    <div class="form-grid">
      <div class="field"><label>Name</label><input id="nr-name" placeholder="e.g. Pumpkin soup" value="${editing ? escapeAttr(recipe.name) : ""}" /></div>
      <div class="field two">
        <div><label>Meal type</label>
          <select id="nr-type">
            ${["breakfast", "lunch", "dinner", "snack"].map((type) =>
              `<option value="${type}"${(editing ? recipe.meal_type : "dinner") === type ? " selected" : ""}>${type[0].toUpperCase()}${type.slice(1)}</option>`
            ).join("")}
          </select>
        </div>
        <div><label>Prep time (min)</label><input id="nr-prep" type="number" min="0" placeholder="30" value="${editing && recipe.prep_time_min ? escapeAttr(String(recipe.prep_time_min)) : ""}" /></div>
      </div>
      <div class="field two">
        <div><label>Tags (comma-separated)</label><input id="nr-tags" placeholder="e.g. soup, vegan" value="${editing ? escapeAttr(customTags.join(", ")) : ""}" /></div>
        <div><label>Author</label><input id="nr-author" placeholder="You" value="${editing && recipe.author ? escapeAttr(recipe.author) : ""}" /></div>
      </div>
      <div class="field">
        <label>Ingredients &amp; amounts</label>
        <div class="ing-rows" id="nr-ings"></div>
        <button type="button" class="btn link" id="nr-add-ing">+ Add ingredient</button>
      </div>
      <div class="field"><label>Notes (markdown)</label><textarea id="nr-notes" class="note-editor" placeholder="# Steps&#10;- Do this&#10;- Then that">${editing ? escapeHtml(recipe.notes || "") : ""}</textarea></div>
    </div>
    <div class="modal-actions">
      <button class="btn" id="nr-cancel">${editing ? "Back" : "Cancel"}</button>
      <button class="btn primary" id="nr-save">${editing ? "Save changes" : "Create recipe"}</button>
    </div>
  `;

  const ings = modalEl.querySelector("#nr-ings");
  const details = editing
    ? (recipe.ingredient_details?.length
        ? recipe.ingredient_details
        : (recipe.ingredients || []).map((n) => ({ name: n, amount: "" })))
    : [{ name: "", amount: "" }, { name: "", amount: "" }];
  for (const item of details) {
    ings.appendChild(ingredientRow(item.name, item.amount));
  }
  if (!details.length) ings.appendChild(ingredientRow());

  modalEl.querySelector("#nr-add-ing").addEventListener("click", () => ings.appendChild(ingredientRow()));
  modalEl.querySelector(".close").addEventListener("click", closeModal);
  modalEl.querySelector("#nr-cancel").addEventListener("click", () => {
    if (editing) openRecipeDetail(recipe.id);
    else closeModal();
  });
  modalEl.querySelector("#nr-save").addEventListener("click", () => submitRecipeForm(recipe));
  openModal();
  modalEl.querySelector("#nr-name").focus();
}

function openNewRecipeForm() {
  openRecipeForm(null);
}

async function submitRecipeForm(recipe) {
  const name = modalEl.querySelector("#nr-name").value.trim();
  if (!name) {
    toast("Please give the recipe a name.");
    return;
  }
  const meal_type = modalEl.querySelector("#nr-type").value;
  const prepRaw = modalEl.querySelector("#nr-prep").value.trim();
  const tags = modalEl.querySelector("#nr-tags").value
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  const author = modalEl.querySelector("#nr-author").value.trim() || null;
  const notes = modalEl.querySelector("#nr-notes").value;
  const ingredients = [...modalEl.querySelectorAll(".ing-row")]
    .map((row) => ({
      name: row.querySelector(".ing-name").value.trim(),
      amount: row.querySelector(".ing-amt").value.trim(),
    }))
    .filter((i) => i.name);

  const payload = { name, meal_type, tags, author, notes, ingredients, full_replace: Boolean(recipe) };
  if (prepRaw) payload.prep_time_min = parseInt(prepRaw, 10);
  else if (recipe) payload.prep_time_min = null;

  const path = recipe ? "/api/recipes/update" : "/api/recipes/add";
  if (recipe) payload.id = recipe.id;

  try {
    const data = await api(path, payload);
    if (data.error) {
      toast(data.error);
      return;
    }
    state.recipes = data.recipes || [];
    state.tags = data.tags || [];
    renderTagFilter();
    renderRecipes();
    renderSummary();
    if (recipe) {
      openRecipeDetail(recipe.id);
      toast(`Saved “${name}”.`);
    } else {
      closeModal();
      toast(`Added “${name}”.`);
    }
  } catch (e) {
    setConnected(false);
  }
}

async function deleteRecipe(recipe) {
  const ok = window.confirm(`Delete “${recipe.name}”? This cannot be undone.`);
  if (!ok) return;
  try {
    const data = await api("/api/recipes/delete", { id: recipe.id });
    if (data.error) {
      toast(data.error);
      return;
    }
    state.recipes = data.recipes || [];
    state.tags = data.tags || [];
    renderTagFilter();
    renderRecipes();
    renderSummary();
    closeModal();
    toast(`Deleted “${recipe.name}”.`);
  } catch (e) {
    setConnected(false);
  }
}

// ---- modal helpers --------------------------------------------------------
function openModal() {
  modalOverlay.hidden = false;
}

function closeModal() {
  modalOverlay.hidden = true;
  modalEl.innerHTML = "";
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/`/g, "&#96;");
}

// ---- actions --------------------------------------------------------------
function addBubble(text, who) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${who === "You" ? "user" : "domus"}`;
  const label = document.createElement("span");
  label.className = "who";
  label.textContent = who;
  bubble.appendChild(label);
  bubble.appendChild(document.createTextNode(text));
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function sendMessage(text) {
  addBubble(text, DISPLAY_NAME);
  try {
    const data = await api("/api/message", {
      text,
      user: DISPLAY_NAME,
      user_id: USER_ID,
    });
    if (data.reply) addBubble(data.reply, "Domus");
    if (data.todos) {
      state.todos = data.todos;
      renderTodos();
    }
    if (data.reminders) {
      applyReminders(data.reminders);
      if (state.householdLoaded) renderReminders();
    }
    setConnected(true);
  } catch (e) {
    addBubble("I couldn't reach the Domus backend.", "Domus");
    setConnected(false);
  }
}

async function addTodo(name, category) {
  try {
    const data = await api("/api/todos/add", { name, category });
    state.todos = data.todos || [];
    renderTodos();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function checkOff(el, id) {
  el.classList.add("checking");
  try {
    const data = await api("/api/todos/toggle", { id, done: true, user_id: USER_ID });
    setTimeout(() => {
      state.todos = data.todos || [];
      renderTodos();
    }, 260);
  } catch (e) {
    el.classList.remove("checking");
    setConnected(false);
  }
}

async function removeItem(el, id) {
  el.classList.add("checking");
  try {
    const data = await api("/api/todos/remove", { id });
    setTimeout(() => {
      state.todos = data.todos || [];
      renderTodos();
    }, 220);
  } catch (e) {
    el.classList.remove("checking");
    setConnected(false);
  }
}

async function planRecipe(name) {
  try {
    const data = await api("/api/recipes/plan", { name });
    if (data.todos) state.todos = data.todos;
    renderTodos();
    if (data.reply) toast(data.reply);
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

let toastTimer = null;
function toast(text) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.style.cssText =
      "position:fixed;left:50%;bottom:96px;transform:translateX(-50%);max-width:440px;" +
      "background:var(--ink);color:var(--bg);padding:12px 16px;border-radius:12px;" +
      "font-size:13.5px;box-shadow:var(--glass-shadow);z-index:40;text-align:center;";
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.style.opacity = "1";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.style.opacity = "0"), 3200);
}

function setConnected(ok) {
  connectionEl.textContent = ok ? "connected" : "offline";
  connectionEl.classList.toggle("ok", ok);
}

// ---- form wiring ----------------------------------------------------------
composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendMessage(text);
});

addShoppingForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const name = shoppingInput.value.trim();
  if (!name) return;
  shoppingInput.value = "";
  addTodo(name, "shopping");
});

addTaskForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const name = taskInput.value.trim();
  if (!name) return;
  taskInput.value = "";
  addTodo(name, taskCategory.value);
});

newRecipeBtn.addEventListener("click", openNewRecipeForm);

modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) closeModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !modalOverlay.hidden) closeModal();
});

// ---- boot -----------------------------------------------------------------
loadTodos();
loadRecipes();
loadChatHistory();
