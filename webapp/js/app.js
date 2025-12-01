const THEME_KEY = 'miniden.theme';
const DEFAULT_THEME = 'purple';

function applyTheme(theme) {
  const value = theme || DEFAULT_THEME;
  document.body.dataset.theme = value;
}

function initThemeSwitcher() {
  const select = document.getElementById('theme-select');
  if (!select) return;

  const saved = localStorage.getItem(THEME_KEY) || DEFAULT_THEME;
  applyTheme(saved);
  select.value = saved;

  select.addEventListener('change', () => {
    const value = select.value || DEFAULT_THEME;
    applyTheme(value);
    localStorage.setItem(THEME_KEY, value);
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

applyTheme(localStorage.getItem(THEME_KEY) || DEFAULT_THEME);
document.addEventListener('DOMContentLoaded', initLayout);
