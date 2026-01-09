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

export function fetchMenu(type = null) {
  return request('/api/public/menu/tree', { type });
}

export function fetchSiteSettings() {
  return request('/api/public/site-settings');
}

export function fetchCategories() {
  return request('/api/public/menu/categories');
}

export function fetchCategoryItems(category, type = null) {
  return request('/api/public/menu/items', { category_slug: category, type });
}

export function fetchBlocks(page) {
  return request('/api/public/blocks', { page });
}

export function fetchCategoryDetails(slug, type = null) {
  return request(`/api/public/menu/category/${slug}`, { type });
}

export function fetchItemById(itemId) {
  return request(`/api/public/item/${itemId}`);
}
