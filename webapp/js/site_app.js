import {
  fetchCategory,
  fetchHome,
  fetchMasterclass,
  fetchMenu,
  fetchProduct,
} from './site_api.js';

const views = {
  home: document.getElementById('view-home'),
  category: document.getElementById('view-category'),
  product: document.getElementById('view-product'),
  masterclass: document.getElementById('view-masterclass'),
  notFound: document.getElementById('view-not-found'),
};

const navMenu = document.getElementById('nav-menu');
const navLinks = document.getElementById('nav-links');
const sidebarOverlay = document.querySelector('.app-sidebar-overlay');
const themeSelect = document.getElementById('theme-select');

function hideAllViews() {
  Object.values(views).forEach((view) => {
    if (view) view.setAttribute('hidden', '');
  });
}

function showView(name) {
  hideAllViews();
  const target = views[name];
  if (target) target.removeAttribute('hidden');
}

function formatPrice(value) {
  const number = Number(value) || 0;
  if (number === 0) return 'Бесплатно';
  return `${number.toLocaleString('ru-RU')} ₽`;
}

function buildCategoryCard(category) {
  const card = document.createElement('article');
  card.className = 'catalog-card hover-lift';
  const body = document.createElement('div');
  body.className = 'catalog-card-body';

  const title = document.createElement('h3');
  title.className = 'catalog-card-title';
  title.textContent = category?.title || 'Категория';

  const subtitle = document.createElement('p');
  subtitle.className = 'catalog-card-description';
  subtitle.textContent = category?.type === 'course' ? 'Мастер-классы' : 'Товары';

  const action = document.createElement('a');
  action.className = 'btn secondary';
  action.href = category?.url || '/';
  action.textContent = 'Открыть';
  action.setAttribute('data-router-link', '');

  body.append(title, subtitle, action);
  card.append(body);
  return card;
}

function buildItemCard(item) {
  const card = document.createElement('article');
  card.className = 'catalog-card';

  const imageWrapper = document.createElement('div');
  imageWrapper.className = 'catalog-card-image';
  if (item?.image_url) {
    const img = document.createElement('img');
    img.src = item.image_url;
    img.alt = item.title || 'Элемент витрины';
    imageWrapper.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'catalog-card-meta';
    placeholder.textContent = 'Изображение появится позже';
    imageWrapper.appendChild(placeholder);
  }

  const body = document.createElement('div');
  body.className = 'catalog-card-body';

  const meta = document.createElement('div');
  meta.className = 'catalog-card-meta';
  meta.textContent = item?.category_title || '';

  const title = document.createElement('h3');
  title.className = 'catalog-card-title';
  title.textContent = item?.title || 'Элемент';

  const description = document.createElement('p');
  description.className = 'catalog-card-description';
  description.textContent = item?.short_text || item?.description || '';

  const footer = document.createElement('div');
  footer.className = 'product-card__actions';

  const price = document.createElement('div');
  price.className = 'price';
  price.textContent = formatPrice(item?.price);

  const more = document.createElement('a');
  more.className = 'btn secondary';
  more.href = item?.url || '#';
  more.textContent = 'Подробнее';
  more.setAttribute('data-router-link', '');

  footer.append(price, more);
  body.append(meta, title, description, footer);
  card.append(imageWrapper, body);
  return card;
}

function renderMenu(menu) {
  if (!navMenu) return;
  navMenu.innerHTML = '';
  if (!menu?.items?.length) {
    const muted = document.createElement('span');
    muted.className = 'muted';
    muted.textContent = 'Категорий нет';
    navMenu.appendChild(muted);
    return;
  }

  menu.items.forEach((item) => {
    const link = document.createElement('a');
    link.href = item.url || `/c/${encodeURIComponent(item.slug)}`;
    link.textContent = item.title || 'Категория';
    link.dataset.routerLink = '';
    navMenu.appendChild(link);
  });
}

function renderHome(data) {
  const categoryGrid = document.getElementById('home-category-grid');
  const categoryEmpty = document.getElementById('home-category-empty');
  const featuredGrid = document.getElementById('home-featured-grid');
  const featuredEmpty = document.getElementById('home-featured-empty');

  categoryGrid.innerHTML = '';
  featuredGrid.innerHTML = '';

  const categories = [...(data?.product_categories || []), ...(data?.course_categories || [])];
  if (!categories.length) {
    categoryEmpty?.removeAttribute('style');
  } else {
    categoryEmpty?.setAttribute('style', 'display:none;');
    categories.forEach((category) => categoryGrid.appendChild(buildCategoryCard(category)));
  }

  const featured = [...(data?.featured_products || []), ...(data?.featured_masterclasses || [])];
  if (!featured.length) {
    featuredEmpty?.removeAttribute('style');
  } else {
    featuredEmpty?.setAttribute('style', 'display:none;');
    featured.forEach((item) => featuredGrid.appendChild(buildItemCard(item)));
  }
}

function renderBreadcrumbs(target, parts) {
  if (!target) return;
  target.innerHTML = '';
  parts.forEach((part, index) => {
    if (index > 0) {
      const divider = document.createElement('span');
      divider.textContent = ' / ';
      target.appendChild(divider);
    }
    if (part.href) {
      const link = document.createElement('a');
      link.href = part.href;
      link.textContent = part.title;
      link.dataset.routerLink = '';
      target.appendChild(link);
    } else {
      const span = document.createElement('span');
      span.textContent = part.title;
      target.appendChild(span);
    }
  });
}

function renderCategory(category) {
  const itemsWrap = document.getElementById('category-items');
  const empty = document.getElementById('category-empty');
  const title = document.getElementById('category-title');
  const meta = document.getElementById('category-meta');
  const typeTag = document.getElementById('category-type');
  const breadcrumbs = document.getElementById('category-breadcrumbs');

  title.textContent = category?.category?.title || 'Категория';
  meta.textContent = `Тип: ${category?.category?.type || 'не указан'}`;
  typeTag.textContent = category?.category?.type === 'course' ? 'Мастер-классы' : 'Товары';

  renderBreadcrumbs(breadcrumbs, [
    { title: 'Главная', href: '/' },
    { title: category?.category?.title || 'Категория' },
  ]);

  itemsWrap.innerHTML = '';
  const items = category?.items || [];
  if (!items.length) {
    empty?.removeAttribute('style');
  } else {
    empty?.setAttribute('style', 'display:none;');
    items.forEach((item) => itemsWrap.appendChild(buildItemCard(item)));
  }
}

function renderProduct(item, targetPrefix = 'product') {
  const breadcrumbs = document.getElementById(`${targetPrefix}-breadcrumbs`);
  const image = document.getElementById(`${targetPrefix}-image`);
  const title = document.getElementById(`${targetPrefix}-title`);
  const price = document.getElementById(`${targetPrefix}-price`);
  const description = document.getElementById(`${targetPrefix}-description`);
  const category = document.getElementById(`${targetPrefix}-category`);

  renderBreadcrumbs(breadcrumbs, [
    { title: 'Главная', href: '/' },
    item?.category_slug ? { title: item.category_title || 'Категория', href: `/c/${item.category_slug}` } : null,
    { title: item?.title || 'Элемент' },
  ].filter(Boolean));

  if (image) {
    if (item?.image_url) {
      image.src = item.image_url;
      image.removeAttribute('hidden');
    } else {
      image.setAttribute('hidden', '');
    }
  }

  if (title) title.textContent = item?.title || 'Элемент';
  if (price) price.textContent = formatPrice(item?.price);
  if (description) description.textContent = item?.description || item?.short_text || '';
  if (category) category.textContent = item?.category_title || '';
}

function parseRoute() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  if (path === '/' || path === '/index.html') return { view: 'home' };

  const categoryMatch = path.match(/^\/(c|category)\/([^/]+)$/);
  if (categoryMatch) {
    return { view: 'category', slug: decodeURIComponent(categoryMatch[2]) };
  }

  const productMatch = path.match(/^\/(p|product)\/([^/]+)$/);
  if (productMatch) {
    return { view: 'product', slug: decodeURIComponent(productMatch[2]) };
  }

  const masterclassMatch = path.match(/^\/(m|course)\/([^/]+)$/);
  if (masterclassMatch) {
    return { view: 'masterclass', slug: decodeURIComponent(masterclassMatch[2]) };
  }

  return { view: 'notFound' };
}

async function handleRoute() {
  try {
    const route = parseRoute();
    if (route.view === 'home') {
      const homeData = await fetchHome();
      renderHome(homeData);
      showView('home');
      return;
    }

    if (route.view === 'category' && route.slug) {
      const category = await fetchCategory(route.slug);
      renderCategory(category);
      showView('category');
      return;
    }

    if (route.view === 'product' && route.slug) {
      const product = await fetchProduct(route.slug);
      renderProduct(product, 'product');
      showView('product');
      return;
    }

    if (route.view === 'masterclass' && route.slug) {
      const masterclass = await fetchMasterclass(route.slug);
      renderProduct(masterclass, 'masterclass');
      showView('masterclass');
      return;
    }

    showView('notFound');
  } catch (error) {
    console.error('Routing failed', error);
    showView('notFound');
  }
}

function navigate(url) {
  window.history.pushState({}, '', url);
  closeSidebar();
  handleRoute();
}

function bindRouterLinks() {
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-router-link]');
    if (link && link.href.startsWith(window.location.origin)) {
      event.preventDefault();
      navigate(link.getAttribute('href'));
    }
  });
}

function openSidebar() {
  navLinks?.classList.add('open');
  sidebarOverlay?.classList.add('active');
}

function closeSidebar() {
  navLinks?.classList.remove('open');
  sidebarOverlay?.classList.remove('active');
}

function setupMenuToggle() {
  const toggle = document.querySelector('.menu-toggle');
  toggle?.addEventListener('click', openSidebar);
  sidebarOverlay?.addEventListener('click', closeSidebar);
}

function loadTheme() {
  const saved = localStorage.getItem('site-theme');
  if (saved) {
    document.body.dataset.theme = saved;
    if (themeSelect) themeSelect.value = saved;
  }
}

function setupThemeSwitcher() {
  loadTheme();
  themeSelect?.addEventListener('change', (event) => {
    const value = event.target.value;
    document.body.dataset.theme = value;
    localStorage.setItem('site-theme', value);
  });
}

async function bootstrap() {
  setupThemeSwitcher();
  setupMenuToggle();
  bindRouterLinks();

  try {
    const menu = await fetchMenu('product');
    renderMenu(menu);
  } catch (error) {
    console.error('Failed to load menu', error);
  }

  window.addEventListener('popstate', handleRoute);
  handleRoute();
}

bootstrap();
