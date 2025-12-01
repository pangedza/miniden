const API_BASE = "/api";

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
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const message = (data && data.detail) || text || "Ошибка API";
    const error = new Error(message);
    error.status = res.status;
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

async function getCurrentUser(options = {}) {
  if (window._currentUser && !options.forceRefresh) {
    return window._currentUser;
  }

  const includeNotes = Boolean(options.includeNotes);
  const telegram = window.Telegram?.WebApp;
  const initData = telegram?.initData;

  try {
    if (initData) {
      const profile = await apiPost("/auth/telegram", { initData, include_notes: includeNotes });
      window._currentUser = profile;
      return profile;
    }

    const res = await fetch(buildUrl("/auth/session", includeNotes ? { include_notes: true } : undefined));
    if (res.status === 401 || res.status === 404) {
      return null;
    }
    const data = await handleResponse(res);
    window._currentUser = data;
    return data;
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

  window._currentProfileLoaded = true;

  const includeNotes = Boolean(options.includeNotes);
  const telegram = window.Telegram?.WebApp;
  const initData = telegram?.initData;

  try {
    if (initData) {
      const profile = await apiPost("/auth/telegram", { initData, include_notes: includeNotes });
      window._currentProfile = profile;
      return profile;
    }

    const res = await fetch(buildUrl("/auth/session", includeNotes ? { include_notes: true } : undefined));
    if (!res.ok) {
      window._currentProfile = null;
      return null;
    }
    const data = await handleResponse(res);
    window._currentProfile = data;
    return data;
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

window.apiGet = apiGet;
window.apiPost = apiPost;
window.getCurrentUser = getCurrentUser;
window.getCurrentUserProfile = getCurrentUserProfile;
window.loadGuestCart = loadGuestCart;
window.saveGuestCart = saveGuestCart;
window.addToGuestCart = addToGuestCart;
window.clearGuestCart = clearGuestCart;
window.syncGuestCartToServer = syncGuestCartToServer;
window.API_BASE = API_BASE;
