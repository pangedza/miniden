export async function request(path, params = null) {
  const url = new URL(path, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });
  }

  url.searchParams.set('_', Date.now().toString());

  const response = await fetch(url.toString(), { cache: 'no-store' });
  const text = await response.text();
  const isJson = text.trim().startsWith('{') || text.trim().startsWith('[');
  const payload = isJson ? JSON.parse(text || '{}') : text;

  if (!response.ok) {
    const message = payload?.detail || payload?.message || response.statusText;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return payload;
}

export async function requestWithStatus(path, params = null) {
  const url = new URL(path, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });
  }

  url.searchParams.set('_', Date.now().toString());

  const response = await fetch(url.toString(), { cache: 'no-store' });
  const status = response.status;
  const statusText = response.statusText || '';
  const text = await response.text();
  const isJson = text.trim().startsWith('{') || text.trim().startsWith('[');
  const payload = isJson ? JSON.parse(text || '{}') : text;

  if (!response.ok) {
    const message = payload?.detail || payload?.message || response.statusText;
    const error = new Error(message);
    error.status = status;
    throw error;
  }

  return { payload, status, statusText, url: url.toString() };
}

export function fetchMenu(type = 'product') {
  return request('/api/site/menu', { type });
}

export function fetchTheme() {
  return request('/api/site/theme');
}

export function fetchPageByKey(pageKey) {
  return request(`/api/site/pages/${encodeURIComponent(pageKey)}`);
}

export function fetchCategories(type = null) {
  return request('/api/site/categories', { type });
}

export function fetchCategory(slug, type = null) {
  return request(`/api/site/categories/${encodeURIComponent(slug)}`, { type });
}

export function fetchProduct(slug) {
  return request(`/api/site/products/${encodeURIComponent(slug)}`);
}

export function fetchMasterclass(slug) {
  return request(`/api/site/masterclasses/${encodeURIComponent(slug)}`);
}

export function fetchItems(params = {}) {
  return request('/api/site/items', params);
}
