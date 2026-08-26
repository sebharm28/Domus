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
const tagFilterEl = document.getElementById("tag-filter");
const newRecipeBtn = document.getElementById("new-recipe-btn");
const modalOverlay = document.getElementById("modal-overlay");
const modalEl = document.getElementById("modal");

const state = {
  todos: [],
  recipes: [],
  tags: [],
  activeTag: null,
  recipesLoaded: false,
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
    .map((t) => `<span class="chip">${escapeHtml(t)}</span>`)
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
    <div class="modal-actions">
      <button class="btn link" id="edit-note">Edit notes</button>
    </div>
  `;
  modalEl.querySelector(".close").addEventListener("click", closeModal);
  modalEl.querySelector("#edit-note").addEventListener("click", () => editNotes(r));
  openModal();
}

function editNotes(r) {
  const actions = modalEl.querySelector(".modal-actions");
  const view = modalEl.querySelector("#note-view");
  view.outerHTML = `<textarea class="note-editor" id="note-edit" placeholder="Write notes in markdown…"># ${r.name}\n</textarea>`;
  const ta = modalEl.querySelector("#note-edit");
  ta.value = r.notes || "";
  ta.focus();
  actions.innerHTML = `
    <button class="btn" id="cancel-note">Cancel</button>
    <button class="btn primary" id="save-note">Save notes</button>
  `;
  actions.querySelector("#cancel-note").addEventListener("click", () => openRecipeDetail(r.id));
  actions.querySelector("#save-note").addEventListener("click", () => saveNotes(r.id, ta.value));
}

async function saveNotes(id, notes) {
  try {
    const data = await api("/api/recipes/update", { id, notes });
    state.recipes = data.recipes || state.recipes;
    state.tags = data.tags || state.tags;
    openRecipeDetail(id); // re-render with saved markdown
    toast("Notes saved.");
  } catch (e) {
    setConnected(false);
  }
}

// ---- new recipe form ------------------------------------------------------
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

function openNewRecipeForm() {
  modalEl.innerHTML = `
    <div class="modal-head">
      <h2>New recipe</h2>
      <button class="close" aria-label="Close">×</button>
    </div>
    <div class="form-grid">
      <div class="field"><label>Name</label><input id="nr-name" placeholder="e.g. Pumpkin soup" /></div>
      <div class="field two">
        <div><label>Meal type</label>
          <select id="nr-type">
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="dinner" selected>Dinner</option>
            <option value="snack">Snack</option>
          </select>
        </div>
        <div><label>Prep time (min)</label><input id="nr-prep" type="number" min="0" placeholder="30" /></div>
      </div>
      <div class="field two">
        <div><label>Tags (comma-separated)</label><input id="nr-tags" placeholder="soup, autumn" /></div>
        <div><label>Author</label><input id="nr-author" placeholder="You" /></div>
      </div>
      <div class="field">
        <label>Ingredients &amp; amounts</label>
        <div class="ing-rows" id="nr-ings"></div>
        <button type="button" class="btn link" id="nr-add-ing">+ Add ingredient</button>
      </div>
      <div class="field"><label>Notes (markdown)</label><textarea id="nr-notes" class="note-editor" placeholder="# Steps&#10;- Do this&#10;- Then that"></textarea></div>
    </div>
    <div class="modal-actions">
      <button class="btn" id="nr-cancel">Cancel</button>
      <button class="btn primary" id="nr-save">Create recipe</button>
    </div>
  `;
  const ings = modalEl.querySelector("#nr-ings");
  ings.appendChild(ingredientRow());
  ings.appendChild(ingredientRow());
  modalEl.querySelector("#nr-add-ing").addEventListener("click", () => ings.appendChild(ingredientRow()));
  modalEl.querySelector(".close").addEventListener("click", closeModal);
  modalEl.querySelector("#nr-cancel").addEventListener("click", closeModal);
  modalEl.querySelector("#nr-save").addEventListener("click", submitNewRecipe);
  openModal();
  modalEl.querySelector("#nr-name").focus();
}

async function submitNewRecipe() {
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

  const payload = { name, meal_type, tags, author, notes, ingredients };
  if (prepRaw) payload.prep_time_min = parseInt(prepRaw, 10);

  try {
    const data = await api("/api/recipes/add", payload);
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
    toast(`Added “${name}”.`);
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

newRecipeBtn.addEventListener("click", openNewRecipeForm);

modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) closeModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !modalOverlay.hidden) closeModal();
});

// ---- boot -----------------------------------------------------------------
addBubble("Hi! I'm Domus. Ask me to add items, plan meals, or set reminders — or use the tabs below.", "Domus");
loadTodos();
loadRecipes();
