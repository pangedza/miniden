import {
  fetchCategory,
  fetchHome,
  fetchMasterclass,
  fetchMenu,
  fetchProduct,
  fetchItems,
} from './site_api.js';
import { getTemplateById, templatesRegistry } from './templates_registry.js';

const queryParams = new URLSearchParams(window.location.search);
const DEBUG_MODE = queryParams.get('debug') === '1';

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
const themeStylesheet = document.getElementById('theme-stylesheet');
const templateName = document.getElementById('template-name');
const homeBlocksContainer = document.getElementById('home-blocks');
const debugState = {
  lastFetchUrl: '—',
  lastFetchStatus: '—',
  lastError: '',
  receivedVersion: '—',
  updatedAt: '—',
  appliedTemplateId: '—',
  themeLoadedUrl: '—',
  blocksCount: 0,
  blockTypes: '',
};
let debugPanel = null;
let lastHomeConfig = null;

function normalizeMediaUrl(url, { absolute = false } = {}) {
  if (!url) return '';

  const raw = String(url).trim();
  if (!raw) return '';

  const isAbsolute = /^(https?:)?\/\//i.test(raw) || raw.startsWith('data:');
  let normalized = raw;

  if (!isAbsolute) {
    if (raw.startsWith('/static/')) {
      normalized = raw;
    } else if (raw.startsWith('/')) {
      normalized = raw;
    } else {
      normalized = `/static/uploads/${raw}`;
    }
  }

  if (absolute) {
    try {
      normalized = new URL(normalized, window.location.origin).href;
    } catch (error) {
      console.warn('Failed to build absolute media URL', raw, error);
    }
  }

  return normalized;
}

function appendImageWithFallback(container, url, alt, { onFallback, absolute = true } = {}) {
  if (!container) return null;

  const normalizedUrl = normalizeMediaUrl(url, { absolute });
  if (!normalizedUrl) {
    onFallback?.();
    return null;
  }

  const img = document.createElement('img');
  img.alt = alt || '';
  img.src = normalizedUrl;
  img.onerror = () => {
    img.remove();
    onFallback?.();
  };
  container.appendChild(img);
  return img;
}

function ensureDebugOverlay() {
  if (!DEBUG_MODE || debugPanel) return debugPanel;

  const overlay = document.createElement('div');
  overlay.id = 'site-debug-overlay';
  overlay.style.position = 'fixed';
  overlay.style.bottom = '12px';
  overlay.style.right = '12px';
  overlay.style.zIndex = '9999';
  overlay.style.background = 'rgba(15,23,42,0.9)';
  overlay.style.color = '#e5e7eb';
  overlay.style.padding = '12px';
  overlay.style.borderRadius = '12px';
  overlay.style.width = '320px';
  overlay.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';
  overlay.style.fontSize = '12px';
  overlay.style.lineHeight = '1.5';

  const title = document.createElement('div');
  title.textContent = 'Home debug overlay';
  title.style.fontWeight = '700';
  title.style.marginBottom = '8px';
  overlay.appendChild(title);

  const rows = {};
  const rowKeys = [
    ['lastFetchUrl', 'lastFetchUrl'],
    ['lastFetchStatus', 'lastFetchStatus'],
    ['lastError', 'lastError'],
    ['receivedVersion', 'receivedVersion'],
    ['updatedAt', 'updatedAt'],
    ['appliedTemplateId', 'appliedTemplateId'],
    ['themeLoadedUrl', 'themeLoadedUrl'],
    ['blocksCount', 'blocksCount'],
    ['blockTypes', 'blockTypes'],
  ];

  rowKeys.forEach(([label, key]) => {
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.justifyContent = 'space-between';
    row.style.gap = '6px';
    row.style.marginBottom = '4px';

    const labelEl = document.createElement('span');
    labelEl.textContent = `${label}:`;
    labelEl.style.color = '#9ca3af';

    const valueEl = document.createElement('span');
    valueEl.dataset.debugKey = key;
    valueEl.style.textAlign = 'right';
    valueEl.style.flex = '1';
    valueEl.textContent = '—';

    row.append(labelEl, valueEl);
    overlay.appendChild(row);
    rows[key] = valueEl;
  });

  const actions = document.createElement('div');
  actions.style.display = 'flex';
  actions.style.justifyContent = 'flex-end';
  actions.style.gap = '8px';
  actions.style.marginTop = '8px';

  const reloadButton = document.createElement('button');
  reloadButton.textContent = 'Reload config';
  reloadButton.style.background = '#22c55e';
  reloadButton.style.color = '#0b1727';
  reloadButton.style.border = 'none';
  reloadButton.style.padding = '6px 10px';
  reloadButton.style.borderRadius = '6px';
  reloadButton.style.cursor = 'pointer';
  reloadButton.style.fontWeight = '700';
  reloadButton.addEventListener('click', () => loadHomeConfig({ reason: 'manual-reload' }));

  actions.appendChild(reloadButton);
  overlay.appendChild(actions);

  document.body.appendChild(overlay);
  debugPanel = { overlay, rows, reloadButton };
  return debugPanel;
}

function updateDebugOverlay(partial = {}) {
  if (!DEBUG_MODE) return;
  if (!debugPanel) ensureDebugOverlay();
  Object.assign(debugState, partial);

  if (!debugPanel) return;
  Object.entries(debugPanel.rows).forEach(([key, el]) => {
    el.textContent = debugState[key] ?? '—';
  });

  debugPanel.overlay.style.border = debugState.lastError ? '1px solid #fca5a5' : '1px solid transparent';
}

function buildThemeUrl(version) {
  const base = '/css/theme.css';
  if (!version) return base;
  return `${base}?v=${encodeURIComponent(version)}`;
}

function ensureThemeStylesheet(version) {
  const cacheBust = queryParams.get('theme') || version;
  const href = buildThemeUrl(cacheBust);
  if (themeStylesheet && href !== themeStylesheet.getAttribute('href')) {
    themeStylesheet.setAttribute('href', href);
  }

  const appliedHref = themeStylesheet?.getAttribute('href') || href;
  updateDebugOverlay({ themeLoadedUrl: appliedHref || '—' });
  return appliedHref;
}

function renderHomeMessage(title, description = 'Настройте главную страницу в AdminSite.') {
  if (!homeBlocksContainer) return;
  homeBlocksContainer.innerHTML = '';

  const notice = document.createElement('div');
  notice.className = 'notice';

  const heading = document.createElement('h2');
  heading.textContent = title;
  notice.appendChild(heading);

  if (description) {
    const text = document.createElement('p');
    text.className = 'muted';
    text.textContent = description;
    notice.appendChild(text);
  }

  homeBlocksContainer.appendChild(notice);
}

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

  const showPlaceholder = () => {
    if (imageWrapper.querySelector('.catalog-card-meta')) return;
    const placeholder = document.createElement('div');
    placeholder.className = 'catalog-card-meta';
    placeholder.textContent = 'Изображение появится позже';
    imageWrapper.appendChild(placeholder);
  };

  const itemImage = appendImageWithFallback(
    imageWrapper,
    item?.image_url || item?.imageUrl,
    item.title || 'Элемент витрины',
    { onFallback: showPlaceholder }
  );

  if (!itemImage) {
    showPlaceholder();
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

function applyTemplate(templateId) {
  const resolvedTemplate = getTemplateById(templateId);
  const appliedId = resolvedTemplate?.id || templateId || '—';
  document.documentElement.dataset.template = appliedId;
  if (templateName) templateName.textContent = resolvedTemplate?.name || templateId || '—';
  updateDebugOverlay({ appliedTemplateId: appliedId });
  return appliedId;
}

function buildHeroSection(block) {
  const section = document.createElement('section');
  section.className = 'page-hero reveal';

  if (block?.background?.value) {
    const bgValue =
      block?.background?.type === 'image'
        ? `url(${block.background.value}) center/cover no-repeat`
        : block.background.value;
    section.style.background = bgValue;
  }

  const content = document.createElement('div');
  content.className = 'page-hero__content';

  const eyebrow = document.createElement('span');
  eyebrow.className = 'hero-eyebrow muted';
  eyebrow.textContent = 'AdminSite';
  content.appendChild(eyebrow);

  const title = document.createElement('h1');
  title.className = 'hero-title';
  title.textContent = block?.title || 'Витрина';
  content.appendChild(title);

  if (block?.subtitle) {
    const subtitle = document.createElement('p');
    subtitle.className = 'hero-subtitle';
    subtitle.textContent = block.subtitle;
    content.appendChild(subtitle);
  }

  const visual = document.createElement('div');
  visual.className = 'page-hero__visual';

  const createPlaceholder = () => {
    const placeholder = document.createElement('div');
    placeholder.className = 'page-hero__placeholder';
    placeholder.setAttribute('aria-hidden', 'true');
    return placeholder;
  };

  const ensurePlaceholder = () => {
    if (!visual.querySelector('.page-hero__placeholder')) {
      visual.appendChild(createPlaceholder());
    }
  };

  const heroImage = appendImageWithFallback(
    visual,
    block?.imageUrl || block?.image_url,
    block?.title || 'Hero',
    { onFallback: ensurePlaceholder }
  );

  if (!heroImage) {
    ensurePlaceholder();
  }

  section.append(content, visual);
  return section;
}

function buildFallbackCards(data) {
  const cards = [];
  const categories = [...(data?.product_categories || []), ...(data?.course_categories || [])];
  categories.slice(0, 3).forEach((category) => {
    cards.push({
      title: category?.title || 'Категория',
      href: category?.url || `/c/${category?.slug || ''}`,
      icon: 'folder',
      imageUrl: category?.image_url,
      description: category?.type === 'course' ? 'Мастер-классы' : 'Каталог',
    });
  });

  const featured = [...(data?.featured_products || []), ...(data?.featured_masterclasses || [])];
  featured.slice(0, 3).forEach((item) => {
    cards.push({
      title: item?.title || 'Элемент',
      href: item?.url || '#',
      imageUrl: item?.image_url,
      description: item?.short_text,
    });
  });

  return cards;
}

function buildCard(item) {
  const card = document.createElement('article');
  card.className = 'page-card hover-lift';

  appendImageWithFallback(
    card,
    item?.imageUrl || item?.image_url,
    item?.title || 'Изображение'
  );

  const body = document.createElement('div');
  body.className = 'page-card__body';

  const title = document.createElement('h3');
  title.textContent = item?.title || 'Карточка';
  body.appendChild(title);

  if (item?.description) {
    const desc = document.createElement('p');
    desc.className = 'muted';
    desc.textContent = item.description;
    body.appendChild(desc);
  }

  if (item?.href) {
    const link = document.createElement('a');
    link.href = item.href;
    link.textContent = 'Открыть';
    link.className = 'btn secondary';
    link.dataset.routerLink = '';
    body.appendChild(link);
  }

  card.appendChild(body);
  return card;
}

function buildCardsSection(block, data) {
  const section = document.createElement('section');
  section.className = 'page-section reveal';

  if (block?.title || block?.subtitle) {
    const header = document.createElement('div');
    header.className = 'section__header';
    if (block?.title) {
      const title = document.createElement('h2');
      title.textContent = block.title;
      header.appendChild(title);
    }
    if (block?.subtitle) {
      const subtitle = document.createElement('p');
      subtitle.className = 'muted';
      subtitle.textContent = block.subtitle;
      header.appendChild(subtitle);
    }
    section.appendChild(header);
  }

  const grid = document.createElement('div');
  grid.className = 'cards-grid';
  grid.style.setProperty('--columns', block?.layout?.columns || 2);

  const items = block?.items?.length ? block.items : buildFallbackCards(data);
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'muted';
    empty.textContent = 'Карточки будут показаны после заполнения конфигурации.';
    section.appendChild(empty);
  } else {
    items.forEach((item) => grid.appendChild(buildCard(item)));
    section.appendChild(grid);
  }

  return section;
}

function buildTextSection(block) {
  const section = document.createElement('section');
  section.className = 'page-section reveal';

  if (block?.title) {
    const title = document.createElement('h2');
    title.textContent = block.title;
    section.appendChild(title);
  }

  if (block?.text) {
    const text = document.createElement('p');
    text.className = 'muted';
    text.textContent = block.text;
    section.appendChild(text);
  }

  return section;
}

function buildSocialSection(block) {
  const section = document.createElement('section');
  section.className = 'page-section reveal';

  const title = document.createElement('h2');
  title.textContent = 'Связаться';
  section.appendChild(title);

  const list = document.createElement('div');
  list.className = 'social-grid';
  const items = block?.items || [];
  if (!items.length) {
    const muted = document.createElement('div');
    muted.className = 'muted';
    muted.textContent = 'Добавьте ссылки в админке AdminSite.';
    section.appendChild(muted);
  } else {
    items.forEach((item) => {
      const link = document.createElement('a');
      link.href = item.href;
      link.target = '_blank';
      link.rel = 'noopener';
      link.className = 'social-chip';
      link.textContent = item.label || item.type;
      list.appendChild(link);
    });
    section.appendChild(list);
  }

  return section;
}

function appendBlockFallback(block, errorMessage = 'Блок не отобразился') {
  if (!homeBlocksContainer) return;
  const notice = document.createElement('div');
  notice.className = 'notice';

  const title = document.createElement('h3');
  title.textContent = block?.title || `Блок ${block?.type || ''}` || 'Блок';
  notice.appendChild(title);

  const text = document.createElement('p');
  text.className = 'muted';
  text.textContent = errorMessage;
  notice.appendChild(text);

  homeBlocksContainer.appendChild(notice);
}

function renderHomeBlocks(blocks, data) {
  if (!homeBlocksContainer) return;
  homeBlocksContainer.innerHTML = '';

  const normalizedBlocks = Array.isArray(blocks) ? blocks : [];
  if (!normalizedBlocks.length) {
    renderHomeMessage('Блоки отсутствуют', 'Сохраните блоки в AdminSite и обновите страницу.');
    return;
  }

  const blockErrors = [];

  normalizedBlocks.forEach((block, index) => {
    try {
      if (block?.type === 'hero') {
        homeBlocksContainer.appendChild(buildHeroSection(block));
        return;
      }
      if (block?.type === 'cards') {
        homeBlocksContainer.appendChild(buildCardsSection(block, data));
        return;
      }
      if (block?.type === 'text') {
        homeBlocksContainer.appendChild(buildTextSection(block));
        return;
      }
      if (block?.type === 'social') {
        homeBlocksContainer.appendChild(buildSocialSection(block));
        return;
      }

      appendBlockFallback(block, 'Тип блока не поддерживается.');
      blockErrors.push(`block #${index + 1}: unsupported type ${block?.type || 'unknown'}`);
    } catch (error) {
      console.error('Failed to render block', block, error);
      const message = error?.message || String(error);
      blockErrors.push(`block #${index + 1} (${block?.type || 'unknown'}): ${message}`);
      appendBlockFallback(block, message);
    }
  });

  updateDebugOverlay({ lastError: blockErrors.join(' | ') });
}

function normalizeHomeResponse(data) {
  const page = data?.page ?? data?.config ?? (data?.blocks ? data : null);
  const blocks = data?.blocks ?? page?.blocks ?? [];
  const templateId =
    page?.templateId || page?.template_id || data?.templateId || data?.template_id || null;
  const version = data?.version ?? page?.version ?? data?.updatedAt ?? page?.updatedAt ?? '—';
  const updatedAt = page?.updatedAt ?? data?.updatedAt ?? version ?? '—';
  const theme = data?.theme || {};
  const themeVersion =
    data?.themeVersion || theme?.timestamp || theme?.updatedAt || theme?.generatedAt || null;
  const themeTemplate = theme?.appliedTemplateId || templateId;
  const blockTypes = Array.isArray(blocks)
    ? blocks.map((block) => block?.type || 'unknown').filter(Boolean)
    : [];

  return {
    __normalized: true,
    page,
    blocks: Array.isArray(blocks) ? blocks : [],
    templateId,
    version,
    updatedAt,
    theme,
    themeVersion,
    themeTemplate,
    blocksCount: Array.isArray(blocks) ? blocks.length : 0,
    blockTypes,
    raw: data,
  };
}

function renderHome(data) {
  const normalized = data?.__normalized ? data : normalizeHomeResponse(data);
  if (!normalized.page && !normalized.blocks.length) {
    renderHomeMessage('Главная не настроена');
    return;
  }

  console.debug('[site] Loaded home config', normalized);
  const themeUrl = ensureThemeStylesheet(normalized.themeVersion);
  const appliedTemplate = applyTemplate(normalized.themeTemplate || normalized.templateId);
  updateDebugOverlay({
    appliedTemplateId: appliedTemplate,
    themeLoadedUrl: themeUrl || '—',
    receivedVersion: normalized.version || '—',
    updatedAt: normalized.updatedAt || normalized.version || '—',
    blocksCount: normalized.blocksCount || 0,
    blockTypes: normalized.blockTypes?.join(', ') || '—',
  });
  renderHomeBlocks(normalized.blocks, normalized.raw || normalized.page || {});
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

function mergeItems(primary = [], secondary = []) {
  const map = new Map();
  [...secondary, ...primary].forEach((item) => {
    if (!item || item.id === undefined || item.id === null) return;
    map.set(item.id, item);
  });
  return Array.from(map.values());
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
      await loadHomeConfig();
      showView('home');
      return;
    }

    if (route.view === 'category' && route.slug) {
      const category = await fetchCategory(route.slug);
      let items = category?.items || [];
      if (category?.category?.id) {
        try {
          const response = await fetchItems({
            type: category?.category?.type,
            category_id: category.category.id,
          });
          items = mergeItems(response?.items || [], items);
        } catch (error) {
          console.error('Failed to load category items', error);
        }
      }
      renderCategory({ ...category, items });
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

async function loadHomeConfig({ reason = 'initial' } = {}) {
  const cacheBust = Date.now().toString();
  const fetchUrl = `/api/site/home?limit=6&t=${cacheBust}`;
  updateDebugOverlay({
    lastFetchUrl: fetchUrl,
    lastFetchStatus: 'loading',
    lastError: '',
  });

  try {
    const { payload: homeData, status, statusText, url } = await fetchHome(6, cacheBust, { reason });
    const normalized = normalizeHomeResponse(homeData);
    lastHomeConfig = normalized;

    updateDebugOverlay({
      lastFetchUrl: url || fetchUrl,
      lastFetchStatus: `${status || 200} ${statusText || 'OK'}`.trim(),
      lastError: '',
      receivedVersion: normalized.version || '—',
      updatedAt: normalized.updatedAt || '—',
      appliedTemplateId: normalized.templateId || '—',
      blocksCount: normalized.blocksCount || 0,
      blockTypes: normalized.blockTypes?.join(', ') || '—',
    });

    renderHome(normalized);
  } catch (error) {
    console.error('Failed to load home', error);
    updateDebugOverlay({
      lastFetchStatus: error?.status ? `error ${error.status}` : 'error',
      lastError: error?.message || String(error),
      lastFetchUrl: fetchUrl,
      appliedTemplateId: '—',
      blocksCount: 0,
      blockTypes: '',
    });
    renderHomeMessage('Не удалось загрузить главную', 'Попробуйте обновить страницу позже.');
  }
}

async function bootstrap() {
  setupMenuToggle();
  bindRouterLinks();
  ensureDebugOverlay();
  ensureThemeStylesheet();

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
