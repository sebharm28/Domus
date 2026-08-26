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
const addShoppingForm = document.getElementById("add-shopping");
const shoppingInput = document.getElementById("shopping-input");
const addTaskForm = document.getElementById("add-task");
const taskInput = document.getElementById("task-input");
const taskCategory = document.getElementById("task-category");

const state = { todos: [], recipes: [], recipesLoaded: false };

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
function switchView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("is-active"));
  const view = document.getElementById(`view-${name}`);
  if (view) {
    view.classList.add("is-active");
    pageTitle.textContent = view.dataset.title || "Domus";
  }
  tabbar.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("is-active", t.dataset.view === name)
  );
  if (name === "recipes" && !state.recipesLoaded) loadRecipes();
}

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
    state.recipesLoaded = true;
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
    row.innerHTML = `
      <span class="check" title="Mark done"></span>
      <span class="label">${escapeHtml(item.name)}</span>
      <span class="badge">${escapeHtml(item.category)}</span>
      <span class="meta">${escapeHtml(due)}</span>
      <button class="del" title="Remove" aria-label="Remove">×</button>
    `;
    row.querySelector(".check").addEventListener("click", () => checkOff(row, item.id));
    row.querySelector(".del").addEventListener("click", () => removeItem(row, item.id));
    tasksEl.appendChild(row);
  }
}

function renderRecipes() {
  recipesEl.innerHTML = "";
  if (state.recipes.length === 0) {
    recipesEl.innerHTML = `<p class="empty">No recipes found.</p>`;
    return;
  }
  const order = { breakfast: 0, lunch: 1, dinner: 2, snack: 3 };
  const sorted = [...state.recipes].sort(
    (a, b) => (order[a.meal_type] ?? 9) - (order[b.meal_type] ?? 9) || a.name.localeCompare(b.name)
  );
  for (const r of sorted) {
    const card = document.createElement("div");
    card.className = "card";
    const prep = r.prep_time_min ? `~${r.prep_time_min} min` : "";
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
      ${r.notes ? `<p class="notes">${escapeHtml(r.notes)}</p>` : ""}
      <button class="plan">Add missing to list</button>
    `;
    card.querySelector(".plan").addEventListener("click", () => planRecipe(r.name));
    recipesEl.appendChild(card);
  }
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
  addBubble(text, "You");
  try {
    const data = await api("/api/message", { text, user: "You" });
    if (data.reply) addBubble(data.reply, "Domus");
    if (data.todos) {
      state.todos = data.todos;
      renderTodos();
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
    const data = await api("/api/todos/toggle", { id, done: true });
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

// ---- boot -----------------------------------------------------------------
addBubble("Hi! I'm Domus. Ask me to add items, plan meals, or set reminders — or use the tabs below.", "Domus");
loadTodos();
loadRecipes();
