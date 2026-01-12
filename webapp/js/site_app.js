import {
  fetchBlocks,
  fetchMenu,
  fetchSiteSettings,
  fetchCategoryDetails,
  fetchItemById,
} from './site_api.js';

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
const typeTabs = document.getElementById('type-tabs');

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

const itemModal = document.getElementById('item-modal');
const itemModalOverlay = document.getElementById('item-modal-overlay');
const itemModalClose = document.getElementById('item-modal-close');
const itemModalImage = document.getElementById('item-modal-image');
const itemModalTitle = document.getElementById('item-modal-title');
const itemModalSubtitle = document.getElementById('item-modal-subtitle');
const itemModalDescription = document.getElementById('item-modal-description');
const itemModalPrice = document.getElementById('item-modal-price');
const itemModalCategory = document.getElementById('item-modal-category');
const itemModalStock = document.getElementById('item-modal-stock');
const itemModalQty = document.getElementById('item-modal-qty');
const itemModalMinus = document.getElementById('item-modal-minus');
const itemModalPlus = document.getElementById('item-modal-plus');
const itemModalAdd = document.getElementById('item-modal-add');

const footerContacts = document.getElementById('footer-contacts');
const footerSocial = document.getElementById('footer-social');

const cartBar = document.getElementById('cart-bar');
const cartBarCount = document.getElementById('cart-bar-count');
const cartBarTotal = document.getElementById('cart-bar-total');
const cartBarCheckout = document.getElementById('cart-bar-checkout');
const cartBarNote = document.getElementById('cart-bar-note');
const cartBadge = document.getElementById('cart-count');
const cartCheckoutSuccess = document.getElementById('cart-checkout-success');
const cartSuccessOpenBot = document.getElementById('cart-success-open-bot');
const cartSuccessClose = document.getElementById('cart-success-close');

let menuData = null;
let activeMenuType = 'product';
const menuCache = {};
let settingsData = null;
let blocksData = { home: [], category: [] };
let modalState = { item: null, returnUrl: null, qty: 1 };
let isModalOpen = false;
let telegramUserId = null;
let cartState = { items: [], total: 0 };
let cartLoading = false;
let checkoutSuccessShown = false;

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

function resolveTelegramUserId() {
  return window.Telegram?.WebApp?.initDataUnsafe?.user?.id || null;
}

function initTelegramContext() {
  telegramUserId = resolveTelegramUserId();
  if (window.Telegram?.WebApp?.ready) {
    window.Telegram.WebApp.ready();
  }
}

function getCartQtyTotal(items) {
  return (items || []).reduce((sum, item) => sum + (Number(item.qty) || 0), 0);
}

function setCartBarOffset(value) {
  document.documentElement.style.setProperty('--cart-bar-offset', `${value}px`);
}

function updateCartBarOffset() {
  if (!cartBar || !cartBar.classList.contains('cart-bar--visible')) {
    setCartBarOffset(0);
    return;
  }
  const height = cartBar.getBoundingClientRect().height;
  setCartBarOffset(Math.ceil(height));
}

function setCartBarVisible(visible) {
  if (!cartBar) return;
  cartBar.classList.toggle('cart-bar--visible', visible);
  cartBar.setAttribute('aria-hidden', visible ? 'false' : 'true');
  updateCartBarOffset();
}

function showInfoToast(message) {
  if (typeof window.showToast === 'function') {
    window.showToast(message);
  } else {
    console.warn(message);
  }
}

function mapCartType(type) {
  if (type === 'product') return 'basket';
  if (type === 'masterclass') return 'course';
  return type || 'basket';
}

function normalizeMenuType(value) {
  return value === 'masterclass' ? 'masterclass' : 'product';
}

function formatCategoryType(type) {
  if (type === 'masterclass') return 'Мастер-классы';
  if (type === 'product') return 'Товары';
  return type || 'Категория';
}

function getMenuTypeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const type = params.get('type');
  return type ? normalizeMenuType(type) : null;
}

function setMenuTypeParam(type, pathOverride = null) {
  const url = new URL(window.location.href);
  url.searchParams.set('type', type);
  const path = pathOverride ?? url.pathname;
  window.history.pushState({}, '', `${path}${url.search}`);
}

function updateTypeTabs() {
  if (!typeTabs) return;
  typeTabs.querySelectorAll('[data-menu-type]').forEach((tab) => {
    tab.classList.toggle('is-active', tab.dataset.menuType === activeMenuType);
  });
}

function isOutOfStock(item) {
  return item?.stock_qty === 0;
}

function isStockLimited(item) {
  return item?.stock_qty !== null && item?.stock_qty !== undefined;
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

async function fetchCart() {
  if (!telegramUserId) return { items: [], total: 0 };
  const url = new URL('/api/cart', window.location.origin);
  url.searchParams.set('user_id', String(telegramUserId));
  const response = await fetch(url.toString(), { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(text || response.statusText || 'Не удалось загрузить корзину');
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function updateCartBar(cart) {
  if (!cartBar || !cart) return;
  const qtyTotal = getCartQtyTotal(cart.items || []);
  const total = Number(cart.total) || 0;
  if (cartBarCount) cartBarCount.textContent = qtyTotal.toString();
  if (cartBarTotal) cartBarTotal.textContent = formatPrice(total);
  if (cartBadge) cartBadge.textContent = qtyTotal.toString();
  setCartBarVisible(qtyTotal > 0);
}

function updateCheckoutAvailability() {
  if (!cartBarCheckout) return;
  const hasTelegram = Boolean(telegramUserId);
  cartBarNote?.toggleAttribute('hidden', hasTelegram);
  cartBarCheckout.dataset.disabledHint = hasTelegram ? '' : 'true';
}

async function refreshCartBar() {
  if (!telegramUserId || cartLoading) {
    cartState = { items: [], total: 0 };
    updateCartBar(cartState);
    return;
  }
  cartLoading = true;
  try {
    cartState = await fetchCart();
    updateCartBar(cartState);
  } catch (error) {
    console.error('Не удалось загрузить корзину', error);
  } finally {
    cartLoading = false;
  }
}

async function addItemToCart(item, qty = 1) {
  if (!telegramUserId) {
    showInfoToast('Откройте витрину из Telegram бота.');
    return;
  }
  const cartType = mapCartType(item.type);
  const response = await fetch('/api/cart/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: telegramUserId,
      product_id: item.id,
      qty,
      type: cartType,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Не удалось добавить товар в корзину');
  }
  const updatedCart = await response.json();
  cartState = updatedCart;
  updateCartBar(updatedCart);
  showInfoToast('Добавлено в корзину');
}

function buildCheckoutPayload(cart) {
  const items = (cart.items || []).map((item) => ({
    item_id: item.product_id,
    title: item.name,
    qty: item.qty,
    price: item.price,
    type: item.type,
    category_slug: item.category_slug || null,
  }));
  const qtyTotal = getCartQtyTotal(cart.items || []);
  return {
    tg_user_id: telegramUserId,
    items,
    totals: {
      qty_total: qtyTotal,
      sum_total: Number(cart.total) || 0,
      currency: '₽',
    },
    client_context: {
      page_url: window.location.href,
      user_agent: navigator.userAgent,
      created_at: new Date().toISOString(),
    },
  };
}

function showCheckoutSuccess() {
  if (!cartCheckoutSuccess || checkoutSuccessShown) return;
  const username = window.TELEGRAM_BOT_USERNAME;
  const botLink = username ? `https://t.me/${username}` : 'https://t.me';
  if (cartSuccessOpenBot) {
    cartSuccessOpenBot.href = botLink;
  }
  cartCheckoutSuccess.removeAttribute('hidden');
  checkoutSuccessShown = true;
}

function dismissCheckoutSuccess() {
  cartCheckoutSuccess?.setAttribute('hidden', '');
}

async function submitCheckout() {
  if (!telegramUserId) {
    showInfoToast('Откройте витрину из Telegram бота.');
    return;
  }
  await refreshCartBar();
  if (!cartState.items?.length) {
    showInfoToast('Корзина пуста.');
    return;
  }
  const payload = buildCheckoutPayload(cartState);
  cartBarCheckout?.setAttribute('disabled', 'true');
  cartBarCheckout?.classList.add('is-loading');
  const originalText = cartBarCheckout?.textContent;
  if (cartBarCheckout) cartBarCheckout.textContent = 'Отправка...';
  checkoutSuccessShown = false;

  try {
    const response = await fetch('/api/public/checkout/from-webapp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || 'Не удалось отправить заказ');
    }
    await response.json();
    showCheckoutSuccess();
  } catch (error) {
    console.error('Ошибка отправки заказа', error);
    showInfoToast(error?.message || 'Не удалось отправить заказ');
  } finally {
    if (cartBarCheckout) {
      cartBarCheckout.textContent = originalText || 'Оформить';
      cartBarCheckout.classList.remove('is-loading');
      cartBarCheckout.removeAttribute('disabled');
    }
  }
}

function buildCategoryButton(category) {
  const button = document.createElement('button');
  button.className = 'pill-button';
  button.type = 'button';
  button.textContent = category.title;
  button.addEventListener('click', () => {
    const params = new URLSearchParams();
    params.set('type', activeMenuType);
    window.history.pushState(
      {},
      '',
      `/c/${encodeURIComponent(category.slug)}?${params.toString()}`
    );
    void route();
  });
  return button;
}

function buildItemCard(item) {
  const card = document.createElement('article');
  card.className = 'catalog-card';
  const outOfStock = isOutOfStock(item);
  if (outOfStock) {
    card.classList.add('is-out-of-stock');
  }
  const descriptionText = item.subtitle || item.description || '';
  if (descriptionText) {
    card.classList.add('has-description');
  }

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

  let stockBadge = null;
  if (outOfStock) {
    stockBadge = document.createElement('span');
    stockBadge.className = 'tag is-danger';
    stockBadge.textContent = 'Нет в наличии';
  }

  const description = document.createElement('p');
  description.className = 'catalog-card-description';
  description.textContent = descriptionText;
  if (!descriptionText) {
    description.classList.add('is-empty');
  }

  const footer = document.createElement('div');
  footer.className = 'catalog-card-actions';

  const price = document.createElement('div');
  price.className = 'price';
  price.textContent = formatPrice(item.price, item.currency || '₽');

  const buttons = document.createElement('div');
  buttons.className = 'catalog-card-buttons';

  const more = document.createElement('button');
  more.className = 'btn secondary';
  more.type = 'button';
  more.textContent = 'Подробнее';
  more.setAttribute('aria-label', 'Открыть подробности товара');
  more.addEventListener('click', (event) => {
    event.preventDefault();
    openItemModal(item, { pushHistory: true });
  });

  const addButton = document.createElement('button');
  addButton.className = 'btn catalog-card-add';
  addButton.type = 'button';
  addButton.textContent = 'В корзину';
  addButton.setAttribute('aria-label', 'Добавить в корзину');

  const canUseTelegram = !!(window.isTelegramWebApp && telegramUserId);
  addButton.disabled = outOfStock || !canUseTelegram;
  if (outOfStock) {
    addButton.title = 'Нет в наличии';
  } else if (!canUseTelegram) {
    addButton.title = 'Добавление доступно только в Telegram';
  }
  addButton.addEventListener('click', () => {
    if (outOfStock || !item?.id) return;
    addItemToCart(item, 1).catch((error) => {
      console.error('Не удалось добавить товар в корзину', error);
      showInfoToast('Не удалось добавить товар в корзину');
    });
  });

  buttons.append(more, addButton);
  footer.append(price, buttons);

  body.append(meta, title);
  if (stockBadge) body.appendChild(stockBadge);
  body.append(description, footer);
  card.append(imageWrapper, body);
  card.addEventListener('click', (event) => {
    if (event.target.closest('button, a')) return;
    openItemModal(item, { pushHistory: true });
  });
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

  const renderTree = (nodes, depth = 0) => {
    nodes.forEach((category) => {
      const link = document.createElement('a');
      link.href = `/c/${encodeURIComponent(category.slug)}?type=${activeMenuType}`;
      link.textContent = category.title;
      link.dataset.routerLink = '';
      link.dataset.categorySlug = category.slug;
      link.dataset.depth = depth.toString();
      link.className = 'category-link';
      link.style.paddingLeft = `${12 + depth * 14}px`;
      navMenu.appendChild(link);
      if (category.children && category.children.length) {
        renderTree(category.children, depth + 1);
      }
    });
  };

  renderTree(categories);
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

async function loadMenuByType(type) {
  const normalized = normalizeMenuType(type);
  if (menuCache[normalized]) {
    menuData = menuCache[normalized];
    return menuData;
  }
  const data = await fetchMenu(normalized);
  menuCache[normalized] = data;
  menuData = data;
  return data;
}

async function setActiveMenuType(type, { updateUrl = false, pathOverride = null } = {}) {
  const normalized = normalizeMenuType(type);
  if (activeMenuType === normalized && menuData) {
    if (updateUrl) setMenuTypeParam(normalized, pathOverride);
    updateTypeTabs();
    return;
  }
  activeMenuType = normalized;
  await loadMenuByType(normalized);
  renderMenuNavigation(menuData?.categories || []);
  updateTypeTabs();
  if (updateUrl) setMenuTypeParam(normalized, pathOverride);
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
  const firstCategory = findFirstCategoryWithItems(categories);
  const items = firstCategory.items || [];
  items.forEach((item) => homeItems.appendChild(buildItemCard(item)));
  setActiveCategory(firstCategory?.slug || null);
}

function renderCategoryView(category) {
  if (!categoryItems) return;
  categoryTitle.textContent = category.title || 'Категория';
  categoryMeta.textContent = 'Категория меню';
  categoryType.textContent = formatCategoryType(category.type);
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

function updateModalQty(nextQty) {
  modalState.qty = Math.max(1, nextQty);
  if (itemModalQty) itemModalQty.textContent = modalState.qty.toString();
}

function renderItemModal(item) {
  const imageUrl = normalizeMediaUrl(item.image_url || (item.images || [])[0]);
  if (itemModalImage) {
    itemModalImage.src = imageUrl || '';
    itemModalImage.style.display = imageUrl ? 'block' : 'none';
  }
  if (itemModalTitle) itemModalTitle.textContent = item.title || 'Позиция';
  if (itemModalSubtitle) itemModalSubtitle.textContent = item.subtitle || '';
  if (itemModalDescription) itemModalDescription.textContent = item.description || '';
  if (itemModalPrice) itemModalPrice.textContent = formatPrice(item.price, item.currency || '₽');
  if (itemModalCategory) itemModalCategory.textContent = item.category_title || '';

  const outOfStock = isOutOfStock(item);
  if (itemModalStock) {
    if (outOfStock) {
      itemModalStock.textContent = 'Нет в наличии';
      itemModalStock.classList.add('is-danger');
      itemModalStock.style.display = '';
    } else {
      itemModalStock.textContent = '';
      itemModalStock.classList.remove('is-danger');
      itemModalStock.style.display = 'none';
    }
  }

  updateModalQty(1);

  const canUseTelegram = !!(window.isTelegramWebApp && window.Telegram?.WebApp);
  if (itemModalAdd) {
    itemModalAdd.disabled = outOfStock || !canUseTelegram;
    itemModalAdd.title = !canUseTelegram ? 'Добавление доступно только в Telegram' : '';
  }
  if (itemModalMinus) {
    itemModalMinus.disabled = outOfStock;
  }
  if (itemModalPlus) {
    itemModalPlus.disabled = outOfStock;
  }
}

function updateModalStockControls(item) {
  if (!item) return;
  const outOfStock = isOutOfStock(item);
  if (itemModalAdd) {
    itemModalAdd.disabled = outOfStock || !(window.isTelegramWebApp && window.Telegram?.WebApp);
  }
  if (itemModalMinus) {
    itemModalMinus.disabled = outOfStock || modalState.qty <= 1;
  }
  if (itemModalPlus) {
    if (outOfStock) {
      itemModalPlus.disabled = true;
    } else if (isStockLimited(item)) {
      itemModalPlus.disabled = modalState.qty >= item.stock_qty;
    } else {
      itemModalPlus.disabled = false;
    }
  }
}

function openItemModal(item, { pushHistory = false, returnUrl } = {}) {
  if (!itemModal || !itemModalOverlay) return;
  modalState.item = item;
  const currentUrl = `${window.location.pathname}${window.location.search}`;
  modalState.returnUrl = returnUrl === undefined ? currentUrl : returnUrl;
  modalState.qty = 1;
  renderItemModal(item);
  updateModalStockControls(item);

  itemModal.classList.add('is-visible');
  itemModalOverlay.classList.add('is-visible');
  itemModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
  isModalOpen = true;

  if (pushHistory) {
    const itemUrl = `/i/${encodeURIComponent(item.id)}`;
    const params = new URLSearchParams(window.location.search);
    params.set('type', activeMenuType);
    const query = params.toString();
    window.history.pushState({ modal: true }, '', `${itemUrl}${query ? `?${query}` : ''}`);
  }
}

function hideItemModal() {
  if (!itemModal || !itemModalOverlay) return;
  itemModal.classList.remove('is-visible');
  itemModalOverlay.classList.remove('is-visible');
  itemModal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
  isModalOpen = false;
}

function closeItemModal({ useHistoryBack = true } = {}) {
  const returnUrl = modalState.returnUrl;
  const item = modalState.item;
  modalState = { item: null, returnUrl: null, qty: 1 };
  hideItemModal();

  if (useHistoryBack && returnUrl) {
    window.history.back();
    return;
  }

  if (item?.category_slug) {
    const params = new URLSearchParams();
    params.set('type', activeMenuType);
    window.history.pushState(
      {},
      '',
      `/c/${encodeURIComponent(item.category_slug)}?${params.toString()}`
    );
  } else {
    const params = new URLSearchParams();
    params.set('type', activeMenuType);
    window.history.pushState({}, '', `/?${params.toString()}`);
  }
  void route();
}

function findCategory(slug, categories = menuData?.categories || []) {
  for (const category of categories) {
    if (category.slug === slug) return category;
    const nested = findCategory(slug, category.children || []);
    if (nested) return nested;
  }
  return null;
}

function findItemBySlug(slug, categories = menuData?.categories || []) {
  for (const category of categories) {
    const item = (category.items || []).find((entry) => entry.slug === slug);
    if (item) return item;
    const nested = findItemBySlug(slug, category.children || []);
    if (nested) return nested;
  }
  return null;
}

function findItemById(itemId, categories = menuData?.categories || []) {
  for (const category of categories) {
    const item = (category.items || []).find((entry) => entry.id === itemId);
    if (item) return item;
    const nested = findItemById(itemId, category.children || []);
    if (nested) return nested;
  }
  return null;
}

function findFirstCategoryWithItems(categories = []) {
  for (const category of categories) {
    if ((category.items || []).length) return category;
    const nested = findFirstCategoryWithItems(category.children || []);
    if (nested) return nested;
  }
  return categories[0] || null;
}

function closeSidebar() {
  navLinks?.classList.remove('app-sidebar--open');
  sidebarOverlay?.classList.remove('is-visible');
}

function bindModalActions() {
  itemModalClose?.addEventListener('click', () => closeItemModal());
  itemModalOverlay?.addEventListener('click', () => closeItemModal());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && isModalOpen) {
      closeItemModal();
    }
  });
  itemModalMinus?.addEventListener('click', () => {
    if (!modalState.item) return;
    updateModalQty(modalState.qty - 1);
    updateModalStockControls(modalState.item);
  });
  itemModalPlus?.addEventListener('click', () => {
    if (!modalState.item) return;
    let nextQty = modalState.qty + 1;
    if (isStockLimited(modalState.item)) {
      nextQty = Math.min(nextQty, modalState.item.stock_qty);
    }
    updateModalQty(nextQty);
    updateModalStockControls(modalState.item);
  });
  itemModalAdd?.addEventListener('click', () => {
    if (!modalState.item || isOutOfStock(modalState.item)) return;
    addItemToCart(modalState.item, modalState.qty).catch((error) => {
      console.error('Не удалось добавить товар в корзину', error);
      showInfoToast('Не удалось добавить товар в корзину');
    });
  });
}

function bindCartBarActions() {
  cartBarCheckout?.addEventListener('click', () => {
    if (!telegramUserId) {
      showInfoToast('Откройте витрину из Telegram бота.');
      cartBarNote?.removeAttribute('hidden');
      return;
    }
    void submitCheckout();
  });

  cartSuccessClose?.addEventListener('click', () => {
    dismissCheckoutSuccess();
  });

  cartCheckoutSuccess?.addEventListener('click', (event) => {
    if (event.target === cartCheckoutSuccess) {
      dismissCheckoutSuccess();
    }
  });

  cartSuccessOpenBot?.addEventListener('click', (event) => {
    const username = window.TELEGRAM_BOT_USERNAME;
    const botLink = username ? `https://t.me/${username}` : 'https://t.me';
    if (window.Telegram?.WebApp?.openTelegramLink) {
      event.preventDefault();
      dismissCheckoutSuccess();
      window.Telegram.WebApp.openTelegramLink(botLink);
      return;
    }
    dismissCheckoutSuccess();
  });

  window.addEventListener('resize', updateCartBarOffset);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      void refreshCartBar();
    }
  });
}

async function route() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  const parts = path.split('/').filter(Boolean);
  const urlType = getMenuTypeFromUrl();

  if (urlType && urlType !== activeMenuType) {
    await setActiveMenuType(urlType);
  } else if (!menuData) {
    await setActiveMenuType(activeMenuType);
  }

  const isItemRoute =
    (parts[0] === 'i' || parts[0] === 'p' || parts[0] === 'm' || parts[0] === 'item') &&
    parts[1];

  if (!isItemRoute && isModalOpen) {
    hideItemModal();
  }

  if (path === '/' || parts.length === 0) {
    renderHome(menuData?.categories || []);
    renderBlocks(blocksData.home, homeBlocks);
    showView('home');
    return;
  }

  if (parts[0] === 'c' && parts[1]) {
    const slug = decodeURIComponent(parts[1]);
    let category = findCategory(slug);
    if (!category) {
      try {
        const fetched = await fetchCategoryDetails(slug);
        if (fetched?.type && fetched.type !== activeMenuType) {
          await setActiveMenuType(fetched.type);
        }
        category = fetched;
      } catch (error) {
        category = null;
      }
    }
    if (!category) {
      setActiveCategory(null);
      showView('notFound');
      return;
    }
    renderCategoryView(category);
    showView('category');
    return;
  }

  if (isItemRoute && parts[1]) {
    const identifier = decodeURIComponent(parts[1]);
    let item = null;
    if (/^\d+$/.test(identifier)) {
      const itemId = Number(identifier);
      item = findItemById(itemId);
      if (!item) {
        try {
          item = await fetchItemById(itemId);
        } catch (error) {
          item = null;
        }
      }
    } else {
      item = findItemBySlug(identifier);
    }

    if (!item) {
      setActiveCategory(null);
      showView('notFound');
      return;
    }

    if (item.type && item.type !== activeMenuType) {
      await setActiveMenuType(item.type);
    }

    const category = item.category_slug ? findCategory(item.category_slug) : null;
    if (category) {
      renderCategoryView(category);
      showView('category');
    } else {
      renderHome(menuData?.categories || []);
      showView('home');
    }
    openItemModal(item, { pushHistory: false, returnUrl: null });
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
    void route();
  });

  window.addEventListener('popstate', () => {
    void route();
  });

  const toggle = document.querySelector('.menu-toggle');
  toggle?.addEventListener('click', () => {
    navLinks?.classList.toggle('app-sidebar--open');
    sidebarOverlay?.classList.toggle('is-visible');
  });
  sidebarOverlay?.addEventListener('click', closeSidebar);
  sidebarClose?.addEventListener('click', closeSidebar);

  typeTabs?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-menu-type]');
    if (!button) return;
    const nextType = button.dataset.menuType;
    if (!nextType || nextType === activeMenuType) return;
    void setActiveMenuType(nextType, { updateUrl: true, pathOverride: '/' });
    closeSidebar();
    void route();
  });

  bindModalActions();
  bindCartBarActions();
}

async function bootstrap() {
  initTelegramContext();
  updateCheckoutAvailability();
  try {
    const urlType = getMenuTypeFromUrl();
    activeMenuType = urlType || activeMenuType;
    const [settings, menu, homeBlocksData, categoryBlocksData] = await Promise.all([
      fetchSiteSettings(),
      fetchMenu(activeMenuType),
      fetchBlocks('home'),
      fetchBlocks('category'),
    ]);
    settingsData = settings;
    menuData = menu;
    menuCache[activeMenuType] = menu;
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
  updateTypeTabs();
  await route();
  await refreshCartBar();
}

bindNavigation();
bootstrap();
