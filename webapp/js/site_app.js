import {
  fetchCategory,
  fetchHome,
  fetchMasterclass,
  fetchMenu,
  fetchProduct,
  fetchItems,
} from './site_api.js';
import { getTemplateById, templatesRegistry } from './templates_registry.js';

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
const templateName = document.getElementById('template-name');
const homeBlocksContainer = document.getElementById('home-blocks');

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

function applyTemplate(templateId) {
  const template = getTemplateById(templateId) || getTemplateById('services') || templatesRegistry[0];
  const vars = template?.cssVars || {};
  const root = document.documentElement;

  const defaults = {
    bg: '#f5f6fb',
    text: '#1f2937',
    muted: '#6b7280',
    'card-bg': '#ffffff',
    accent: '#2563eb',
    radius: '16px',
    shadow: '0 10px 30px rgba(15, 23, 42, 0.08)',
    font: '"Inter", system-ui, sans-serif',
  };

  Object.entries({ ...defaults, ...vars }).forEach(([key, value]) => {
    if (typeof value === 'string') {
      root.style.setProperty(`--${key}`, value);
    }
  });

  root.style.setProperty(
    '--card-border-color',
    template?.stylePreset?.cardBorder ? 'rgba(0,0,0,0.08)' : 'transparent',
  );
  root.dataset.template = template?.id || 'services';
  if (templateName) templateName.textContent = template?.name || templateId || 'Services';
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
  const img = document.createElement('img');
  img.alt = block?.title || 'Hero';
  img.src = block?.imageUrl || '/static/img/home-placeholder.svg';
  visual.appendChild(img);

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

  if (item?.imageUrl) {
    const img = document.createElement('img');
    img.className = 'page-card__image';
    img.src = item.imageUrl;
    img.alt = item.title || 'Изображение';
    card.appendChild(img);
  }

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

function renderHomeBlocks(page, data) {
  if (!homeBlocksContainer) return;
  homeBlocksContainer.innerHTML = '';

  const blocks = Array.isArray(page?.blocks) ? page.blocks : [];
  if (!blocks.length) {
    renderHomeMessage('Главная не настроена');
    return;
  }

  blocks.forEach((block) => {
    if (block?.type === 'hero') {
      homeBlocksContainer.appendChild(buildHeroSection(block));
    }
    if (block?.type === 'cards') {
      homeBlocksContainer.appendChild(buildCardsSection(block, data));
    }
    if (block?.type === 'text') {
      homeBlocksContainer.appendChild(buildTextSection(block));
    }
    if (block?.type === 'social') {
      homeBlocksContainer.appendChild(buildSocialSection(block));
    }
  });
}

function renderHome(data) {
  if (!data?.page) {
    renderHomeMessage('Главная не настроена');
    return;
  }

  console.debug('[site] Loaded home config', data);
  const templateId = data.page?.templateId || 'services';
  applyTemplate(templateId);
  renderHomeBlocks(data.page, data);
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
      try {
        const homeData = await fetchHome();
        renderHome(homeData);
      } catch (error) {
        console.error('Failed to load home', error);
        renderHomeMessage('Не удалось загрузить главную', 'Попробуйте обновить страницу позже.');
      }
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

async function bootstrap() {
  applyTemplate('services');
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
