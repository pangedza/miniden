const THEME_KEY = 'miniden_theme';
const LEGACY_THEME_KEYS = ['miniden.theme'];
const DEFAULT_THEME = 'lifestyle';
const AVAILABLE_THEMES = ['lifestyle', 'purple', 'dark', 'light', 'cream'];

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

applyTheme(readStoredTheme() || DEFAULT_THEME);
document.addEventListener('DOMContentLoaded', initLayout);
