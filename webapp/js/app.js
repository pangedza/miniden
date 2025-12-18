const THEME_KEY = 'miniden_theme';
const LEGACY_THEME_KEYS = ['miniden.theme'];
const DEFAULT_THEME = 'lifestyle';
const AVAILABLE_THEMES = ['lifestyle', 'purple', 'dark', 'light', 'cream'];
const BRANDING_CACHE_KEY = 'miniden_branding';

function withCacheBusting(url, version) {
  if (!url) return url;
  const separator = url.includes('?') ? '&' : '?';
  const safeVersion = Number.isFinite(version) ? Number(version) : 1;
  return `${url}${separator}v=${safeVersion}`;
}

function readStoredTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored) return stored;
  for (const legacyKey of LEGACY_THEME_KEYS) {
    const legacy = localStorage.getItem(legacyKey);
    if (legacy) return legacy;
  }
  return null;
}

function persistTheme(theme) {
  localStorage.setItem(THEME_KEY, theme);
  LEGACY_THEME_KEYS.forEach((key) => localStorage.setItem(key, theme));
}

function ensureThemeOptions(select) {
  if (!select) return;
  const existing = new Set(Array.from(select.options || []).map((opt) => opt.value));
  AVAILABLE_THEMES.forEach((theme) => {
    if (existing.has(theme)) return;
    const option = document.createElement('option');
    option.value = theme;
    option.textContent = theme === 'lifestyle' ? 'Lifestyle' : theme;
    select.appendChild(option);
  });
}

function applyTheme(theme) {
  const value = AVAILABLE_THEMES.includes(theme) ? theme : DEFAULT_THEME;
  document.body.dataset.theme = value;
  document.documentElement.dataset.theme = value;
}

function initThemeSwitcher() {
  const select = document.getElementById('theme-select');
  if (!select) return;

  ensureThemeOptions(select);
  const saved = readStoredTheme() || DEFAULT_THEME;
  const themeToApply = AVAILABLE_THEMES.includes(saved) ? saved : DEFAULT_THEME;
  applyTheme(themeToApply);
  select.value = themeToApply;

  select.addEventListener('change', () => {
    const value = AVAILABLE_THEMES.includes(select.value) ? select.value : DEFAULT_THEME;
    applyTheme(value);
    persistTheme(value);
  });
}

function initSidebar() {
  const sidebar = document.querySelector('.app-sidebar');
  const overlay = document.querySelector('.app-sidebar-overlay');
  const toggle = document.querySelector('.menu-toggle');
  const sidebarLinks = document.querySelectorAll('.app-sidebar a');

  const openSidebar = () => {
    sidebar?.classList.add('app-sidebar--open');
    overlay?.classList.add('is-visible');
  };

  const closeSidebar = () => {
    sidebar?.classList.remove('app-sidebar--open');
    overlay?.classList.remove('is-visible');
  };

  const toggleSidebar = () => {
    if (!sidebar) return;
    if (sidebar.classList.contains('app-sidebar--open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  };

  toggle?.addEventListener('click', toggleSidebar);
  overlay?.addEventListener('click', closeSidebar);
  sidebarLinks.forEach((link) => link.addEventListener('click', closeSidebar));
}

function initLayout() {
  initThemeSwitcher();
  initSidebar();
}

function applyFavicon(branding) {
  const faviconLink =
    document.getElementById('site-favicon') || document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
  if (!faviconLink) return;

  const version = branding?.assets_version || 1;
  const href = branding?.favicon_url
    ? withCacheBusting(branding.favicon_url, version)
    : withCacheBusting('/favicon.ico', version);

  faviconLink.setAttribute('href', href);
}

function applyBranding(branding) {
  const version = branding?.assets_version || 1;
  const logoUrl = branding?.logo_url ? withCacheBusting(branding.logo_url, version) : null;
  const siteTitle = (branding?.site_title || '').trim();

  document.querySelectorAll('[data-branding-title]').forEach((el) => {
    const fallback = el.dataset.brandingDefault || el.textContent || 'MiniDeN';
    el.textContent = siteTitle || fallback;
  });

  document.querySelectorAll('[data-branding-logo]').forEach((img) => {
    const block = img.closest('[data-branding-block]');
    if (logoUrl) {
      img.src = logoUrl;
      img.alt = siteTitle || img.alt || 'Логотип';
      img.style.display = 'block';
      block?.classList.add('has-logo');
    } else {
      img.removeAttribute('src');
      img.style.display = 'none';
      block?.classList.remove('has-logo');
    }
  });

  applyFavicon(branding);
}

async function loadBranding(forceRefresh = false) {
  if (window._brandingData && !forceRefresh) {
    applyBranding(window._brandingData);
    return window._brandingData;
  }

  try {
    const cached = localStorage.getItem(BRANDING_CACHE_KEY);
    if (cached && !forceRefresh) {
      const parsed = JSON.parse(cached);
      if (parsed && typeof parsed === 'object') {
        window._brandingData = parsed;
        applyBranding(parsed);
      }
    }
  } catch (error) {
    console.warn('Не удалось прочитать кеш брендинга', error);
  }

  try {
    const res = await fetch('/api/branding');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    window._brandingData = data;
    applyBranding(data);
    try {
      localStorage.setItem(BRANDING_CACHE_KEY, JSON.stringify(data));
    } catch (error) {
      console.warn('Не удалось сохранить брендинг в кеш', error);
    }
    return data;
  } catch (error) {
    console.warn('Не удалось загрузить брендинг', error);
    applyBranding(window._brandingData || { assets_version: 1 });
    return window._brandingData || null;
  }
}

const initialTheme =
  readStoredTheme() || document.documentElement.dataset.theme || document.body.dataset.theme || DEFAULT_THEME;
applyTheme(initialTheme);
window.withCacheBusting = withCacheBusting;
window.applyBranding = applyBranding;
window.loadBranding = loadBranding;

document.addEventListener('DOMContentLoaded', () => {
  initLayout();
  loadBranding();
});
