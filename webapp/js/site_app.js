import { fetchBlocks, fetchMenu, fetchSiteSettings } from './site_api.js';

const views = {
  home: document.getElementById('view-home'),
  category: document.getElementById('view-category'),
  item: document.getElementById('view-product'),
  notFound: document.getElementById('view-not-found'),
};

const navMenu = document.getElementById('nav-menu');
const navLinks = document.getElementById('nav-links');
const sidebarOverlay = document.querySelector('.app-sidebar-overlay');
const sidebarClose = document.querySelector('.menu-close');

const heroTitle = document.getElementById('hero-title');
const heroSubtitle = document.getElementById('hero-subtitle');
const heroImage = document.getElementById('hero-image');
const heroSection = document.getElementById('hero-section');

const homeCategories = document.getElementById('home-categories');
const homeBlocks = document.getElementById('home-blocks');
const homeItems = document.getElementById('home-items');
const homeEmpty = document.getElementById('home-empty');

const categoryTitle = document.getElementById('category-title');
const categoryMeta = document.getElementById('category-meta');
const categoryType = document.getElementById('category-type');
const categoryItems = document.getElementById('category-items');
const categoryEmpty = document.getElementById('category-empty');
const categoryDescription = document.getElementById('category-description');
const categoryBlocks = document.getElementById('category-blocks');

const itemTitle = document.getElementById('product-title');
const itemDescription = document.getElementById('product-description');
const itemPrice = document.getElementById('product-price');
const itemCategory = document.getElementById('product-category');
const itemImage = document.getElementById('product-image');
const itemSubtitle = document.getElementById('product-subtitle');

const footerContacts = document.getElementById('footer-contacts');
const footerSocial = document.getElementById('footer-social');

let menuData = null;
let settingsData = null;
let blocksData = { home: [], category: [] };

function normalizeMediaUrl(url) {
  if (!url) return '';
  const raw = String(url).trim();
  if (!raw) return '';
  if (/^(https?:)?\/\//i.test(raw) || raw.startsWith('data:')) return raw;
  if (raw.startsWith('/')) return raw;
  return `/media/${raw}`;
}

function formatPrice(value, currency = '₽') {
  if (value === null || value === undefined || value === '') return 'Цена по запросу';
  const number = Number(value);
  if (!Number.isFinite(number)) return 'Цена по запросу';
  if (number === 0) return 'Бесплатно';
  return `${number.toLocaleString('ru-RU')} ${currency}`;
}

function hideAllViews() {
  Object.values(views).forEach((view) => view?.setAttribute('hidden', ''));
}

function showView(name) {
  hideAllViews();
  views[name]?.removeAttribute('hidden');
  document.body.dataset.view = name;
}

function applyColors(settings) {
  if (!settings) return;
  const root = document.documentElement;
  if (settings.primary_color) {
    root.style.setProperty('--color-primary', settings.primary_color);
    root.style.setProperty('--color-primary-hover', settings.primary_color);
  }
  if (settings.secondary_color) {
    root.style.setProperty('--color-accent', settings.secondary_color);
  }
  if (settings.background_color) {
    root.style.setProperty('--color-page-bg', settings.background_color);
  }
}

function applyBranding(settings) {
  const brandName = settings?.brand_name || 'MiniDeN';
  document.querySelectorAll('.brand__title').forEach((el) => {
    el.textContent = brandName;
  });

  const logoUrl = normalizeMediaUrl(settings?.logo_url);
  document.querySelectorAll('[data-brand-logo]').forEach((img) => {
    if (logoUrl) {
      img.src = logoUrl;
      img.style.display = 'block';
      img.alt = brandName;
      img.closest('[data-branding-block]')?.classList.add('has-logo');
    } else {
      img.style.display = 'none';
      img.closest('[data-branding-block]')?.classList.remove('has-logo');
    }
  });
}

function renderHero(settings) {
  if (!heroSection) return;
  if (settings?.hero_enabled === false) {
    heroSection.style.display = 'none';
    return;
  }
  heroSection.style.display = '';
  const title = settings?.hero_title || 'Меню и витрина';
  const subtitle = settings?.hero_subtitle || 'Добавляйте категории и позиции через AdminSite.';
  const imageUrl = normalizeMediaUrl(settings?.hero_image_url);

  if (heroTitle) heroTitle.textContent = title;
  if (heroSubtitle) heroSubtitle.textContent = subtitle;
  if (heroImage) {
    if (imageUrl) {
      heroImage.src = imageUrl;
      heroImage.style.display = 'block';
    } else {
      heroImage.style.display = 'none';
    }
  }
}

function renderFooter(settings) {
  if (footerContacts) {
    footerContacts.innerHTML = '';
    const contacts = settings?.contacts || {};
    Object.entries(contacts).forEach(([key, value]) => {
      if (!value) return;
      const line = document.createElement('div');
      line.className = 'muted';
      line.textContent = `${key}: ${value}`;
      footerContacts.appendChild(line);
    });
  }

  if (footerSocial) {
    footerSocial.innerHTML = '';
    const links = settings?.social_links || {};
    Object.entries(links).forEach(([key, value]) => {
      if (!value) return;
      const link = document.createElement('a');
      link.href = value;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = key;
      footerSocial.appendChild(link);
    });
  }
}

function buildCategoryButton(category) {
  const button = document.createElement('button');
  button.className = 'pill-button';
  button.type = 'button';
  button.textContent = category.title;
  button.addEventListener('click', () => {
    window.history.pushState({}, '', `/c/${encodeURIComponent(category.slug)}`);
    route();
  });
  return button;
}

function buildItemCard(item) {
  const card = document.createElement('article');
  card.className = 'catalog-card';

  const imageWrapper = document.createElement('div');
  imageWrapper.className = 'catalog-card-image';

  const imageUrl = normalizeMediaUrl(item.image_url || (item.images || [])[0]);
  if (imageUrl) {
    const img = document.createElement('img');
    img.src = imageUrl;
    img.alt = item.title || '';
    imageWrapper.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'catalog-card-meta';
    placeholder.textContent = 'Фото скоро появится';
    imageWrapper.appendChild(placeholder);
  }

  const body = document.createElement('div');
  body.className = 'catalog-card-body';

  const meta = document.createElement('div');
  meta.className = 'catalog-card-meta';
  meta.textContent = item.category_title || '';

  const title = document.createElement('h3');
  title.className = 'catalog-card-title';
  title.textContent = item.title || 'Позиция';

  const description = document.createElement('p');
  description.className = 'catalog-card-description';
  description.textContent = item.subtitle || item.description || '';

  const footer = document.createElement('div');
  footer.className = 'catalog-card-actions';

  const price = document.createElement('div');
  price.className = 'price';
  price.textContent = formatPrice(item.price, item.currency || '₽');

  const canUseTelegram = !!(window.isTelegramWebApp && window.Telegram?.WebApp);
  if (canUseTelegram && item?.id !== undefined) {
    const addButton = document.createElement('button');
    addButton.className = 'btn';
    addButton.type = 'button';
    addButton.textContent = 'В корзину';
    addButton.addEventListener('click', () => {
      try {
        window.Telegram.WebApp.sendData(
          JSON.stringify({
            action: 'add_to_cart',
            product_id: item.id,
            qty: 1,
            type: item.type,
            source: 'menu',
          })
        );
        window.Telegram.WebApp.close();
      } catch (error) {
        console.error('Не удалось отправить данные в Telegram WebApp', error);
      }
    });
    footer.append(price, addButton);
  } else {
    const more = document.createElement('a');
    more.className = 'btn secondary';
    more.href = `/i/${encodeURIComponent(item.slug)}`;
    more.textContent = 'Подробнее';
    more.setAttribute('data-router-link', '');
    footer.append(price, more);
  }

  body.append(meta, title, description, footer);
  card.append(imageWrapper, body);
  return card;
}

function renderMenuNavigation(categories) {
  if (!navMenu) return;
  navMenu.innerHTML = '';
  if (!categories.length) {
    const muted = document.createElement('span');
    muted.className = 'muted';
    muted.textContent = 'Категорий нет';
    navMenu.appendChild(muted);
    return;
  }

  categories.forEach((category) => {
    const link = document.createElement('a');
    link.href = `/c/${encodeURIComponent(category.slug)}`;
    link.textContent = category.title;
    link.dataset.routerLink = '';
    link.dataset.categorySlug = category.slug;
    link.className = 'category-link';
    navMenu.appendChild(link);
  });
}

function setActiveCategory(slug) {
  if (!navMenu) return;
  navMenu.querySelectorAll('[data-category-slug]').forEach((link) => {
    if (slug && link.dataset.categorySlug === slug) {
      link.classList.add('is-active');
    } else {
      link.classList.remove('is-active');
    }
  });
}

function renderBlocks(blocks, container) {
  if (!container) return;
  container.innerHTML = '';
  if (!blocks || !blocks.length) {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');
  blocks.forEach((block) => {
    const wrapper = document.createElement('article');
    wrapper.className = `content-block content-block--${block.type}`;
    const title = document.createElement('h3');
    title.textContent = block.title || '';
    const subtitle = document.createElement('p');
    subtitle.textContent = block.subtitle || '';
    subtitle.className = 'muted';

    if (block.type === 'banner') {
      wrapper.classList.add('content-block--banner');
      const image = document.createElement('img');
      const imageUrl = normalizeMediaUrl(block.image_url);
      if (imageUrl) {
        image.src = imageUrl;
        image.alt = block.title || 'Banner';
        wrapper.appendChild(image);
      }
    }

    if (block.type === 'cta') {
      const button = document.createElement('a');
      button.className = 'btn';
      button.textContent = block.payload?.button_text || 'Оставить заявку';
      button.href = block.payload?.button_link || '/cart';
      wrapper.appendChild(button);
    }

    if (block.title) wrapper.appendChild(title);
    if (block.subtitle) wrapper.appendChild(subtitle);
    container.appendChild(wrapper);
  });
}

function renderHome(categories) {
  if (!homeItems) return;
  if (homeCategories) {
    homeCategories.innerHTML = '';
  }
  homeItems.innerHTML = '';

  if (!categories.length) {
    homeEmpty?.classList.remove('hidden');
    homeEmpty.textContent = 'Добавьте категории в AdminSite, чтобы отобразить меню.';
    setActiveCategory(null);
    return;
  }

  homeEmpty?.classList.add('hidden');
  const firstCategory = categories[0];
  const items = firstCategory.items || [];
  items.forEach((item) => homeItems.appendChild(buildItemCard(item)));
  setActiveCategory(firstCategory?.slug || null);
}

function renderCategoryView(category) {
  if (!categoryItems) return;
  categoryTitle.textContent = category.title || 'Категория';
  categoryMeta.textContent = 'Категория меню';
  categoryType.textContent = category.type || 'Категория';
  categoryDescription.textContent = category.description || '';

  categoryItems.innerHTML = '';
  const items = category.items || [];
  if (!items.length) {
    categoryEmpty.style.display = 'block';
    categoryEmpty.textContent = 'В этой категории пока нет позиций.';
  } else {
    categoryEmpty.style.display = 'none';
    items.forEach((item) => categoryItems.appendChild(buildItemCard(item)));
  }
  setActiveCategory(category.slug);
  renderBlocks(blocksData.category, categoryBlocks);
}

function renderItemView(item) {
  const imageUrl = normalizeMediaUrl(item.image_url || (item.images || [])[0]);
  if (itemImage) {
    itemImage.src = imageUrl || '';
    itemImage.style.display = imageUrl ? 'block' : 'none';
  }
  itemTitle.textContent = item.title || 'Позиция';
  itemSubtitle.textContent = item.subtitle || '';
  itemDescription.textContent = item.description || '';
  itemPrice.textContent = formatPrice(item.price, item.currency || '₽');
  itemCategory.textContent = item.category_title || '';
  setActiveCategory(item.category_slug);
}

function findCategory(slug) {
  return menuData?.categories?.find((category) => category.slug === slug) || null;
}

function findItem(slug) {
  const categories = menuData?.categories || [];
  for (const category of categories) {
    const item = (category.items || []).find((entry) => entry.slug === slug);
    if (item) return item;
  }
  return null;
}

function closeSidebar() {
  navLinks?.classList.remove('app-sidebar--open');
  sidebarOverlay?.classList.remove('is-visible');
}

function route() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  const parts = path.split('/').filter(Boolean);

  if (path === '/' || parts.length === 0) {
    renderHome(menuData?.categories || []);
    renderBlocks(blocksData.home, homeBlocks);
    showView('home');
    return;
  }

  if (parts[0] === 'c' && parts[1]) {
    const category = findCategory(decodeURIComponent(parts[1]));
    if (!category) {
      setActiveCategory(null);
      showView('notFound');
      return;
    }
    renderCategoryView(category);
    showView('category');
    return;
  }

  if ((parts[0] === 'i' || parts[0] === 'p' || parts[0] === 'm') && parts[1]) {
    const item = findItem(decodeURIComponent(parts[1]));
    if (!item) {
      setActiveCategory(null);
      showView('notFound');
      return;
    }
    renderItemView(item);
    showView('item');
    return;
  }

  showView('notFound');
}

function bindNavigation() {
  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-router-link]');
    if (!link || !link.getAttribute('href')) return;
    const href = link.getAttribute('href');
    if (!href.startsWith('/')) return;
    event.preventDefault();
    window.history.pushState({}, '', href);
    closeSidebar();
    route();
  });

  window.addEventListener('popstate', route);

  const toggle = document.querySelector('.menu-toggle');
  toggle?.addEventListener('click', () => {
    navLinks?.classList.toggle('app-sidebar--open');
    sidebarOverlay?.classList.toggle('is-visible');
  });
  sidebarOverlay?.addEventListener('click', closeSidebar);
  sidebarClose?.addEventListener('click', closeSidebar);
}

async function bootstrap() {
  try {
    const [settings, menu, homeBlocksData, categoryBlocksData] = await Promise.all([
      fetchSiteSettings(),
      fetchMenu(),
      fetchBlocks('home'),
      fetchBlocks('category'),
    ]);
    settingsData = settings;
    menuData = menu;
    blocksData = {
      home: homeBlocksData?.items || [],
      category: categoryBlocksData?.items || [],
    };
  } catch (error) {
    console.error('Не удалось загрузить данные витрины', error);
    menuData = { categories: [] };
    blocksData = { home: [], category: [] };
  }

  applyColors(settingsData);
  applyBranding(settingsData);
  renderHero(settingsData);
  renderFooter(settingsData);
  renderMenuNavigation(menuData?.categories || []);
  route();
}

bindNavigation();
bootstrap();
