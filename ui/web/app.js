const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("input");
const shoppingEl = document.getElementById("shopping");
const tasksEl = document.getElementById("tasks");
const refreshBtn = document.getElementById("refresh");
const connectionEl = document.getElementById("connection");

// A small emoji lookup so the Bring!-style tiles feel friendly. Falls back to a
// generic bag for anything unknown.
const EMOJI = {
  milk: "🥛", eggs: "🥚", butter: "🧈", bread: "🍞", cheese: "🧀",
  rice: "🍚", pasta: "🍝", coffee: "☕", tea: "🍵", water: "💧",
  apple: "🍎", apples: "🍎", banana: "🍌", bananas: "🍌", tomato: "🍅",
  tomatoes: "🍅", onion: "🧅", onions: "🧅", garlic: "🧄", potato: "🥔",
  potatoes: "🥔", carrot: "🥕", carrots: "🥕", chicken: "🍗", fish: "🐟",
  salmon: "🐟", beef: "🥩", curry: "🍛", chocolate: "🍫", sugar: "🧂",
  salt: "🧂", flour: "🌾", oil: "🫒", wine: "🍷", beer: "🍺",
  yogurt: "🥣", lemon: "🍋", lemons: "🍋", orange: "🍊", oranges: "🍊",
};

function emojiFor(name) {
  const key = (name || "").trim().toLowerCase();
  if (EMOJI[key]) return EMOJI[key];
  for (const word of key.split(/\s+/)) {
    if (EMOJI[word]) return EMOJI[word];
  }
  return "🛒";
}

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

function renderTodos(todos) {
  const shopping = todos.filter((t) => t.category === "shopping");
  const others = todos.filter((t) => t.category !== "shopping");

  shoppingEl.innerHTML = "";
  if (shopping.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Nothing to buy yet — try “Domus, add milk to the list”.";
    shoppingEl.appendChild(empty);
  } else {
    for (const item of shopping) {
      const tile = document.createElement("div");
      tile.className = "tile";
      tile.title = "Tap to check off";
      tile.innerHTML = `
        <span class="emoji">${emojiFor(item.name)}</span>
        <span class="name">${escapeHtml(item.name)}</span>
        ${item.quantity && item.quantity > 1 ? `<span class="qty">${item.quantity}</span>` : ""}
      `;
      tile.addEventListener("click", () => checkOff(tile, item.id));
      shoppingEl.appendChild(tile);
    }
  }

  tasksEl.innerHTML = "";
  if (others.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No other open tasks.";
    tasksEl.appendChild(empty);
  } else {
    for (const item of others) {
      const row = document.createElement("div");
      row.className = "task-row";
      const due = item.due_date ? ` · due ${item.due_date}` : "";
      row.innerHTML = `
        <span class="check"></span>
        <span class="label">${escapeHtml(item.name)}</span>
        <span class="badge">${escapeHtml(item.category)}</span>
        <span class="meta">${escapeHtml(due)}</span>
      `;
      row.addEventListener("click", () => checkOff(row, item.id));
      tasksEl.appendChild(row);
    }
  }
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function loadTodos() {
  try {
    const res = await fetch("/api/todos");
    const data = await res.json();
    renderTodos(data.todos || []);
    setConnected(true);
  } catch (err) {
    setConnected(false);
  }
}

async function sendMessage(text) {
  addBubble(text, "You");
  try {
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, user: "You" }),
    });
    const data = await res.json();
    if (data.reply) addBubble(data.reply, "Domus");
    if (data.todos) renderTodos(data.todos);
    setConnected(true);
  } catch (err) {
    addBubble("I couldn't reach the Domus backend.", "Domus");
    setConnected(false);
  }
}

async function checkOff(el, id) {
  el.classList.add("checking");
  try {
    const res = await fetch("/api/todos/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, done: true }),
    });
    const data = await res.json();
    // Let the pop animation finish before re-rendering the grid.
    setTimeout(() => renderTodos(data.todos || []), 260);
  } catch (err) {
    el.classList.remove("checking");
    setConnected(false);
  }
}

function setConnected(ok) {
  connectionEl.textContent = ok ? "connected" : "offline";
  connectionEl.classList.toggle("ok", ok);
}

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendMessage(text);
});

refreshBtn.addEventListener("click", loadTodos);

addBubble(
  "Hi! I'm Domus. Ask me to add items, show the list, plan meals, or set reminders.",
  "Domus"
);
loadTodos();
