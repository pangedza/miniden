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

window.apiGet = apiGet;
window.apiPost = apiPost;
window.getCurrentUser = getCurrentUser;
window.API_BASE = API_BASE;
