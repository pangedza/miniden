const API_BASE = "/api";
const TELEGRAM_AUTH_PATH = "/auth/telegram";
const TELEGRAM_WEBAPP_AUTH_PATH = "/auth/telegram_webapp";
const AUTH_SESSION_PATH = "/auth/session";
const TELEGRAM_BOT_USERNAME = "BotMiniden_bot";

window._telegramWebAppAuthState = window._telegramWebAppAuthState || {
  status: "idle",
  profile: null,
  error: null,
};

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
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    console.error("Failed to parse JSON", error, text);
    const parseError = new Error("Ошибка сервера: неверный формат ответа");
    parseError.status = res.status;
    parseError.data = { raw: text };
    throw parseError;
  }

  if (!res.ok) {
    const message = (data && (data.detail || data.message)) || text || "Ошибка API";
    const error = new Error(message);
    error.status = res.status;
    error.data = data;
    throw error;
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

async function getTelegramInitDataWithRetry(maxAttempts = 20, delayMs = 100) {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      if (window.Telegram && window.Telegram.WebApp) {
        const raw = window.Telegram.WebApp.initData || "";
        if (raw) return raw;
      }

      const searchParams = new URLSearchParams(window.location.search || "");
      const queryInitData = searchParams.get("tgWebAppData");
      if (queryInitData) {
        return queryInitData;
      }
    } catch (error) {
      console.warn("Failed to read Telegram initData", error);
    }

    if (attempt < maxAttempts) {
      await wait(delayMs);
    }
  }

  return null;
}

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

async function telegramWebAppAutoLogin() {
  if (!isTelegramWebApp || !window.Telegram || !window.Telegram.WebApp) {
    console.warn("Not in Telegram WebApp environment");
    return { ok: false, reason: "not_webapp" };
  }

  const initData = await getTelegramInitDataWithRetry();
  if (!initData) {
    console.warn("Telegram WebApp initData is empty");
    return { ok: false, reason: "empty_init_data" };
  }

  try {
    const response = await fetch("/api/auth/telegram_webapp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
      credentials: "include",
    });

    if (!response.ok) {
      console.error("WebApp auth failed with status", response.status);
      return { ok: false, reason: "http_" + response.status };
    }

    const data = await response.json();
    if (data.status === "ok") {
      return { ok: true, user: data.user };
    }

    console.error("WebApp auth error payload", data);
    return { ok: false, reason: data.error || "unknown" };
  } catch (e) {
    console.error("WebApp auth exception", e);
    return { ok: false, reason: "exception" };
  }
}

async function ensureTelegramWebAppAuth() {
  if (!isTelegramWebApp || !window.Telegram || !window.Telegram.WebApp) {
    return { status: "skipped" };
  }

  if (window._telegramWebAppAuthPromise) {
    return window._telegramWebAppAuthPromise;
  }

  window._telegramWebAppAuthState = {
    status: "pending",
    profile: null,
    error: null,
  };

  const authPromise = (async () => {
    try {
      const sessionRes = await fetch(buildUrl(AUTH_SESSION_PATH));
      if (sessionRes.ok) {
        const sessionData = await sessionRes.json();
        if (sessionData?.authenticated && sessionData.user) {
          window._currentProfile = sessionData.user;
          window._currentUser = sessionData.user;
          window._currentProfileLoaded = true;
          window._telegramWebAppAuthState = {
            status: "authorized",
            profile: sessionData.user,
            error: null,
          };
          return window._telegramWebAppAuthState;
        }
      }
    } catch (error) {
      console.warn("Profile check failed", error);
    }

    const initData = await getTelegramInitDataWithRetry();
    if (!initData) {
      window._telegramWebAppAuthState = {
        status: "no_init_data",
        profile: null,
        error: null,
      };
      return window._telegramWebAppAuthState;
    }

    const authResult = await telegramWebAppAutoLogin();
    if (!authResult.ok) {
      window._telegramWebAppAuthState = {
        status: "auth_failed",
        profile: null,
        error: authResult.reason,
      };
      return window._telegramWebAppAuthState;
    }

    try {
      const profile = await fetchAuthSession();
      if (profile) {
        window._currentProfile = profile;
        window._currentProfileLoaded = true;
        window._currentUser = profile;
        window._telegramWebAppAuthState = {
          status: "authorized",
          profile,
          error: null,
        };
        return window._telegramWebAppAuthState;
      }
    } catch (error) {
      console.warn("Failed to load profile after Telegram auth", error);
    }

    window._telegramWebAppAuthState = {
      status: "authorized",
      profile: window._currentProfile || null,
      error: null,
    };
    return window._telegramWebAppAuthState;
  })();

  window._telegramWebAppAuthPromise = authPromise;
  return authPromise;
}

if (isTelegramWebApp) {
  ensureTelegramWebAppAuth();
}

async function getCurrentUser(options = {}) {
  if (window._currentUser && !options.forceRefresh) {
    return window._currentUser;
  }

  const includeNotes = Boolean(options.includeNotes);

  if (isTelegramWebApp) {
    await ensureTelegramWebAppAuth();
    if (window._currentUser && !options.forceRefresh) {
      return window._currentUser;
    }
  }

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

  if (isTelegramWebApp) {
    await ensureTelegramWebAppAuth();
    if (window._currentProfile && !options.forceRefresh) {
      window._currentProfileLoaded = true;
      return window._currentProfile;
    }
  }

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
window.ensureTelegramWebAppAuth = ensureTelegramWebAppAuth;
window.getTelegramWebAppAuthState = () => window._telegramWebAppAuthState;
window.processTelegramAuthFromUrl = processTelegramAuthFromUrl;
window.startTelegramOAuthFlow = startTelegramOAuthFlow;
window.isTelegramWebApp = isTelegramWebApp;
window.telegramWebAppAutoLogin = telegramWebAppAutoLogin;
window.getTelegramInitDataWithRetry = getTelegramInitDataWithRetry;
