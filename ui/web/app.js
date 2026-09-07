// ---- element refs ---------------------------------------------------------
const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("input");
const shoppingEl = document.getElementById("shopping");
const tasksEl = document.getElementById("tasks");
const recipesEl = document.getElementById("recipes");
const summaryEl = document.getElementById("summary");
const briefingCard = document.getElementById("briefing-card");
const chatEmptyEl = document.getElementById("chat-empty");
const chatEmptyHint = document.getElementById("chat-empty-hint");
const quickActionsEl = document.getElementById("quick-actions");
const authSignOutBtn = document.getElementById("auth-sign-out");
const homeApartmentEl = document.getElementById("home-apartment");
const notesBoardEl = document.getElementById("notes-board");
const notesNewBtn = document.getElementById("notes-new-btn");
const bathCleaningEl = document.getElementById("bath-cleaning");
const bathTowelsEl = document.getElementById("bath-towels");
const bathMedicineListEl = document.getElementById("bath-medicine-list");
const bathMedicineForm = document.getElementById("bath-medicine-form");
const mealPlannerGrid = document.getElementById("meal-planner-grid");
const mealPlannerTitle = document.getElementById("meal-planner-title");
const mealPlanWeekEl = document.getElementById("meal-plan-week");
const mealPlanOpenPlanner = document.getElementById("meal-plan-open-planner");
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
const taskDueInput = document.getElementById("task-due");
const taskCategory = document.getElementById("task-category");
const taskAssignee = document.getElementById("task-assignee");
const taskFiltersEl = document.getElementById("task-filters");
const checkedOffEl = document.getElementById("checked-off");
const checkedOffListEl = document.getElementById("checked-off-list");
const tagFilterEl = document.getElementById("tag-filter");
const newRecipeBtn = document.getElementById("new-recipe-btn");
const modalOverlay = document.getElementById("modal-overlay");
const modalEl = document.getElementById("modal");
const profilesEl = document.getElementById("profiles");
const statsEl = document.getElementById("stats");
const settingsEl = document.getElementById("settings");
const remindersEl = document.getElementById("reminders");
const profileChip = document.getElementById("profile-chip");
const profileChipName = document.getElementById("profile-chip-name");
const profileOverlay = document.getElementById("profile-overlay");
const profilePickList = document.getElementById("profile-pick-list");
const profileNewForm = document.getElementById("profile-new-form");
const profileNewName = document.getElementById("profile-new-name");
const profileNewApartment = document.getElementById("profile-new-apartment");
const profileCreatePassword = document.getElementById("profile-create-password");
const profileInviteToken = document.getElementById("profile-invite-token");
const profileJoinName = document.getElementById("profile-join-name");
const profileJoinPassword = document.getElementById("profile-join-password");
const profileJoinOtp = document.getElementById("profile-join-otp");
const profileLoginInvite = document.getElementById("profile-login-invite");
const profileLoginMember = document.getElementById("profile-login-member");
const profileLoginPassword = document.getElementById("profile-login-password");
const profileLoginOtp = document.getElementById("profile-login-otp");
const authModeHint = document.getElementById("auth-mode-hint");
const authSubmitBtn = document.getElementById("auth-submit-btn");
const authSetupToggle = document.getElementById("auth-setup-toggle");
const authSetupBody = document.getElementById("auth-setup-body");
const authSavedSection = document.getElementById("auth-saved-section");
const authTabs = document.querySelectorAll(".auth-tab");
const authPanels = document.querySelectorAll(".auth-panel");
const apartmentPanelEl = document.getElementById("apartment-panel");
const statsFiltersEl = document.getElementById("stats-filters");
const cleaningPlanListEl = document.getElementById("cleaning-plan-list");
const cleaningChoreForm = document.getElementById("cleaning-chore-form");
const openCleaningPlanBtn = document.getElementById("open-cleaning-plan");
const householdBadgeEl = document.getElementById("household-badge");

const CHECKED_OFF_MAX = 15;

const TASK_CATEGORIES = [
  { id: null, label: "All" },
  { id: "admin", label: "Admin" },
  { id: "household", label: "Household" },
  { id: "maintenance", label: "Maintenance" },
  { id: "personal", label: "Personal" },
  { id: "general", label: "General" },
];

const currentUser = {
  id: null,
  displayName: null,
  apartment: null,
  chatId: null,
  sessionToken: null,
};

const SESSION_STORAGE_KEY = "domus-session-tokens";
const ACTIVE_SESSION_KEY = "domus-active-session";
let chatLoadGeneration = 0;

function loadStoredSessionTokens() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function saveSessionToken(token) {
  if (!token) return;
  const tokens = loadStoredSessionTokens();
  if (!tokens.includes(token)) tokens.push(token);
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(tokens));
  localStorage.setItem(ACTIVE_SESSION_KEY, token);
}

function getActiveSessionToken() {
  return localStorage.getItem(ACTIVE_SESSION_KEY) || currentUser.sessionToken;
}

function inviteLinkForToken(token) {
  const base = `${window.location.origin}${window.location.pathname}`;
  return `${base}?invite=${encodeURIComponent(token)}`;
}

function getUserId() {
  return currentUser.id;
}

function apiPath(path) {
  const uid = getUserId();
  if (uid == null) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}user_id=${encodeURIComponent(uid)}`;
}

function getDisplayName() {
  return currentUser.displayName || "You";
}

function applyCurrentUser(id, displayName, apartment = null, chatId = null, sessionToken = null) {
  currentUser.id = id;
  currentUser.displayName = displayName;
  currentUser.apartment = apartment;
  currentUser.chatId = chatId;
  if (sessionToken) {
    currentUser.sessionToken = sessionToken;
    saveSessionToken(sessionToken);
  }
  localStorage.setItem("domus-user-id", String(id));
  localStorage.setItem("domus-display-name", displayName);
  if (apartment) localStorage.setItem("domus-apartment", apartment);
  else localStorage.removeItem("domus-apartment");
  if (profileChip && profileChipName) {
    profileChipName.textContent = apartment
      ? `${displayName} · ${apartment}`
      : displayName;
    profileChip.hidden = false;
  }
  if (state.householdLoaded) renderHousehold();
  updateHomeContext();
}

function applyAuthResult(data) {
  const profile = data.profile;
  if (!profile || !data.session_token) throw new Error("Invalid auth response");
  applyCurrentUser(
    profile.id,
    profile.display_name,
    profile.apartment || null,
    profile.chat_id ?? null,
    data.session_token
  );
}

function updateHomeContext() {
  const onHome = document.getElementById("view-home")?.classList.contains("is-active");
  const apt = currentUser.apartment;
  if (homeApartmentEl) {
    if (onHome && apt) {
      homeApartmentEl.textContent = apt;
      homeApartmentEl.hidden = false;
    } else {
      homeApartmentEl.hidden = true;
    }
  }
  if (chatEmptyHint && apt) {
    chatEmptyHint.textContent = `No messages yet for ${apt}. Say hi, add to your list, or tap a quick action above.`;
  } else if (chatEmptyHint) {
    chatEmptyHint.textContent =
      "Say hi, add something to your list, or use a quick action above.";
  }
}

function syncChatEmptyState() {
  const hasMessages = messagesEl.childElementCount > 0;
  if (chatEmptyEl) chatEmptyEl.hidden = hasMessages;
  messagesEl.classList.toggle("is-empty", !hasMessages);
  if (quickActionsEl) quickActionsEl.hidden = hasMessages;
}

function clearCurrentUser() {
  currentUser.id = null;
  currentUser.displayName = null;
  currentUser.apartment = null;
  currentUser.chatId = null;
  currentUser.sessionToken = null;
  localStorage.removeItem("domus-user-id");
  localStorage.removeItem("domus-display-name");
  localStorage.removeItem("domus-apartment");
  if (profileChip) profileChip.hidden = true;
}

function signOutOnDevice() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
  localStorage.removeItem(ACTIVE_SESSION_KEY);
  clearCurrentUser();
  state.entities = [];
  state.chatLoaded = false;
  messagesEl.innerHTML = "";
  syncChatEmptyState();
  renderProfilePicker();
  updateAuthSetupLayout();
  openProfilePicker({ required: true });
  toast("Signed out on this device.");
}

async function reloadSessionData() {
  if (!getUserId()) return;
  chatLoadGeneration += 1;
  messagesEl.innerHTML = "";
  syncChatEmptyState();
  await Promise.all([loadTodos(), loadChatHistory(), loadBriefing()]);
  updateHomeContext();
  if (state.householdLoaded) {
    const data = await api(apiPath("/api/reminders"));
    applyReminders(data);
    renderReminders();
  }
}

function isCurrentUser(who) {
  return who === getDisplayName();
}

function parseInviteToken(raw) {
  const value = (raw || "").trim();
  if (!value) return "";
  try {
    if (value.includes("://") || value.includes("?invite=")) {
      const url = value.startsWith("http") ? new URL(value) : new URL(`http://local${value.startsWith("?") ? value : `?${value}`}`);
      const fromQuery = url.searchParams.get("invite");
      if (fromQuery) return fromQuery.trim().toLowerCase();
    }
  } catch (_) {
    /* keep raw token */
  }
  return value.toLowerCase();
}

const AUTH_MODE_COPY = {
  create: {
    hint: "Start a new household. You become admin and member #1.",
    submit: "Create household",
  },
  join: {
    hint: "Got an invite from your roommate? Enter the link and your name.",
    submit: "Join household",
  },
  login: {
    hint: "Already a member? Log in on this phone or browser.",
    submit: "Log in",
  },
};

let authFormMode = "create";

function setAuthFormMode(mode) {
  authFormMode = mode;
  authTabs.forEach((tab) => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  authPanels.forEach((panel) => {
    panel.hidden = panel.dataset.mode !== mode;
  });
  const copy = AUTH_MODE_COPY[mode] || AUTH_MODE_COPY.create;
  if (authModeHint) authModeHint.textContent = copy.hint;
  if (authSubmitBtn) authSubmitBtn.textContent = copy.submit;
  if (mode === "login") syncLoginMembers();
}

function updateAuthSetupLayout() {
  const hasEntities = (state.entities || []).length > 0;
  if (authSavedSection) {
    authSavedSection.hidden = !hasEntities;
  }
  if (authSetupToggle && authSetupBody) {
    if (hasEntities) {
      authSetupToggle.hidden = false;
      const expanded = authSetupToggle.getAttribute("aria-expanded") === "true";
      authSetupBody.hidden = !expanded;
      authSetupToggle.textContent = expanded
        ? "Hide setup options"
        : "Add another household or device";
    } else {
      authSetupToggle.hidden = true;
      authSetupBody.hidden = false;
    }
  }
}

function openProfilePicker({ required = false } = {}) {
  if (!profileOverlay) return;
  profileOverlay.hidden = false;
  profileOverlay.classList.add("is-open");
  profileOverlay.dataset.required = required ? "1" : "0";
  if (authSignOutBtn) {
    authSignOutBtn.hidden = required || !getUserId();
  }
  if (authSetupToggle) authSetupToggle.setAttribute("aria-expanded", "false");
  renderProfilePicker();
  refreshEntityList().then(() => {
    updateAuthSetupLayout();
    setAuthFormMode(authFormMode);
  });
}

function closeProfilePicker() {
  if (!profileOverlay) return;
  if (profileOverlay.dataset.required === "1" && currentUser.id == null) return;
  profileOverlay.hidden = true;
  profileOverlay.classList.remove("is-open");
}

function renderProfilePicker() {
  if (!profilePickList) return;
  const entities = state.entities || [];
  if (entities.length === 0) {
    profilePickList.innerHTML = "";
    return;
  }
  profilePickList.innerHTML = entities
    .map(
      (e) => `
    <button type="button" class="profile-pick-btn${
      e.session_token === getActiveSessionToken() ? " is-active" : ""
    }" data-token="${escapeAttr(e.session_token)}">
      <strong>${escapeHtml(e.display_name)}</strong>
      <span class="muted">${escapeHtml(e.household_name || e.apartment || "")}</span>
    </button>`
    )
    .join("");
  updateAuthSetupLayout();
}

function selectEntity(sessionToken) {
  const entity = (state.entities || []).find((e) => e.session_token === sessionToken);
  if (!entity) return;
  applyCurrentUser(
    entity.user_id,
    entity.display_name,
    entity.apartment || null,
    entity.chat_id ?? null,
    entity.session_token
  );
  closeProfilePicker();
  reloadSessionData();
}

async function refreshEntityList() {
  const tokens = loadStoredSessionTokens();
  if (tokens.length === 0) {
    state.entities = [];
    renderProfilePicker();
    updateAuthSetupLayout();
    return;
  }
  try {
    const data = await api("/api/auth/entities", { session_tokens: tokens });
    state.entities = data.entities || [];
    const valid = new Set(state.entities.map((e) => e.session_token));
    const pruned = tokens.filter((t) => valid.has(t));
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(pruned));
    renderProfilePicker();
  } catch (_) {
    /* keep cached */
  }
  updateAuthSetupLayout();
}

async function createHouseholdAccount(displayName, householdName, password) {
  const data = await api("/api/auth/create-household", {
    display_name: displayName,
    household_name: householdName,
    password,
  });
  applyAuthResult(data);
  await refreshEntityList();
  closeProfilePicker();
  toast(`Household created. Password set — share invite link from Household tab.`);
  reloadSessionData();
}

async function joinHousehold(displayName, inviteToken, { password = "", otp = "" } = {}) {
  const body = { display_name: displayName, invite_token: inviteToken };
  if (password) body.password = password;
  if (otp) body.otp = otp;
  const data = await api("/api/auth/join", body);
  applyAuthResult(data);
  await refreshEntityList();
  closeProfilePicker();
  toast("Joined household.");
  reloadSessionData();
}

async function loginExistingEntity(userId, inviteToken, { password = "", otp = "" } = {}) {
  const body = { user_id: userId, invite_token: inviteToken };
  if (password) body.password = password;
  if (otp) body.otp = otp;
  const data = await api("/api/auth/login", body);
  applyAuthResult(data);
  await refreshEntityList();
  closeProfilePicker();
  toast("Logged in.");
  reloadSessionData();
}

async function initProfiles() {
  try {
    await refreshEntityList();
    const active = getActiveSessionToken();
    if (active) {
      const entity = (state.entities || []).find((e) => e.session_token === active);
      if (entity) {
        applyCurrentUser(
          entity.user_id,
          entity.display_name,
          entity.apartment || null,
          entity.chat_id ?? null,
          entity.session_token
        );
        setConnected(true);
        return;
      }
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
    clearCurrentUser();
    const params = new URLSearchParams(window.location.search);
    const invite = params.get("invite");
    if (invite) {
      const token = invite.trim().toLowerCase();
      if (profileInviteToken) profileInviteToken.value = token;
      if (profileLoginInvite) profileLoginInvite.value = token;
      authFormMode = "join";
    }
    openProfilePicker({ required: true });
    setAuthFormMode(authFormMode);
    setConnected(true);
  } catch (e) {
    setConnected(false);
    openProfilePicker({ required: true });
  }
}

const state = {
  todos: [],
  shopping: [],
  taskItems: [],
  checkedOff: [],
  taskCategoryFilter: null,
  recipes: [],
  tags: [],
  profiles: [],
  entities: [],
  settings: null,
  stats: [],
  reminders: { recurring: [], pending_timers: [], recent_timers: [] },
  chatLoaded: false,
  activeTag: null,
  recipesLoaded: false,
  householdLoaded: false,
  briefing: null,
  mealPlan: null,
  mealPlanWeekOffset: 0,
  kitchenNotes: [],
  noteColors: ["yellow", "pink", "blue", "green", "mint", "rosa"],
  bathCleaning: null,
  bathTowels: null,
  bathMedicine: null,
  apartment: null,
  cleaningPlan: null,
  statsFilterPerson: "all",
  statsFilterApartment: "mine",
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

// ---- dark mode (system / light / dark) ------------------------------------
const THEME_KEY = "domus-theme";

function getThemePreference() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark" || saved === "system") return saved;
  return "system";
}

function resolveTheme(preference) {
  if (preference === "light" || preference === "dark") return preference;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyThemePreference() {
  const preference = getThemePreference();
  const resolved = resolveTheme(preference);
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.dataset.themePref = preference;

  if (preference === "system") {
    themeIcon.textContent = "🖥️";
    themeToggle.title = `System theme (${resolved}) — click for light mode`;
  } else if (preference === "light") {
    themeIcon.textContent = "🌙";
    themeToggle.title = "Light mode — click for dark mode";
  } else {
    themeIcon.textContent = "☀️";
    themeToggle.title = "Dark mode — click for system theme";
  }
}

applyThemePreference();

themeToggle.addEventListener("click", () => {
  const pref = getThemePreference();
  const next = pref === "system" ? "light" : pref === "light" ? "dark" : "system";
  localStorage.setItem(THEME_KEY, next);
  applyThemePreference();
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (getThemePreference() === "system") applyThemePreference();
});

// ---- tab navigation -------------------------------------------------------
const TAB_PARENT = {
  recipes: "kitchen",
  "kitchen-timer": "kitchen",
  "kitchen-converter": "kitchen",
  "kitchen-notes": "kitchen",
  "kitchen-meal-planner": "kitchen",
  "bath-cleaning": "bath",
  "bath-towels": "bath",
  "bath-medicine": "bath",
  "bath-timer": "bath",
  "bath-brush": "bath",
  "household-cleaning": "household",
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

function playTimerDone(title = "Domus timer", body = "Time is up!") {
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
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      new Notification(title, { body, tag: "domus-timer", icon: "/favicon.ico" });
    } catch (_) {
      /* notification optional */
    }
  }
}

async function ensureTimerNotifications() {
  if (!("Notification" in window)) return;
  if (Notification.permission === "default") {
    try {
      await Notification.requestPermission();
    } catch (_) {
      /* user dismissed */
    }
  }
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
    playTimerDone("Domus timer", doneLabel);
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

  const customSet = root.querySelector(".timer-custom-set");
  if (customSet) {
    customSet.addEventListener("click", () => {
      const min = Number(root.querySelector(".timer-custom-min")?.value || 0);
      const sec = Number(root.querySelector(".timer-custom-sec")?.value || 0);
      const total = Math.floor(min) * 60 + Math.floor(sec);
      if (total <= 0) {
        toast("Enter a custom duration.");
        return;
      }
      presetBtns.forEach((b) => b.classList.remove("is-active"));
      totalSeconds = total;
      remainingSeconds = total;
      label = `Custom · ${formatTimerTime(total)}`;
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
    });
  }

  const activePreset = root.querySelector(".timer-preset.is-active");
  if (activePreset) selectPreset(activePreset);

  startBtn.addEventListener("click", () => {
    if (done) {
      done = false;
      remainingSeconds = totalSeconds;
    }
    if (totalSeconds <= 0) {
      toast("Pick a preset or set a custom duration.");
      return;
    }
    ensureTimerNotifications();
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
  if (name === "recipes") loadMealPlanStrip();
  if (name === "kitchen-notes") loadKitchenNotes();
  if (name === "kitchen-meal-planner") loadMealPlanner();
  if (name === "kitchen-converter") updateConverter();
  if (name === "bath-cleaning") loadBathCleaning();
  if (name === "bath-towels") loadBathTowels();
  if (name === "bath-medicine") loadBathMedicine();
  if (name === "household") loadHousehold();
  if (name === "household-cleaning") loadCleaningPlan();
  updateHomeContext();
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
  const headers = {};
  const token = getActiveSessionToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify({ ...body, session_token: token || body.session_token }) }
    : { headers };
  const res = await fetch(path, opts);
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(
        res.ok ? "Invalid server response" : `Server error (${res.status}) — restart ui/server.py?`
      );
    }
  }
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

async function loadHousehold() {
  try {
    const requests = [
      api("/api/profiles"),
      api("/api/settings"),
      api(statsApiPath()),
      api(apiPath("/api/reminders")),
    ];
    if (getUserId() && currentUser.apartment) {
      requests.push(api(apiPath("/api/apartment")));
    }
    const results = await Promise.all(requests);
    const [profiles, settings, stats, reminders, apartment] = results;
    state.profiles = profiles.profiles || [];
    state.settings = settings;
    state.stats = stats.stats || [];
    state.apartment = apartment || null;
    applyReminders(reminders);
    state.householdLoaded = true;
    renderHousehold();
    updatePendingBadge();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

function statsApiPath() {
  const params = new URLSearchParams();
  if (getUserId()) params.set("user_id", String(getUserId()));
  if (state.statsFilterPerson && state.statsFilterPerson !== "all") {
    params.set("person", String(state.statsFilterPerson));
  } else if (state.statsFilterPerson === "all") {
    params.set("person", "all");
  }
  if (state.statsFilterApartment === "all") {
    params.set("apartment", "all");
  } else if (state.statsFilterApartment === "mine" && currentUser.apartment) {
    params.set("apartment", currentUser.apartment);
  } else if (state.statsFilterApartment && state.statsFilterApartment !== "mine") {
    params.set("apartment", state.statsFilterApartment);
  }
  return `/api/stats?${params}`;
}

function updatePendingBadge() {
  if (!householdBadgeEl) return;
  const pending = state.apartment?.pending?.length || 0;
  const isOwner = (state.apartment?.members || []).some(
    (m) => m.user_id === getUserId() && m.role === "owner"
  );
  if (pending > 0 && isOwner) {
    householdBadgeEl.textContent = String(pending);
    householdBadgeEl.hidden = false;
  } else {
    householdBadgeEl.hidden = true;
  }
}

async function reloadStats() {
  try {
    const data = await api(statsApiPath());
    state.stats = data.stats || [];
    renderStatsPanel();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function loadBriefing() {
  if (!briefingCard) return;
  if (!getUserId()) {
    briefingCard.innerHTML = `<p class="briefing-placeholder muted">Pick a profile to see today's briefing.</p>`;
    return;
  }
  try {
    const data = await api(apiPath("/api/briefing"));
    state.briefing = data;
    renderBriefingCard();
    setConnected(true);
  } catch (e) {
    if (!state.briefing) {
      briefingCard.innerHTML = `<p class="briefing-placeholder muted">Couldn't load today's briefing.</p>`;
    }
    setConnected(false);
  }
}

function renderBriefingCard() {
  if (!briefingCard || !state.briefing) return;
  const b = state.briefing;
  const sections = [];

  if (b.held?.length) {
    sections.push(
      `<div class="briefing-section"><h3>Held overnight</h3><ul>${b.held
        .map((t) => `<li>${escapeHtml(t.text)} <span class="muted">· ${escapeHtml(t.due_label)}</span></li>`)
        .join("")}</ul></div>`
    );
  }

  if (b.due_today?.length) {
    sections.push(
      `<div class="briefing-section"><h3>Due today</h3><ul>${b.due_today
        .map((t) => `<li>${escapeHtml(t.text)} <span class="muted">· ${escapeHtml(t.category)}</span></li>`)
        .join("")}</ul></div>`
    );
  } else {
    sections.push(`<div class="briefing-section"><h3>Due today</h3><p class="muted">Nothing scheduled.</p></div>`);
  }

  if (b.overdue?.length) {
    sections.push(
      `<div class="briefing-section briefing-overdue"><h3>Overdue</h3><ul>${b.overdue
        .map((t) => `<li>${escapeHtml(t.text)} <span class="muted">· was ${escapeHtml(t.due_label)}</span></li>`)
        .join("")}</ul></div>`
    );
  }

  const shop = b.shopping || {};
  if (shop.count > 0) {
    const preview = (shop.preview || []).map((s) => escapeHtml(s)).join(", ");
    const extra = shop.count > (shop.preview?.length || 0) ? ` (+${shop.count - shop.preview.length} more)` : "";
    sections.push(
      `<div class="briefing-section"><h3>Shopping <span class="briefing-count">${shop.count}</span></h3><p>${preview}${extra}</p></div>`
    );
  }

  const other = b.other_open || {};
  if (other.count > 0) {
    sections.push(
      `<div class="briefing-section"><h3>Other tasks <span class="briefing-count">${other.count}</span></h3><ul>${(other.items || [])
        .map((t) => `<li>${escapeHtml(t.text)}</li>`)
        .join("")}${other.count > (other.items?.length || 0) ? `<li class="muted">…and ${other.count - other.items.length} more</li>` : ""}</ul></div>`
    );
  }

  if (b.meal_idea?.name) {
    const prep = b.meal_idea.prep_time_min ? ` (~${b.meal_idea.prep_time_min} min)` : "";
    const mealType = b.meal_idea.meal_type ? b.meal_idea.meal_type.charAt(0).toUpperCase() + b.meal_idea.meal_type.slice(1) : "Meal";
    sections.push(
      `<div class="briefing-section briefing-meal"><h3>${escapeHtml(mealType)} idea</h3><p>${escapeHtml(b.meal_idea.name)}${prep}</p></div>`
    );
  }

  const aptLine = b.apartment
    ? `<span class="briefing-apt">${escapeHtml(b.apartment)}</span>`
    : "";

  briefingCard.innerHTML = `
    <header class="briefing-header">
      <div>
        <h2 class="briefing-title">Today</h2>
        <p class="briefing-meta">${escapeHtml(b.date_label || "")}${aptLine ? ` · ${aptLine}` : ""}</p>
      </div>
      <button type="button" class="btn link briefing-refresh" id="briefing-refresh">Refresh</button>
    </header>
    <div class="briefing-body">${sections.join("")}</div>
  `;

  document.getElementById("briefing-refresh")?.addEventListener("click", () => loadBriefing());
}

async function loadChatHistory() {
  const generation = ++chatLoadGeneration;
  try {
    const data = await api(apiPath("/api/chat/history"));
    if (generation !== chatLoadGeneration) return;
    const turns = data.history || [];
    messagesEl.innerHTML = "";
    for (const turn of turns) {
      const who =
        turn.role === "user" ? turn.display_name || getDisplayName() : "Domus";
      appendBubble(turn.text, who);
    }
    state.chatLoaded = true;
    setConnected(true);
  } catch (e) {
    if (generation !== chatLoadGeneration) return;
    if (!state.chatLoaded && messagesEl.childElementCount === 0) {
      syncChatEmptyState();
    }
    setConnected(false);
  } finally {
    if (generation === chatLoadGeneration) {
      syncChatEmptyState();
      if (messagesEl.childElementCount > 0) scrollChatToBottom();
    }
  }
}

async function loadTodos() {
  try {
    await ensureProfiles();
    const data = await api(apiPath("/api/todos"));
    applyTodosData(data);
    renderTodos();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

function applyTodosData(data) {
  if (data.shopping && data.tasks) {
    state.shopping = data.shopping;
    state.taskItems = data.tasks;
    state.todos = [...state.shopping, ...state.taskItems];
  } else {
    state.todos = data.todos || [];
    state.shopping = state.todos.filter((t) => t.category === "shopping");
    state.taskItems = state.todos.filter((t) => t.category !== "shopping");
  }
}

async function ensureProfiles() {
  if (state.profiles.length === 0) {
    try {
      const data = await api("/api/profiles");
      state.profiles = data.profiles || [];
      renderTaskAssigneeOptions();
    } catch (_) {
      /* ignore */
    }
  }
}

function hasMultipleApartments() {
  const apartments = new Set(
    state.profiles.map((p) => p.apartment).filter(Boolean)
  );
  return apartments.size > 1;
}

function showApartmentTag(item) {
  if (!hasMultipleApartments()) return false;
  if (!item.apartment) return true;
  return item.apartment !== currentUser.apartment;
}

function apartmentTagLabel(item) {
  if (!item.apartment) return "Shared";
  return item.apartment;
}

function formatDueLabel(iso) {
  if (!iso) return "";
  try {
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  } catch (_) {
    return iso;
  }
}

function renderTaskAssigneeOptions() {
  if (!taskAssignee) return;
  const current = taskAssignee.value;
  taskAssignee.innerHTML = `<option value="">Anyone</option>${state.profiles
    .map(
      (p) =>
        `<option value="${p.id}">${escapeHtml(p.display_name)}${
          p.apartment ? ` · ${escapeHtml(p.apartment)}` : ""
        }</option>`
    )
    .join("")}`;
  if (current) taskAssignee.value = current;
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
    loadMealPlanStrip();
  } catch (e) {
    setConnected(false);
  }
}

// ---- kitchen: unit converter ------------------------------------------------
const G_PER_CUP = { water: 240, flour: 125, sugar: 200, butter: 227, rice: 185 };
const ML_PER_CUP = 240;
const ML_PER_TBSP = 15;

function convertIngredient(amount, from, ingredient) {
  const gPerCup = G_PER_CUP[ingredient] || 240;
  let grams;
  if (from === "g") grams = amount;
  else if (from === "cup") grams = amount * gPerCup;
  else if (from === "ml") grams = amount * (gPerCup / ML_PER_CUP);
  else if (from === "tbsp") grams = amount * ML_PER_TBSP * (gPerCup / ML_PER_CUP);
  else grams = amount;
  return {
    cup: grams / gPerCup,
    ml: (grams / gPerCup) * ML_PER_CUP,
    g: grams,
    tbsp: ((grams / gPerCup) * ML_PER_CUP) / ML_PER_TBSP,
  };
}

function updateConverter() {
  const amount = Number(document.getElementById("conv-amount")?.value || 0);
  const ingredient = document.getElementById("conv-ingredient")?.value || "water";
  const from = document.getElementById("conv-from")?.value || "cup";
  const resultEl = document.getElementById("conv-result");
  if (!resultEl || amount <= 0) {
    if (resultEl) resultEl.textContent = "Enter an amount to convert.";
    return;
  }
  const out = convertIngredient(amount, from, ingredient);
  resultEl.innerHTML = `
    <strong>${amount} ${from}</strong> ≈
    ${out.cup.toFixed(2)} cups ·
    ${Math.round(out.ml)} ml ·
    ${Math.round(out.g)} g ·
    ${out.tbsp.toFixed(1)} tbsp
  `;

  const temp = Number(document.getElementById("conv-temp")?.value || 0);
  const unit = document.getElementById("conv-temp-unit")?.value || "c";
  const tempEl = document.getElementById("conv-temp-result");
  if (tempEl) {
    if (unit === "c") {
      const f = temp * (9 / 5) + 32;
      tempEl.textContent = `${temp} °C ≈ ${f.toFixed(0)} °F (fan ovens often −20 °C)`;
    } else {
      const c = (temp - 32) * (5 / 9);
      tempEl.textContent = `${temp} °F ≈ ${c.toFixed(0)} °C`;
    }
  }
}

function initConverter() {
  const root = document.getElementById("unit-converter");
  if (!root) return;
  root.querySelectorAll(".converter-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      root.querySelectorAll(".converter-tab").forEach((t) => t.classList.remove("is-active"));
      root.querySelectorAll(".converter-panel").forEach((p) => p.classList.remove("is-active"));
      tab.classList.add("is-active");
      root.querySelector(`[data-panel="${tab.dataset.tab}"]`)?.classList.add("is-active");
    });
  });
  ["conv-amount", "conv-ingredient", "conv-from", "conv-temp", "conv-temp-unit"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", updateConverter);
    document.getElementById(id)?.addEventListener("change", updateConverter);
  });
  updateConverter();
}

// ---- kitchen: shared notes board ------------------------------------------
const NOTE_COLOR_CLASS = {
  yellow: "note-yellow",
  pink: "note-pink",
  blue: "note-blue",
  green: "note-green",
  mint: "note-mint",
  rosa: "note-rosa",
};

function mentionOptionsHtml() {
  const names = ["Domus", ...state.profiles.map((p) => p.display_name)];
  return [...new Set(names)]
    .map((n) => `<option value="${escapeAttr(n)}"></option>`)
    .join("");
}

function renderNoteBody(text) {
  let html = mdToHtml(text || "");
  html = html.replace(/@([\w.-]+)/g, '<span class="note-mention">@$1</span>');
  return html;
}

async function loadKitchenNotes() {
  if (!notesBoardEl) return;
  if (!getUserId()) {
    notesBoardEl.innerHTML = `<p class="empty">Pick a profile to see apartment notes.</p>`;
    return;
  }
  try {
    await ensureProfiles();
    const data = await api(apiPath("/api/kitchen-notes"));
    state.kitchenNotes = data.notes || [];
    state.noteColors = data.colors || state.noteColors;
    renderNotesBoard();
    setConnected(true);
  } catch (e) {
    notesBoardEl.innerHTML = `<p class="empty">Couldn't load notes.${e.message ? ` ${escapeHtml(e.message)}` : ""}</p>`;
    setConnected(false);
  }
}

function renderNotesBoard() {
  if (!notesBoardEl) return;
  if (state.kitchenNotes.length === 0) {
    notesBoardEl.innerHTML = `<p class="empty">No notes yet — tap + New note to pin one to the board.</p>`;
    return;
  }
  notesBoardEl.innerHTML = state.kitchenNotes
    .map((note) => {
      const colorClass = NOTE_COLOR_CLASS[note.color] || "note-yellow";
      return `
      <article class="sticky-note ${colorClass}" data-id="${note.id}">
        <header class="sticky-note-head">
          <span class="note-author">${escapeHtml(note.author_name)}</span>
          <span class="note-date">${escapeHtml(note.date_label || "")}</span>
        </header>
        <div class="note-preview">${renderNoteBody(note.preview || note.body)}</div>
      </article>`;
    })
    .join("");
  notesBoardEl.querySelectorAll(".sticky-note").forEach((card) => {
    card.addEventListener("click", () => openNoteEditor(Number(card.dataset.id)));
  });
}

function openNoteEditor(noteId) {
  const note = noteId
    ? state.kitchenNotes.find((n) => n.id === noteId)
    : null;
  const colors = state.noteColors
    .map(
      (c) =>
        `<button type="button" class="note-color-dot note-${c}${note?.color === c || (!note && c === "yellow") ? " is-active" : ""}" data-color="${c}" title="${c}"></button>`
    )
    .join("");
  modalEl.innerHTML = `
    <button class="close" type="button" aria-label="Close">×</button>
    <h2>${note ? "Edit note" : "New note"}</h2>
    <div class="note-editor-toolbar">
      <button type="button" class="note-md-btn" data-wrap="**" title="Bold"><strong>B</strong></button>
      <button type="button" class="note-md-btn" data-wrap="*" title="Italic"><em>I</em></button>
      <button type="button" class="note-md-btn" data-wrap="\`" title="Code">\`</button>
      <span class="note-md-hint">@ to mention · **bold** · *italic*</span>
    </div>
    <div class="note-color-row">${colors}</div>
    <textarea id="note-body" class="kitchen-notes" placeholder="Type your note… Use @Name or @Domus" list="note-mentions">${note ? escapeHtml(note.body) : ""}</textarea>
    <datalist id="note-mentions">${mentionOptionsHtml()}</datalist>
    <div class="note-preview-box" id="note-preview-box">${note ? renderNoteBody(note.body) : ""}</div>
    <div class="modal-actions">
      <button type="button" class="btn primary" id="note-save">Save</button>
      ${note ? `<button type="button" class="btn link" id="note-delete">Delete</button>` : ""}
      <button type="button" class="btn link" id="note-cancel">Cancel</button>
    </div>
  `;
  let selectedColor = note?.color || "yellow";
  const bodyEl = modalEl.querySelector("#note-body");
  const previewBox = modalEl.querySelector("#note-preview-box");
  bodyEl?.addEventListener("input", () => {
    if (previewBox) previewBox.innerHTML = renderNoteBody(bodyEl.value);
  });
  modalEl.querySelectorAll(".note-md-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      wrapNoteSelection(bodyEl, btn.dataset.wrap);
      if (previewBox) previewBox.innerHTML = renderNoteBody(bodyEl.value);
    });
  });
  modalEl.querySelectorAll(".note-color-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      selectedColor = dot.dataset.color;
      modalEl.querySelectorAll(".note-color-dot").forEach((d) => d.classList.remove("is-active"));
      dot.classList.add("is-active");
    });
  });
  modalEl.querySelector(".close")?.addEventListener("click", closeModal);
  modalEl.querySelector("#note-cancel")?.addEventListener("click", closeModal);
  modalEl.querySelector("#note-save")?.addEventListener("click", () =>
    saveNoteEditor(note?.id, selectedColor)
  );
  modalEl.querySelector("#note-delete")?.addEventListener("click", () =>
    deleteNote(note.id)
  );
  openModal();
  bodyEl?.focus();
}

function wrapNoteSelection(textarea, wrap) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const val = textarea.value;
  const selected = val.slice(start, end) || "text";
  textarea.value = val.slice(0, start) + wrap + selected + wrap + val.slice(end);
  textarea.focus();
}

async function saveNoteEditor(noteId, color) {
  const body = modalEl.querySelector("#note-body")?.value ?? "";
  try {
    if (noteId) {
      await api("/api/kitchen-notes/update", {
        id: noteId,
        body,
        color,
        user_id: getUserId(),
      });
    } else {
      await api("/api/kitchen-notes/create", {
        body,
        color,
        user_id: getUserId(),
      });
    }
    closeModal();
    await loadKitchenNotes();
    toast("Note saved.");
  } catch (e) {
    toast(e.message || "Couldn't save note.");
    setConnected(false);
  }
}

async function deleteNote(noteId) {
  if (!window.confirm("Delete this note?")) return;
  try {
    await api("/api/kitchen-notes/delete", { id: noteId, user_id: getUserId() });
    closeModal();
    await loadKitchenNotes();
    toast("Note deleted.");
  } catch (e) {
    setConnected(false);
  }
}

notesNewBtn?.addEventListener("click", () => openNoteEditor(null));

// ---- bath hub -------------------------------------------------------------
async function loadBathCleaning() {
  if (!bathCleaningEl || !getUserId()) return;
  try {
    const data = await api(apiPath("/api/bath/cleaning"));
    state.bathCleaning = data;
    renderBathCleaning();
    setConnected(true);
  } catch (e) {
    bathCleaningEl.innerHTML = `<p class="empty">Couldn't load checklist.</p>`;
    setConnected(false);
  }
}

function renderBathCleaning() {
  if (!bathCleaningEl || !state.bathCleaning) return;
  const items = state.bathCleaning.items || [];
  bathCleaningEl.innerHTML = items
    .map(
      (item) => `
    <button type="button" class="bath-tile${item.done ? " is-done" : ""}" data-key="${item.key}">
      <span class="bath-tile-check">${item.done ? "✓" : ""}</span>
      <span class="bath-tile-label">${escapeHtml(item.label)}</span>
      ${item.done_by ? `<span class="bath-tile-meta">${escapeHtml(item.done_by)}</span>` : ""}
    </button>`
    )
    .join("");
  bathCleaningEl.querySelectorAll(".bath-tile").forEach((tile) => {
    tile.addEventListener("click", () => toggleBathCleaning(tile.dataset.key));
  });
}

async function toggleBathCleaning(itemKey) {
  try {
    const data = await api("/api/bath/cleaning/toggle", {
      item_key: itemKey,
      user_id: getUserId(),
    });
    state.bathCleaning = data;
    renderBathCleaning();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function loadBathTowels() {
  if (!bathTowelsEl || !getUserId()) return;
  try {
    const data = await api(apiPath("/api/bath/towels"));
    state.bathTowels = data;
    renderBathTowels();
    setConnected(true);
  } catch (e) {
    bathTowelsEl.innerHTML = `<p class="empty">Couldn't load towels.</p>`;
    setConnected(false);
  }
}

function renderBathTowels() {
  if (!bathTowelsEl || !state.bathTowels) return;
  const threshold = state.bathTowels.wash_threshold || 4;
  bathTowelsEl.innerHTML = (state.bathTowels.towels || [])
    .map(
      (t) => `
    <article class="bath-towel-card${t.needs_wash ? " needs-wash" : ""}">
      <h3>${escapeHtml(t.label)}</h3>
      <p class="bath-towel-uses">${t.use_count} use${t.use_count === 1 ? "" : "s"} since wash</p>
      <p class="muted">${t.last_washed_label ? `Last washed ${escapeHtml(t.last_washed_label)}` : "Not washed yet"}</p>
      ${t.needs_wash ? `<p class="bath-wash-hint">Ready for laundry (≥${threshold} uses)</p>` : ""}
      <div class="bath-towel-actions">
        <button type="button" class="btn" data-action="use" data-label="${escapeAttr(t.label)}">+ Use</button>
        <button type="button" class="btn primary" data-action="washed" data-label="${escapeAttr(t.label)}">Washed</button>
      </div>
    </article>`
    )
    .join("");
  bathTowelsEl.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const label = btn.dataset.label;
      if (btn.dataset.action === "use") logTowelUse(label);
      else logTowelWashed(label);
    });
  });
}

async function logTowelUse(label) {
  try {
    const data = await api("/api/bath/towels/use", { label, user_id: getUserId() });
    state.bathTowels = data;
    renderBathTowels();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function logTowelWashed(label) {
  try {
    const data = await api("/api/bath/towels/washed", { label, user_id: getUserId() });
    state.bathTowels = data;
    renderBathTowels();
    toast(`${label} marked washed.`);
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function loadBathMedicine() {
  if (!bathMedicineListEl || !getUserId()) return;
  try {
    const data = await api(apiPath("/api/bath/medicine"));
    state.bathMedicine = data;
    renderBathMedicine();
    setConnected(true);
  } catch (e) {
    bathMedicineListEl.innerHTML = `<p class="empty">Couldn't load cabinet.${e.message ? ` ${escapeHtml(e.message)}` : ""}</p>`;
    setConnected(false);
  }
}

function renderBathMedicine() {
  if (!bathMedicineListEl || !state.bathMedicine) return;
  const items = state.bathMedicine.items || [];
  if (items.length === 0) {
    bathMedicineListEl.innerHTML = `<p class="empty">Nothing tracked yet — add items above.</p>`;
    return;
  }
  bathMedicineListEl.innerHTML = items
    .map(
      (item) => `
    <div class="bath-medicine-row status-${item.status}">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        ${item.quantity_note ? `<span class="muted"> · ${escapeHtml(item.quantity_note)}</span>` : ""}
        ${item.expiry_date ? `<p class="muted">Expires ${escapeHtml(item.expiry_date)}</p>` : ""}
      </div>
      <button type="button" class="del" data-id="${item.id}" aria-label="Remove">×</button>
    </div>`
    )
    .join("");
  bathMedicineListEl.querySelectorAll(".del").forEach((btn) => {
    btn.addEventListener("click", () => deleteMedicineItem(Number(btn.dataset.id)));
  });
}

async function deleteMedicineItem(id) {
  try {
    const data = await api("/api/bath/medicine/delete", { id, user_id: getUserId() });
    state.bathMedicine = data;
    renderBathMedicine();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

bathMedicineForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("medicine-name")?.value.trim();
  if (!name) return;
  const expiry = document.getElementById("medicine-expiry")?.value || null;
  const qty = document.getElementById("medicine-qty")?.value.trim() || null;
  try {
    const data = await api("/api/bath/medicine/add", {
      name,
      expiry_date: expiry,
      quantity_note: qty,
      user_id: getUserId(),
    });
    state.bathMedicine = data;
    renderBathMedicine();
    bathMedicineForm.reset();
    toast("Item added.");
    setConnected(true);
  } catch (err) {
    toast(err.message || "Couldn't add item.");
    setConnected(false);
  }
});

// ---- meal planner ---------------------------------------------------------
function mealPlanApiPath(weekOffset) {
  return apiPath(`/api/meal-plan?week=${weekOffset}`);
}

async function loadMealPlanner(weekOffset = state.mealPlanWeekOffset) {
  if (!mealPlannerGrid) return;
  state.mealPlanWeekOffset = weekOffset;
  try {
    const data = await api(mealPlanApiPath(weekOffset));
    state.mealPlan = data;
    renderMealPlanner();
    if (weekOffset === 0 && mealPlanWeekEl) {
      renderMealPlanWeek(data, mealPlanWeekEl, { compact: true });
    }
    setConnected(true);
  } catch (e) {
    mealPlannerGrid.innerHTML = `<p class="empty">Couldn't load meal plan.</p>`;
    setConnected(false);
  }
}

async function loadMealPlanStrip() {
  if (!mealPlanWeekEl) return;
  try {
    const data = await api(mealPlanApiPath(0));
    renderMealPlanWeek(data, mealPlanWeekEl, { compact: true });
    setConnected(true);
  } catch (e) {
    mealPlanWeekEl.innerHTML = `<p class="empty muted">Meal plan unavailable.</p>`;
  }
}

function renderMealPlanWeek(plan, container, { compact = false } = {}) {
  if (!container || !plan?.days) return;
  container.innerHTML = plan.days
    .map((d) => {
      const dish = d.dish
        ? `<span class="meal-plan-dish">${escapeHtml(d.dish)}</span>`
        : `<span class="meal-plan-empty">${compact ? "—" : "Add meal"}</span>`;
      return `
      <button type="button" class="meal-plan-day${d.is_today ? " is-today" : ""}${d.dish ? " has-meal" : ""}"
        data-day="${d.day}" title="${escapeHtml(d.dish || "No meal planned")}">
        <span class="meal-plan-wd">${escapeHtml(d.weekday)}</span>
        <span class="meal-plan-dt">${escapeHtml(d.label)}</span>
        ${dish}
      </button>`;
    })
    .join("");
  if (!compact) {
    container.querySelectorAll(".meal-plan-day").forEach((btn) => {
      btn.addEventListener("click", () => openMealPlanDayModal(btn.dataset.day));
    });
  } else {
    container.querySelectorAll(".meal-plan-day").forEach((btn) => {
      btn.addEventListener("click", () => switchView("kitchen-meal-planner"));
    });
  }
}

function renderMealPlanner() {
  if (!state.mealPlan || !mealPlannerGrid) return;
  const start = state.mealPlan.week_start;
  const end = state.mealPlan.week_end;
  if (mealPlannerTitle) {
    mealPlannerTitle.textContent =
      state.mealPlanWeekOffset === 0
        ? "This week"
        : `${start} – ${end}`;
  }
  renderMealPlanWeek(state.mealPlan, mealPlannerGrid, { compact: false });
}

function openMealPlanDayModal(day) {
  if (!state.recipesLoaded) loadRecipes();
  const dayInfo = state.mealPlan?.days?.find((d) => d.day === day);
  const recipeOptions = state.recipes.length
    ? state.recipes
        .map((r) => `<option value="${escapeAttr(r.name)}">${escapeHtml(r.name)}</option>`)
        .join("")
    : "";
  modalEl.innerHTML = `
    <button class="close" type="button" aria-label="Close">×</button>
    <h2>${escapeHtml(dayInfo?.weekday || "")} · ${escapeHtml(dayInfo?.label || day)}</h2>
    <div class="field">
      <label for="mp-dish">Meal</label>
      <input id="mp-dish" type="text" placeholder="Type a dish or suggestion" value="${dayInfo?.dish ? escapeAttr(dayInfo.dish) : ""}" list="mp-recipes" />
      <datalist id="mp-recipes">${recipeOptions}</datalist>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn primary" id="mp-save">Save</button>
      <button type="button" class="btn" id="mp-suggest">Suggest dinner</button>
      <button type="button" class="btn link" id="mp-clear">Clear</button>
      <button type="button" class="btn link" id="mp-cancel">Cancel</button>
    </div>
  `;
  modalEl.querySelector(".close").addEventListener("click", closeModal);
  modalEl.querySelector("#mp-cancel").addEventListener("click", closeModal);
  modalEl.querySelector("#mp-save").addEventListener("click", () => saveMealPlanDay(day));
  modalEl.querySelector("#mp-suggest").addEventListener("click", () => suggestMealPlanDay(day));
  modalEl.querySelector("#mp-clear").addEventListener("click", () => clearMealPlanDay(day));
  openModal();
  modalEl.querySelector("#mp-dish")?.focus();
}

async function saveMealPlanDay(day) {
  const dish = modalEl.querySelector("#mp-dish")?.value.trim();
  if (!dish) {
    toast("Enter a meal name.");
    return;
  }
  try {
    const data = await api("/api/meal-plan/set", {
      day,
      dish,
      week_offset: state.mealPlanWeekOffset,
      user_id: getUserId(),
    });
    state.mealPlan = data;
    closeModal();
    renderMealPlanner();
    renderMealPlanStrip();
    toast("Meal saved.");
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function suggestMealPlanDay(day) {
  try {
    const data = await api("/api/meal-plan/suggest", {
      day,
      week_offset: state.mealPlanWeekOffset,
      user_id: getUserId(),
    });
    state.mealPlan = data;
    closeModal();
    renderMealPlanner();
    renderMealPlanStrip();
    toast("Dinner suggested.");
    setConnected(true);
  } catch (e) {
    toast("Couldn't suggest a meal.");
    setConnected(false);
  }
}

async function clearMealPlanDay(day) {
  try {
    const data = await api("/api/meal-plan/clear", {
      day,
      week_offset: state.mealPlanWeekOffset,
      user_id: getUserId(),
    });
    state.mealPlan = data;
    closeModal();
    renderMealPlanner();
    renderMealPlanStrip();
    toast("Day cleared.");
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function autoMealPlanWeek() {
  try {
    const data = await api("/api/meal-plan/auto", {
      week_offset: state.mealPlanWeekOffset,
      user_id: getUserId(),
    });
    state.mealPlan = data;
    renderMealPlanner();
    renderMealPlanStrip();
    const msg =
      data.planned_count > 0
        ? `Planned ${data.planned_count} dinners.${data.shopping_added?.length ? ` Added ${data.shopping_added.length} items to shopping.` : ""}`
        : "No dinners could be planned.";
    toast(msg);
    if (data.shopping_added?.length) loadTodos();
    setConnected(true);
  } catch (e) {
    toast("Couldn't plan the week.");
    setConnected(false);
  }
}

document.getElementById("meal-plan-prev")?.addEventListener("click", () =>
  loadMealPlanner(state.mealPlanWeekOffset - 1)
);
document.getElementById("meal-plan-next")?.addEventListener("click", () =>
  loadMealPlanner(state.mealPlanWeekOffset + 1)
);
document.getElementById("meal-plan-today")?.addEventListener("click", () => loadMealPlanner(0));
document.getElementById("meal-plan-auto")?.addEventListener("click", () => autoMealPlanWeek());
mealPlanOpenPlanner?.addEventListener("click", () => switchView("kitchen-meal-planner"));

// ---- rendering ------------------------------------------------------------
function renderTodos() {
  renderShopping(state.shopping);
  renderCheckedOff();
  renderTaskFilters();
  const filtered = state.taskCategoryFilter
    ? state.taskItems.filter((t) => t.category === state.taskCategoryFilter)
    : state.taskItems;
  renderTasks(filtered);
  renderSummary();
}

function renderTaskFilters() {
  if (!taskFiltersEl) return;
  taskFiltersEl.innerHTML = TASK_CATEGORIES.map(
    (cat) =>
      `<button type="button" class="task-filter-chip${
        state.taskCategoryFilter === cat.id ? " is-active" : ""
      }" data-category="${cat.id ?? ""}">${escapeHtml(cat.label)}</button>`
  ).join("");
}

function renderSummary() {
  const shopping = state.shopping.length;
  const tasks = state.taskItems.length;
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
    const qty = item.quantity && item.quantity > 1 ? item.quantity : 1;
    const tile = document.createElement("div");
    tile.className = "tile";
    tile.title = "Tap to check off";
    const aptTag = showApartmentTag(item)
      ? `<span class="apt-tag" title="Apartment">${escapeHtml(apartmentTagLabel(item))}</span>`
      : "";
    tile.innerHTML = `
      <button class="del" title="Remove" aria-label="Remove">×</button>
      ${aptTag}
      <span class="emoji">${emojiFor(item.name)}</span>
      <span class="name">${escapeHtml(item.name)}</span>
      <div class="qty-controls">
        <button type="button" class="qty-btn" data-delta="-1" aria-label="Decrease quantity">−</button>
        <span class="qty-val">${qty}</span>
        <button type="button" class="qty-btn" data-delta="1" aria-label="Increase quantity">+</button>
      </div>
    `;
    tile.querySelector(".del").addEventListener("click", (e) => {
      e.stopPropagation();
      removeItem(tile, item.id);
    });
    tile.querySelectorAll(".qty-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        adjustQuantity(item.id, Number(btn.dataset.delta));
      });
    });
    tile.addEventListener("click", () => checkOff(tile, item));
    shoppingEl.appendChild(tile);
  }
}

function renderCheckedOff() {
  if (!checkedOffEl || !checkedOffListEl) return;
  if (state.checkedOff.length === 0) {
    checkedOffEl.hidden = true;
    return;
  }
  checkedOffEl.hidden = false;
  checkedOffListEl.innerHTML = state.checkedOff
    .map(
      (entry) => `
    <li class="checked-off-item">
      <span>${escapeHtml(entry.label)}</span>
      <button type="button" class="btn link checked-off-undo" data-id="${entry.id}">Undo</button>
    </li>`
    )
    .join("");
  checkedOffListEl.querySelectorAll(".checked-off-undo").forEach((btn) => {
    btn.addEventListener("click", () => {
      const entry = state.checkedOff.find((e) => e.id === Number(btn.dataset.id));
      if (entry) undoCheckOff(entry);
    });
  });
}

function renderTasks(items) {
  tasksEl.innerHTML = "";
  if (items.length === 0) {
    const hint = state.taskCategoryFilter
      ? `No ${state.taskCategoryFilter} tasks — try another filter or add one above.`
      : "No open tasks — add one above.";
    tasksEl.innerHTML = `<p class="empty">${hint}</p>`;
    return;
  }
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "row";
    const due = item.due_date
      ? `<span class="row-tag row-due">Due ${escapeHtml(formatDueLabel(item.due_date))}</span>`
      : "";
    const assignee = item.assigned_to
      ? `<span class="row-tag row-assignee">→ ${escapeHtml(item.assigned_to)}</span>`
      : "";
    const apt =
      item.apartment && (hasMultipleApartments() || item.apartment !== currentUser.apartment)
        ? `<span class="row-tag row-apt">${escapeHtml(item.apartment)}</span>`
        : "";
    row.innerHTML = `
      <span class="check" title="Mark done"></span>
      <div class="row-main">
        <span class="label">${escapeHtml(item.name)}</span>
        <div class="row-tags">
          <span class="badge">${escapeHtml(item.category)}</span>
          ${apt}${assignee}${due}
        </div>
      </div>
      <button class="del" title="Remove" aria-label="Remove">×</button>
    `;
    row.querySelector(".check").addEventListener("click", () => checkOff(row, item));
    row.querySelector(".del").addEventListener("click", () => removeItem(row, item.id));
    tasksEl.appendChild(row);
  }
}

function renderApartmentPanel() {
  if (!apartmentPanelEl) return;
  const apt = state.apartment;
  if (!apt?.apartment) {
    apartmentPanelEl.innerHTML = `<p class="empty muted">Switch to a household entity to manage members and invites.</p>`;
    return;
  }
  const members = apt.members || [];
  const isOwner = members.some(
    (m) => m.user_id === getUserId() && m.role === "owner" && m.status === "active"
  );
  const inviteToken = apt.invite_token || "";
  const inviteLink = inviteToken ? inviteLinkForToken(inviteToken) : "";
  apartmentPanelEl.innerHTML = `
    <p class="household-name"><strong>${escapeHtml(apt.household_name || apt.apartment)}</strong></p>
    ${
      inviteLink
        ? `<div class="invite-box">
            <span class="invite-box-label">Invite link</span>
            <code class="invite-link">${escapeHtml(inviteLink)}</code>
          </div>`
        : ""
    }
    <p class="apartment-code muted">Legacy join code: <code>${escapeHtml(apt.join_code || "—")}</code></p>
    <div class="apartment-actions">
      <button type="button" class="btn link" id="apt-copy-invite">Copy invite link</button>
      ${isOwner ? `<button type="button" class="btn link" id="apt-regen-invite">New invite link</button>` : ""}
      <button type="button" class="btn link" id="apt-gen-otp">Show join code (OTP)</button>
      ${isOwner ? `<button type="button" class="btn link" id="apt-regen-code">New legacy code</button>` : ""}
      <button type="button" class="btn link" id="apt-export">Export data</button>
      <button type="button" class="btn link" id="apt-import">Import to new household</button>
      <button type="button" class="btn link" id="apt-leave">Leave household</button>
    </div>
    <p class="muted section-hint">New members join with the invite link + household password or a one-time OTP.</p>
    <h3 class="apartment-subhead">Members</h3>
    <ul class="apartment-members">
      ${members
        .map(
          (m) => `
        <li>
          <span class="apartment-member-name">${escapeHtml(m.display_name)} <span class="muted">${escapeHtml(m.role)}</span></span>
          <span class="apartment-member-actions">
        ${isOwner && m.role !== "owner" && m.user_id !== getUserId()
          ? `<button type="button" class="btn link apt-kick" data-id="${m.user_id}">Remove</button>
             <button type="button" class="btn link apt-transfer" data-id="${m.user_id}">Make admin</button>`
          : ""}
        ${isOwner || m.user_id === getUserId()
          ? `<button type="button" class="btn link apt-rename" data-id="${m.user_id}" data-name="${escapeAttr(m.display_name)}">Rename</button>`
          : ""}
          </span>
        </li>`
        )
        .join("")}
    </ul>
  `;
  apartmentPanelEl.querySelector("#apt-copy-invite")?.addEventListener("click", () => {
    if (!inviteLink) return;
    navigator.clipboard?.writeText(inviteLink);
    toast("Invite link copied.");
  });
  apartmentPanelEl.querySelector("#apt-regen-invite")?.addEventListener("click", regenerateInviteLink);
  apartmentPanelEl.querySelector("#apt-gen-otp")?.addEventListener("click", generateJoinOtp);
  apartmentPanelEl.querySelector("#apt-export")?.addEventListener("click", exportHouseholdData);
  apartmentPanelEl.querySelector("#apt-import")?.addEventListener("click", importHouseholdData);
  apartmentPanelEl.querySelectorAll(".apt-kick").forEach((btn) => {
    btn.addEventListener("click", () => kickApartmentMember(Number(btn.dataset.id)));
  });
  apartmentPanelEl.querySelectorAll(".apt-transfer").forEach((btn) => {
    btn.addEventListener("click", () => transferAdmin(Number(btn.dataset.id)));
  });
  apartmentPanelEl.querySelectorAll(".apt-rename").forEach((btn) => {
    btn.addEventListener("click", () =>
      renameMember(Number(btn.dataset.id), btn.dataset.name || "")
    );
  });
  apartmentPanelEl.querySelector("#apt-regen-code")?.addEventListener("click", regenerateJoinCode);
  apartmentPanelEl.querySelector("#apt-leave")?.addEventListener("click", leaveApartment);
}

async function regenerateInviteLink() {
  if (!window.confirm("Generate a new invite link? Old links will stop working.")) return;
  try {
    const data = await api(apiPath("/api/household/regenerate-invite"), {});
    state.apartment = { ...state.apartment, ...data };
    renderApartmentPanel();
    toast("New invite link generated.");
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not regenerate invite link.");
  }
}

async function generateJoinOtp() {
  try {
    const data = await api(apiPath("/api/household/generate-otp"), {});
    toast(`Join code: ${data.code} (valid ${data.ttl_minutes} min)`);
  } catch (e) {
    toast(e.message || "Could not generate code.");
  }
}

async function exportHouseholdData() {
  const anonymize = window.confirm(
    "Anonymize names in history (who did what)?\n\nOK = anonymize ex-partners etc.\nCancel = keep original names."
  );
  try {
    const path = apiPath(`/api/household/export?anonymize=${anonymize ? "1" : "0"}`);
    const data = await api(path);
    const blob = new Blob([JSON.stringify(data.export, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `domus-export-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast(anonymize ? "Exported (anonymized)." : "Exported.");
  } catch (e) {
    toast(e.message || "Export failed.");
  }
}

async function importHouseholdData() {
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "application/json,.json";
  fileInput.onchange = async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const adminName = window.prompt("Your name in the new household:", getDisplayName());
    if (!adminName) return;
    const password = window.prompt("Password for the new household (min 4 chars):");
    if (!password || password.length < 4) {
      toast("Password required (min 4 characters).");
      return;
    }
    const newName = window.prompt("New household name (leave empty to keep exported name):") || "";
    try {
      const text = await file.text();
      const bundle = JSON.parse(text);
      const data = await api("/api/household/import", {
        export: bundle,
        display_name: adminName,
        password,
        household_name: newName || undefined,
      });
      applyAuthResult(data);
      await refreshEntityList();
      toast("Imported into new household.");
      reloadSessionData();
    } catch (e) {
      toast(e.message || "Import failed.");
    }
  };
  fileInput.click();
}

async function transferAdmin(memberId) {
  if (!window.confirm("Transfer admin role to this member?")) return;
  try {
    const data = await api(apiPath("/api/household/transfer-admin"), { member_id: memberId });
    state.apartment = { ...state.apartment, ...data };
    renderApartmentPanel();
    toast("Admin transferred.");
  } catch (e) {
    toast(e.message || "Could not transfer admin.");
  }
}

async function renameMember(memberId, currentName) {
  const newName = window.prompt("New name:", currentName);
  if (!newName || newName.trim() === currentName) return;
  try {
    const data = await api(apiPath("/api/household/rename-member"), {
      member_id: memberId,
      display_name: newName.trim(),
    });
    state.apartment = { ...state.apartment, ...data };
    if (memberId === getUserId()) {
      applyCurrentUser(getUserId(), newName.trim(), currentUser.apartment, currentUser.chatId, getActiveSessionToken());
    }
    renderApartmentPanel();
    renderProfiles();
    toast("Renamed.");
  } catch (e) {
    toast(e.message || "Could not rename.");
  }
}

async function regenerateJoinCode() {
  if (!window.confirm("Generate a new join code? The old code will stop working.")) return;
  try {
    const data = await api(apiPath("/api/apartment/regenerate-code"), {});
    state.apartment = data;
    renderApartmentPanel();
    toast(`New code: ${data.join_code}`);
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not regenerate code.");
    setConnected(false);
  }
}

async function leaveApartment() {
  if (!window.confirm("Leave this apartment? You will lose access to its chat and tasks.")) return;
  try {
    await api(apiPath("/api/apartment/leave"), {});
    currentUser.apartment = null;
    state.apartment = null;
    toast("Left apartment.");
    reloadSessionData();
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not leave apartment.");
    setConnected(false);
  }
}

function openProfileEditor(profile) {
  modalEl.innerHTML = `
    <button class="close" type="button" aria-label="Close">×</button>
    <h2>Edit profile</h2>
    <div class="field">
      <label for="pe-diet">Diet</label>
      <input id="pe-diet" type="text" value="${escapeAttr(profile.diet || "")}" placeholder="e.g. vegetarian" />
    </div>
    <div class="field">
      <label for="pe-allergies">Allergies</label>
      <input id="pe-allergies" type="text" value="${escapeAttr(profile.allergies || "")}" placeholder="comma-separated" />
    </div>
    <div class="field">
      <label for="pe-likes">Likes</label>
      <input id="pe-likes" type="text" value="${escapeAttr(profile.likes || "")}" placeholder="comma-separated" />
    </div>
    <div class="field">
      <label for="pe-dislikes">Dislikes</label>
      <input id="pe-dislikes" type="text" value="${escapeAttr(profile.dislikes || "")}" placeholder="comma-separated" />
    </div>
    <div class="modal-actions">
      <button type="button" class="btn primary" id="pe-save">Save</button>
      <button type="button" class="btn link" id="pe-cancel">Cancel</button>
    </div>
  `;
  modalEl.querySelector(".close")?.addEventListener("click", closeModal);
  modalEl.querySelector("#pe-cancel")?.addEventListener("click", closeModal);
  modalEl.querySelector("#pe-save")?.addEventListener("click", () => saveProfileEditor(profile.id));
  openModal();
}

async function saveProfileEditor(profileId) {
  try {
    const data = await api(apiPath("/api/profiles/update"), {
      profile_id: profileId,
      diet: modalEl.querySelector("#pe-diet")?.value.trim() || "",
      allergies: modalEl.querySelector("#pe-allergies")?.value.trim() || "",
      likes: modalEl.querySelector("#pe-likes")?.value.trim() || "",
      dislikes: modalEl.querySelector("#pe-dislikes")?.value.trim() || "",
    });
    state.profiles = data.profiles || [];
    const profile = data.profile;
    if (profile && profile.id === currentUser.id) {
      applyCurrentUser(
        profile.id,
        profile.display_name,
        profile.apartment,
        profile.chat_id,
        getActiveSessionToken()
      );
    }
    closeModal();
    renderHousehold();
    toast("Profile updated.");
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not save profile.");
    setConnected(false);
  }
}

async function acceptApartmentMember(userId) {
  try {
    const data = await api(apiPath("/api/apartment/accept"), { member_id: userId });
    state.apartment = data;
    state.profiles = data.profiles || state.profiles;
    renderHousehold();
    toast("Member accepted.");
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not accept member.");
    setConnected(false);
  }
}

async function kickApartmentMember(userId) {
  if (!window.confirm("Remove this member from the apartment?")) return;
  try {
    const data = await api(apiPath("/api/apartment/kick"), { member_id: userId });
    state.apartment = data;
    state.profiles = data.profiles || state.profiles;
    renderHousehold();
    toast("Member removed.");
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not remove member.");
    setConnected(false);
  }
}

function renderStatsPanel() {
  if (!statsEl) return;
  renderStatsFilters();
  if (state.stats.length === 0) {
    statsEl.innerHTML = `<p class="empty">No completed tasks in the last 7 days for this filter.</p>`;
    return;
  }
  statsEl.innerHTML = state.stats
    .map(
      (s) => `
      <div class="stat-row">
        <strong>${escapeHtml(s.display_name)}</strong>
        <span>${s.count} completed</span>
        ${s.apartment ? `<span class="muted">${escapeHtml(s.apartment)}</span>` : ""}
        ${s.samples?.length ? `<span class="muted">${escapeHtml(s.samples.slice(0, 2).join(", "))}</span>` : ""}
      </div>`
    )
    .join("");
}

function renderStatsFilters() {
  if (!statsFiltersEl) return;
  const profiles = householdProfiles();
  const apartments = [...new Set(profiles.map((p) => p.apartment).filter(Boolean))];
  const personOptions = profiles
    .map(
      (p) =>
        `<option value="${p.id}"${String(state.statsFilterPerson) === String(p.id) ? " selected" : ""}>${escapeHtml(p.display_name)}</option>`
    )
    .join("");
  const aptOptions = apartments
    .map(
      (a) =>
        `<option value="${escapeAttr(a)}"${state.statsFilterApartment === a ? " selected" : ""}>${escapeHtml(a)}</option>`
    )
    .join("");
  statsFiltersEl.innerHTML = `
    <label class="stats-filter">
      <span>Person</span>
      <select id="stats-person-filter">
        <option value="all"${state.statsFilterPerson === "all" ? " selected" : ""}>Everyone</option>
        ${personOptions}
      </select>
    </label>
    <label class="stats-filter">
      <span>Apartment</span>
      <select id="stats-apt-filter">
        <option value="mine"${state.statsFilterApartment === "mine" ? " selected" : ""}>My apartment</option>
        <option value="all"${state.statsFilterApartment === "all" ? " selected" : ""}>All apartments</option>
        ${aptOptions}
      </select>
    </label>
  `;
  statsFiltersEl.querySelector("#stats-person-filter")?.addEventListener("change", (e) => {
    state.statsFilterPerson = e.target.value === "all" ? "all" : Number(e.target.value);
    reloadStats();
  });
  statsFiltersEl.querySelector("#stats-apt-filter")?.addEventListener("change", (e) => {
    state.statsFilterApartment = e.target.value;
    reloadStats();
  });
}

function householdProfiles() {
  const apt = currentUser.apartment;
  const memberIds = new Set(
    (state.apartment?.members || [])
      .filter((m) => m.status === "active")
      .map((m) => m.user_id)
  );
  if (apt && memberIds.size > 0) {
    return state.profiles.filter((p) => memberIds.has(p.id));
  }
  if (apt) {
    return state.profiles.filter((p) => p.apartment === apt);
  }
  return state.profiles;
}

function renderHousehold() {
  if (!profilesEl) return;

  renderApartmentPanel();

  const profiles = householdProfiles();
  if (profiles.length === 0) {
    profilesEl.innerHTML = `<p class="empty">No household members yet.</p>`;
  } else {
    profilesEl.innerHTML = profiles
      .map(
        (p) => `
      <article class="profile-card${p.id === currentUser.id ? " is-you" : ""}">
        <header class="profile-card-head">
          <h3>${escapeHtml(p.display_name)}${p.id === currentUser.id ? ' <span class="you-badge">you</span>' : ""}</h3>
          ${p.id === currentUser.id ? `<button type="button" class="btn link profile-edit-btn" data-id="${p.id}">Edit</button>` : ""}
        </header>
        ${p.apartment ? `<p><strong>Apartment:</strong> ${escapeHtml(p.apartment)}</p>` : ""}
        ${p.membership_status === "pending" ? `<p class="muted">Join request pending approval</p>` : ""}
        ${p.diet ? `<p><strong>Diet:</strong> ${escapeHtml(p.diet)}</p>` : ""}
        ${p.likes ? `<p><strong>Likes:</strong> ${escapeHtml(p.likes)}</p>` : ""}
        ${p.dislikes ? `<p><strong>Dislikes:</strong> ${escapeHtml(p.dislikes)}</p>` : ""}
        ${p.allergies ? `<p><strong>Allergies:</strong> ${escapeHtml(p.allergies)}</p>` : ""}
      </article>`
      )
      .join("");
    profilesEl.querySelectorAll(".profile-edit-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const profile = state.profiles.find((p) => p.id === Number(btn.dataset.id));
        if (profile) openProfileEditor(profile);
      });
    });
  }

  renderStatsPanel();

  const cfg = state.settings || {};
  settingsEl.innerHTML = `
    <dl class="settings-dl">
      <dt>Morning briefing</dt><dd>${cfg.briefing_hour ?? 8}:00 daily</dd>
      <dt>Evening summary</dt><dd>${cfg.evening_briefing_hour ?? 20}:00 daily</dd>
      <dt>Quiet hours</dt><dd>${cfg.quiet_hours_enabled ? `${cfg.quiet_hours_start}:00 – ${cfg.quiet_hours_end}:00` : "Off"}</dd>
      <dt>Redaction before LLM</dt><dd>${cfg.redaction_enabled ? "On" : "Off"}</dd>
      <dt>OpenRouter (smarter chat)</dt><dd>${cfg.openrouter_configured ? `On — ${escapeHtml(cfg.openrouter_model || "default model")}` : "Off — rules only"}</dd>
    </dl>
    <p class="muted section-hint">Briefing/quiet hours: edit <code>.env</code> in the repo root and restart <code>ui/server.py</code>. Add <code>OPENROUTER_API_KEY</code> from <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">openrouter.ai/keys</a> for natural-language parsing beyond built-in rules.</p>
  `;

  renderReminders();
  updatePendingBadge();
}

async function loadCleaningPlan() {
  if (!cleaningPlanListEl || !getUserId() || !currentUser.apartment) {
    if (cleaningPlanListEl) {
      cleaningPlanListEl.innerHTML = `<p class="empty">Join an apartment to use the shared cleaning plan.</p>`;
    }
    return;
  }
  try {
    const data = await api(apiPath("/api/cleaning-plan"));
    state.cleaningPlan = data;
    renderCleaningPlan();
    setConnected(true);
  } catch (e) {
    cleaningPlanListEl.innerHTML = `<p class="empty">Couldn't load cleaning plan.</p>`;
    setConnected(false);
  }
}

function renderCleaningPlan() {
  if (!cleaningPlanListEl || !state.cleaningPlan) return;
  const chores = state.cleaningPlan.chores || [];
  if (chores.length === 0) {
    cleaningPlanListEl.innerHTML = `<p class="empty">No chores yet — add one above.</p>`;
    return;
  }
  const memberOptions = (state.profiles || [])
    .filter((p) => p.apartment === currentUser.apartment)
    .map(
      (p) =>
        `<option value="${p.id}">${escapeHtml(p.display_name)}</option>`
    )
    .join("");
  cleaningPlanListEl.innerHTML = chores
    .map((c) => {
      const status = c.overdue
        ? `<span class="cleaning-overdue">Due — ${c.days_since ?? "?"} days since last</span>`
        : c.last_done_by
          ? `<span class="muted">Last: ${escapeHtml(c.last_done_by)}${c.days_since != null ? ` · ${c.days_since}d ago` : ""}</span>`
          : `<span class="muted">Not done yet</span>`;
      return `
      <article class="cleaning-chore-card${c.overdue ? " is-overdue" : ""}">
        <div class="cleaning-chore-main">
          <h3>${escapeHtml(c.label)}</h3>
          <p class="muted">Every ${c.interval_days} day${c.interval_days === 1 ? "" : "s"}</p>
          ${status}
        </div>
        <div class="cleaning-chore-actions">
          <label class="cleaning-assign">
            <span class="sr-only">Assign to</span>
            <select data-chore="${c.id}" class="cleaning-assign-select">
              <option value="">Unassigned</option>
              ${memberOptions}
            </select>
          </label>
          <button type="button" class="btn primary cleaning-done-btn" data-id="${c.id}">Done</button>
        </div>
      </article>`;
    })
    .join("");
  chores.forEach((c) => {
    const sel = cleaningPlanListEl.querySelector(`select[data-chore="${c.id}"]`);
    if (sel && c.assigned_to_user_id) sel.value = String(c.assigned_to_user_id);
  });
  cleaningPlanListEl.querySelectorAll(".cleaning-done-btn").forEach((btn) => {
    btn.addEventListener("click", () => markCleaningDone(Number(btn.dataset.id)));
  });
  cleaningPlanListEl.querySelectorAll(".cleaning-assign-select").forEach((sel) => {
    sel.addEventListener("change", () =>
      assignCleaningChore(Number(sel.dataset.chore), sel.value ? Number(sel.value) : null)
    );
  });
}

async function markCleaningDone(choreId) {
  try {
    const data = await api(apiPath("/api/cleaning-plan/done"), { chore_id: choreId });
    state.cleaningPlan = data;
    renderCleaningPlan();
    toast("Marked done.");
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not mark done.");
    setConnected(false);
  }
}

async function assignCleaningChore(choreId, userId) {
  try {
    const data = await api(apiPath("/api/cleaning-plan/assign"), {
      chore_id: choreId,
      assigned_to_user_id: userId,
    });
    state.cleaningPlan = data;
    renderCleaningPlan();
    setConnected(true);
  } catch (e) {
    toast(e.message || "Could not assign.");
    setConnected(false);
  }
}

openCleaningPlanBtn?.addEventListener("click", () => switchView("household-cleaning"));

cleaningChoreForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const label = document.getElementById("cleaning-chore-label")?.value.trim();
  const days = Number(document.getElementById("cleaning-chore-days")?.value || 7);
  if (!label) return;
  try {
    const data = await api(apiPath("/api/cleaning-plan/add"), {
      label,
      interval_days: days,
    });
    state.cleaningPlan = data;
    renderCleaningPlan();
    cleaningChoreForm.reset();
    document.getElementById("cleaning-chore-days").value = "7";
    toast("Chore added.");
    setConnected(true);
  } catch (err) {
    toast(err.message || "Could not add chore.");
    setConnected(false);
  }
});

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
    const data = await api("/api/reminders/remove", { id, user_id: getUserId() });
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
    const data = await api("/api/reminders/cancel-timer", { id, user_id: getUserId() });
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
function scrollChatToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
    const last = messagesEl.lastElementChild;
    if (last) {
      last.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  });
}

function appendBubble(text, who) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${isCurrentUser(who) ? "user" : "domus"}`;
  const label = document.createElement("span");
  label.className = "who";
  label.textContent = who;
  bubble.appendChild(label);
  bubble.appendChild(document.createTextNode(text));
  messagesEl.appendChild(bubble);
  return bubble;
}

function addBubble(text, who) {
  const bubble = appendBubble(text, who);
  syncChatEmptyState();
  scrollChatToBottom();
  return bubble;
}

function addThinkingBubble() {
  const bubble = document.createElement("div");
  bubble.className = "bubble domus thinking";
  bubble.setAttribute("aria-live", "polite");
  const label = document.createElement("span");
  label.className = "who";
  label.textContent = "Domus";
  bubble.appendChild(label);
  bubble.appendChild(document.createTextNode("Thinking…"));
  messagesEl.appendChild(bubble);
  syncChatEmptyState();
  scrollChatToBottom();
  return bubble;
}

async function sendMessage(text) {
  if (!getUserId()) {
    openProfilePicker({ required: true });
    return;
  }
  if (composer.dataset.sending === "1") return;
  composer.dataset.sending = "1";
  const sendBtn = composer.querySelector('button[type="submit"]');
  if (sendBtn) sendBtn.disabled = true;
  addBubble(text, getDisplayName());
  const thinking = addThinkingBubble();
  try {
    const data = await api("/api/message", {
      text,
      user: getDisplayName(),
      user_id: getUserId(),
    });
    thinking.remove();
    const reply = (data.reply || "").trim();
    if (reply) {
      addBubble(reply, "Domus");
    } else {
      addBubble("I heard you, but I don't have a reply right now. Try again in a moment.", "Domus");
    }
    if (data.todos) {
      applyTodosData(data);
      renderTodos();
    }
    if (data.reminders) {
      applyReminders(data.reminders);
      if (state.householdLoaded) renderReminders();
    }
    loadBriefing();
    setConnected(true);
  } catch (e) {
    thinking.remove();
    addBubble(`I couldn't reach Domus. ${e.message || "Check that the server is running."}`, "Domus");
    setConnected(false);
  } finally {
    composer.dataset.sending = "0";
    if (sendBtn) sendBtn.disabled = false;
    input.focus();
  }
}

async function addTodo(name, category, options = {}) {
  if (!getUserId()) {
    openProfilePicker({ required: true });
    return;
  }
  const body = {
    name,
    category,
    user: getDisplayName(),
    user_id: getUserId(),
  };
  if (options.dueDate) body.due_date = options.dueDate;
  if (options.assignedToUserId) body.assigned_to_user_id = options.assignedToUserId;
  try {
    const data = await api("/api/todos/add", body);
    applyTodosData(data);
    renderTodos();
    loadBriefing();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

async function adjustQuantity(id, delta) {
  try {
    const data = await api("/api/todos/quantity", {
      id,
      delta,
      user_id: getUserId(),
    });
    applyTodosData(data);
    renderTodos();
    loadBriefing();
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

function recordCheckedOff(item) {
  const qty = item.quantity && item.quantity > 1 ? `${item.quantity}× ` : "";
  const label = `${qty}${item.name}`;
  state.checkedOff.unshift({ id: item.id, label, item: { ...item } });
  if (state.checkedOff.length > CHECKED_OFF_MAX) {
    state.checkedOff.length = CHECKED_OFF_MAX;
  }
}

async function undoCheckOff(entry) {
  try {
    const data = await api("/api/todos/toggle", {
      id: entry.id,
      done: false,
      user_id: getUserId(),
    });
    applyTodosData(data);
    state.checkedOff = state.checkedOff.filter((e) => e.id !== entry.id);
    renderTodos();
    loadBriefing();
    toast(`Restored “${entry.item.name}”.`);
    setConnected(true);
  } catch (e) {
    setConnected(false);
  }
}

function handleQuickAction(action) {
  if (!getUserId()) {
    openProfilePicker({ required: true });
    return;
  }
  if (action === "add-milk") {
    addTodo("milk", "shopping");
    toast("Added milk to your list.");
    return;
  }
  if (action === "briefing") {
    loadBriefing();
    briefingCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    sendMessage("what's on today?");
    return;
  }
  if (action === "plan-dinner") {
    sendMessage("what should I eat for dinner?");
  }
}

async function checkOff(el, itemOrId) {
  const item =
    typeof itemOrId === "object"
      ? itemOrId
      : [...state.shopping, ...state.taskItems].find((t) => t.id === itemOrId);
  const id = typeof itemOrId === "object" ? itemOrId.id : itemOrId;
  el.classList.add("checking");
  try {
    const data = await api("/api/todos/toggle", { id, done: true, user_id: getUserId() });
    if (item) {
      recordCheckedOff(item);
      const entry = state.checkedOff[0];
      toastUndo(`Checked off “${item.name}”.`, () => undoCheckOff(entry));
    }
    setTimeout(() => {
      applyTodosData(data);
      renderTodos();
      loadBriefing();
    }, 260);
  } catch (e) {
    el.classList.remove("checking");
    setConnected(false);
  }
}

async function removeItem(el, id) {
  el.classList.add("checking");
  try {
    const data = await api("/api/todos/remove", { id, user_id: getUserId() });
    setTimeout(() => {
      applyTodosData(data);
      renderTodos();
      loadBriefing();
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
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.style.opacity = "1";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.style.opacity = "0"), 3200);
}

function toastUndo(text, onUndo) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.innerHTML = `<span>${escapeHtml(text)}</span> <button type="button" class="toast-undo">Undo</button>`;
  el.style.opacity = "1";
  clearTimeout(toastTimer);
  el.querySelector(".toast-undo")?.addEventListener("click", () => {
    onUndo();
    el.style.opacity = "0";
  });
  toastTimer = setTimeout(() => (el.style.opacity = "0"), 5000);
}

function setConnected(ok) {
  connectionEl.textContent = ok ? "connected" : "offline";
  connectionEl.classList.toggle("ok", ok);
}

// ---- form wiring ----------------------------------------------------------
async function syncLoginMembers() {
  if (!profileLoginMember || !profileLoginInvite) return;
  const token = parseInviteToken(profileLoginInvite.value);
  if (!token) {
    profileLoginMember.innerHTML = `<option value="">Enter invite link first…</option>`;
    profileLoginMember.disabled = true;
    return;
  }
  profileLoginMember.disabled = true;
  profileLoginMember.innerHTML = `<option value="">Loading members…</option>`;
  try {
    const data = await api(`/api/auth/invite?token=${encodeURIComponent(token)}`);
    const members = data.members || [];
    if (!members.length) {
      profileLoginMember.innerHTML = `<option value="">No members found</option>`;
      return;
    }
    profileLoginMember.innerHTML = members
      .map((m) => `<option value="${m.user_id}">${escapeHtml(m.display_name)}</option>`)
      .join("");
    profileLoginMember.disabled = false;
  } catch (_) {
    profileLoginMember.innerHTML = `<option value="">Invalid invite link</option>`;
  }
}

function readJoinAuth() {
  const password = profileJoinPassword?.value.trim() || "";
  const otp = profileJoinOtp?.value.trim() || "";
  return { password, otp };
}

function readLoginAuth() {
  const password = profileLoginPassword?.value.trim() || "";
  const otp = profileLoginOtp?.value.trim() || "";
  return { password, otp };
}

if (profileChip) {
  profileChip.addEventListener("click", () => openProfilePicker({ required: false }));
}

authSignOutBtn?.addEventListener("click", () => {
  if (window.confirm("Sign out on this device? You can log in again from the welcome screen.")) {
    signOutOnDevice();
  }
});

if (authSetupToggle && authSetupBody) {
  authSetupToggle.addEventListener("click", () => {
    const expanded = authSetupToggle.getAttribute("aria-expanded") === "true";
    authSetupToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
    updateAuthSetupLayout();
  });
}

authTabs.forEach((tab) => {
  tab.addEventListener("click", () => setAuthFormMode(tab.dataset.mode || "create"));
});

if (profilePickList) {
  profilePickList.addEventListener("click", (e) => {
    const btn = e.target.closest(".profile-pick-btn");
    if (!btn?.dataset.token) return;
    selectEntity(btn.dataset.token);
  });
}

let loginMemberTimer;
profileLoginInvite?.addEventListener("input", () => {
  clearTimeout(loginMemberTimer);
  loginMemberTimer = setTimeout(syncLoginMembers, 350);
});

profileInviteToken?.addEventListener("blur", () => {
  const parsed = parseInviteToken(profileInviteToken.value);
  if (parsed && profileInviteToken.value !== parsed) profileInviteToken.value = parsed;
});

profileLoginInvite?.addEventListener("blur", () => {
  const parsed = parseInviteToken(profileLoginInvite.value);
  if (parsed && profileLoginInvite.value !== parsed) profileLoginInvite.value = parsed;
  syncLoginMembers();
});

if (profileNewForm) {
  profileNewForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const mode = authFormMode;
    try {
      if (mode === "join") {
        const name = profileJoinName?.value.trim() || "";
        const inviteToken = parseInviteToken(profileInviteToken?.value || "");
        const { password, otp } = readJoinAuth();
        if (!name) {
          toast("Your name is required.");
          return;
        }
        if (!inviteToken) {
          toast("Paste the invite link or code.");
          return;
        }
        if (!password && !otp) {
          toast("Enter the household password or a one-time code.");
          return;
        }
        await joinHousehold(name, inviteToken, { password, otp });
        profileJoinName.value = "";
        profileInviteToken.value = "";
        if (profileJoinPassword) profileJoinPassword.value = "";
        if (profileJoinOtp) profileJoinOtp.value = "";
      } else if (mode === "login") {
        const inviteToken = parseInviteToken(profileLoginInvite?.value || "");
        const userId = Number(profileLoginMember?.value);
        const { password, otp } = readLoginAuth();
        if (!inviteToken || !Number.isFinite(userId)) {
          toast("Pick your name after entering the invite link.");
          return;
        }
        if (!password && !otp) {
          toast("Enter the household password or a one-time code.");
          return;
        }
        await loginExistingEntity(userId, inviteToken, { password, otp });
        if (profileLoginInvite) profileLoginInvite.value = "";
        if (profileLoginPassword) profileLoginPassword.value = "";
        if (profileLoginOtp) profileLoginOtp.value = "";
      } else {
        const name = profileNewName?.value.trim() || "";
        const householdName = profileNewApartment?.value.trim() || "";
        const password = profileCreatePassword?.value.trim() || "";
        if (!name || !householdName) {
          toast("Name and household name are required.");
          return;
        }
        if (password.length < 4) {
          toast("Choose a household password (min 4 characters).");
          return;
        }
        await createHouseholdAccount(name, householdName, password);
        profileNewName.value = "";
        profileNewApartment.value = "";
        if (profileCreatePassword) profileCreatePassword.value = "";
      }
      setConnected(true);
    } catch (err) {
      toast(err.message || "Could not continue.");
      setConnected(false);
    }
  });
}

setAuthFormMode("create");

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendMessage(text);
});

if (quickActionsEl) {
  quickActionsEl.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    handleQuickAction(btn.dataset.action);
  });
}

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
  const dueDate = taskDueInput?.value || null;
  const assigneeId = taskAssignee?.value ? Number(taskAssignee.value) : null;
  taskInput.value = "";
  if (taskDueInput) taskDueInput.value = "";
  addTodo(name, taskCategory.value, {
    dueDate,
    assignedToUserId: Number.isFinite(assigneeId) ? assigneeId : null,
  });
});

if (taskFiltersEl) {
  taskFiltersEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".task-filter-chip");
    if (!btn) return;
    const val = btn.dataset.category;
    state.taskCategoryFilter = val === "" ? null : val;
    renderTodos();
  });
}

newRecipeBtn.addEventListener("click", openNewRecipeForm);

modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) closeModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !modalOverlay.hidden) closeModal();
});

// ---- boot -----------------------------------------------------------------
async function boot() {
  await initProfiles();
  loadRecipes();
  initConverter();
  updateHomeContext();
  if (getUserId()) {
    await reloadSessionData();
  }
}

boot();
