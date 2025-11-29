const AUTH_TOKEN_STORAGE_KEY = 'tg_auth_token';
const API_BASE = '/api';
const BOT_LINK = 'https://t.me/BotMiniden_bot';

function saveAuthToken(token) {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

function getSavedAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

function clearSavedAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

async function startTelegramAuth() {
  const res = await fetch(`${API_BASE}/auth/create-token`, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || 'Не удалось получить токен авторизации');
  }
  const data = await res.json();
  const token = data?.token;
  if (!token) {
    throw new Error('Пустой токен авторизации');
  }
  saveAuthToken(token);
  window.location.href = `${BOT_LINK}?start=auth_${token}`;
}

function startAuthPolling(onSuccess, onWaiting, onError) {
  const token = getSavedAuthToken();
  if (!token) return null;

  const intervalId = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/check?token=${encodeURIComponent(token)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (data?.ok) {
        clearInterval(intervalId);
        clearSavedAuthToken();
        onSuccess?.(data);
      } else {
        onWaiting?.();
      }
    } catch (e) {
      clearInterval(intervalId);
      onError?.(e);
    }
  }, 500);

  return intervalId;
}
