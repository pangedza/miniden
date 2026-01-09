const API_BASE = "/api";
const TELEGRAM_AUTH_PATH = "/auth/telegram";
const AUTH_SESSION_PATH = "/auth/session";
const TELEGRAM_BOT_USERNAME = "BotMiniden_bot";

function buildUrl(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

async function handleResponse(res) {
  if (res.status === 204) return null;
  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const text = await res.text();
  let data = null;

  if (isJson) {
    try {
      data = text ? JSON.parse(text) : null;
    } catch (error) {
      console.error("Failed to parse JSON", error, text);
      const parseError = new Error("Ошибка сервера: неверный формат ответа");
      parseError.status = res.status;
      parseError.data = { raw: text };
      throw parseError;
    }
  }

  if (!res.ok) {
    const message =
      (data && (data.detail || data.message)) ||
      (text && !isJson ? "Сервер временно недоступен" : text) ||
      "Ошибка API";
    const error = new Error(message);
    error.status = res.status;
    error.data = data || { raw: text };
    throw error;
  }

  if (!isJson) {
    return { raw: text };
  }

  return data;
}

async function apiGet(path, params) {
  const res = await fetch(buildUrl(path, params));
  return handleResponse(res);
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse(res);
}

const isTelegramWebApp = !!(window.Telegram && window.Telegram.WebApp);

function normalizeError(message, status) {
  const error = new Error(message);
  if (status) error.status = status;
  return error;
}

function getTelegramAuthQueryFromUrl() {
  const search = window.location.search || "";
  if (!search.includes("hash")) return null;
  const params = new URLSearchParams(search);
  if (!params.has("id") || !params.has("hash")) return null;
  return search.startsWith("?") ? search.slice(1) : search;
}

function clearTelegramAuthParamsFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("id");
  url.searchParams.delete("hash");
  url.searchParams.delete("first_name");
  url.searchParams.delete("last_name");
  url.searchParams.delete("username");
  url.searchParams.delete("photo_url");
  url.searchParams.delete("auth_date");
  url.searchParams.delete("auth_query");
  window.history.replaceState({}, document.title, url.toString());
}

function buildTelegramOAuthUrl() {
  const returnTo = new URL("/api/auth/telegram-login", window.location.origin);

  const url = new URL("https://oauth.telegram.org/auth");
  url.searchParams.set("bot", TELEGRAM_BOT_USERNAME);
  url.searchParams.set("origin", window.location.origin);
  url.searchParams.set("request_access", "write");
  url.searchParams.set("return_to", returnTo.toString());

  return url.toString();
}

async function processTelegramAuthFromUrl() {
  const authQuery = getTelegramAuthQueryFromUrl();
  if (!authQuery) return null;

  try {
    const res = await apiPost(TELEGRAM_AUTH_PATH, { auth_query: authQuery, init_data: null });
    window._currentProfile = null;
    window._currentUser = null;
    window._currentProfileLoaded = false;
    const profile = await fetchAuthSession();
    if (profile) {
      window._currentProfile = profile;
      window._currentUser = profile;
      window._currentProfileLoaded = true;
    }
    return res;
  } finally {
    clearTelegramAuthParamsFromUrl();
  }
}

function startTelegramOAuthFlow() {
  const url = buildTelegramOAuthUrl();
  window.location.href = url;
}

async function fetchAuthSession(includeNotes) {
  const params = includeNotes ? { include_notes: true } : undefined;
  const res = await fetch(buildUrl(AUTH_SESSION_PATH, params));

  if (res.status === 401 || res.status === 404) {
    return null;
  }

  const data = await handleResponse(res);
  if (!data?.authenticated) return null;
  return data.user || null;
}

async function getCurrentUser(options = {}) {
  if (window._currentUser && !options.forceRefresh) {
    return window._currentUser;
  }

  const includeNotes = Boolean(options.includeNotes);

  try {
    const profile = await fetchAuthSession(includeNotes);
    window._currentUser = profile;
    return profile;
  } catch (error) {
    if (error.status === 401 || error.status === 404) {
      return null;
    }
    console.error("Failed to load current user", error);
    throw error;
  }
}

async function getCurrentUserProfile(options = {}) {
  if (options.forceRefresh) {
    window._currentProfile = undefined;
    window._currentProfileLoaded = false;
  }

  if (window._currentProfileLoaded && !options.forceRefresh) {
    return window._currentProfile ?? null;
  }

  const includeNotes = Boolean(options.includeNotes);

  window._currentProfileLoaded = true;

  try {
    const profile = await fetchAuthSession(includeNotes);
    window._currentProfile = profile;
    return profile;
  } catch (error) {
    console.error("Failed to load current user profile", error);
    window._currentProfile = null;
    return null;
  }
}

const GUEST_CART_KEY = "miniden_guest_cart";

function loadGuestCart() {
  try {
    const raw = localStorage.getItem(GUEST_CART_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    return [];
  } catch (e) {
    console.warn("Failed to load guest cart", e);
    return [];
  }
}

function saveGuestCart(items) {
  try {
    localStorage.setItem(GUEST_CART_KEY, JSON.stringify(items || []));
  } catch (e) {
    console.warn("Failed to save guest cart", e);
  }
}

function addToGuestCart(product_id, type, qty = 1) {
  const current = loadGuestCart();
  const existing = current.find((item) => item.product_id === product_id && item.type === type);
  if (existing) {
    existing.qty = (existing.qty || 0) + qty;
  } else {
    current.push({ product_id, type, qty });
  }
  saveGuestCart(current);
}

function clearGuestCart() {
  try {
    localStorage.removeItem(GUEST_CART_KEY);
  } catch (e) {
    console.warn("Failed to clear guest cart", e);
  }
}

async function syncGuestCartToServer(profile) {
  if (!profile?.telegram_id) return;
  const guestItems = loadGuestCart();
  if (!guestItems.length) return;

  for (const item of guestItems) {
    try {
      await apiPost("/cart/add", {
        user_id: profile.telegram_id,
        product_id: item.product_id,
        qty: item.qty || 1,
        type: item.type || "basket",
      });
    } catch (e) {
      console.warn("Failed to sync guest cart item", item, e);
    }
  }

  clearGuestCart();
}

function showToast(message, title = "MiniDeN") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `
      <div class="toast__title">${title}</div>
      <div class="toast__text">${message}</div>
    `;

  container.appendChild(el);

  requestAnimationFrame(() => {
    el.classList.add("toast--visible");
  });

  function hide() {
    el.classList.remove("toast--visible");
    setTimeout(() => el.remove(), 250);
  }

  const timeout = setTimeout(hide, 2500);
  el.addEventListener("click", () => {
    clearTimeout(timeout);
    hide();
  });
}

window.apiGet = apiGet;
window.apiPost = apiPost;
window.getCurrentUser = getCurrentUser;
window.getCurrentUserProfile = getCurrentUserProfile;
window.loadGuestCart = loadGuestCart;
window.saveGuestCart = saveGuestCart;
window.addToGuestCart = addToGuestCart;
window.clearGuestCart = clearGuestCart;
window.syncGuestCartToServer = syncGuestCartToServer;
window.showToast = showToast;
window.API_BASE = API_BASE;
window.processTelegramAuthFromUrl = processTelegramAuthFromUrl;
window.startTelegramOAuthFlow = startTelegramOAuthFlow;
window.isTelegramWebApp = isTelegramWebApp;
window.TELEGRAM_BOT_USERNAME = TELEGRAM_BOT_USERNAME;
