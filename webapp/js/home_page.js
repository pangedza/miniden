const homePostsSection = document.getElementById('home-posts');
const homePostsGrid = document.getElementById('home-posts-grid');
const homePostsEmpty = document.getElementById('home-posts-empty');
const heroSection = document.querySelector('.lifestyle-hero');
const heroTitle = document.querySelector('.hero-title');
const heroSubtitle = document.querySelector('.hero-subtitle');
const heroButton = document.querySelector('.hero-cta a');
const heroImage = document.querySelector('.hero-visual img');
const tileHomeKids = document.getElementById('tile-home-kids');
const tileProcess = document.getElementById('tile-process');
const tileBaskets = document.getElementById('tile-baskets');
const tileLearning = document.getElementById('tile-learning');
const aboutSection = document.getElementById('story');
const aboutTitle = aboutSection?.querySelector('strong');
const aboutText = aboutSection?.querySelector('p');
const processSection = document.getElementById('process');
const processTitle = processSection?.querySelector('h2');
const processText = processSection?.querySelector('p');
const shopEntry = document.getElementById('shop-entry');
const shopEntryTitle = shopEntry?.querySelector('h3');
const shopEntryText = shopEntry?.querySelector('p');
const shopEntryButton = shopEntry?.querySelector('.btn');
const shopEntryImage = shopEntry?.querySelector('img');
const learningEntry = document.getElementById('learning-entry');
const learningEntryTitle = learningEntry?.querySelector('h3');
const learningEntryText = learningEntry?.querySelector('p');
const learningEntryButton = learningEntry?.querySelector('.btn');
const learningEntryImage = learningEntry?.querySelector('img');
const loginSection = document.getElementById('telegram-login-section');
const authStatusSection = document.getElementById('auth-status');

const HOME_PLACEHOLDER = '/static/img/home-placeholder.svg';
const DEBUG_HOME_IMAGES =
  Boolean(window?.MINIDEN_DEBUG_HOME_IMAGES) || localStorage?.getItem('miniden.debug_home_images') === '1';

const GRADIENT_PLACEHOLDER =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stop-color="%23f3e7e9"/><stop offset="100%" stop-color="%23e3eeff"/></linearGradient></defs><rect width="800" height="500" fill="url(%23g)"/></svg>';

const DEFAULT_BLOCKS = [
  {
    block_key: 'hero_main',
    title: 'Дом, который вяжется руками',
    subtitle: 'Miniden • домашнее вязание',
    body: 'Мини-истории о корзинках, детских комнатах и спокойных вечерах. Всё, что делаю — про уют, семью и обучение без спешки.',
    button_text: 'Узнать историю',
    button_url: '#story',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 10,
  },
  {
    block_key: 'tile_home_kids',
    title: 'Дом и дети',
    body: 'Тёплые вещи для дома',
    button_url: '/products',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 20,
  },
  {
    block_key: 'tile_process',
    title: 'Процесс',
    body: 'От пряжи до упаковки',
    button_url: '/masterclasses',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 21,
  },
  {
    block_key: 'tile_baskets',
    title: 'Мои корзинки',
    body: 'Корзинки и наборы',
    button_url: '/products',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 22,
  },
  {
    block_key: 'tile_learning',
    title: 'Обучение',
    body: 'Начните с нуля',
    button_url: '/masterclasses',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 23,
  },
  {
    block_key: 'about_short',
    title: 'Немного обо мне',
    body: 'Я вяжу дома. Учу так, как училась сама: без спешки, в тишине и с акцентом на уютные вещи для семьи.',
    is_active: true,
    order: 30,
  },
  {
    block_key: 'process_text',
    title: 'Процесс',
    body: 'От выбора пряжи до упаковки — всё делаю сама, небольшими партиями и с вниманием к мелочам.',
    is_active: true,
    order: 40,
  },
  {
    block_key: 'shop_entry',
    title: 'Корзинки и наборы',
    body: 'Небольшие вещи, которые собирают дом воедино.',
    button_text: 'Перейти в каталог',
    button_url: '/products',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 50,
  },
  {
    block_key: 'learning_entry',
    title: 'Мастер-классы',
    body: 'Простые шаги, поддержка и вдохновение, чтобы связать своё первое изделие.',
    button_text: 'Смотреть обучение',
    button_url: '/masterclasses',
    image_url: HOME_PLACEHOLDER,
    is_active: true,
    order: 60,
  },
];

function normalizeBlock(raw) {
  if (!raw) return null;
  const order = Number.isFinite(raw.order)
    ? raw.order
    : Number.isFinite(raw.sort_order)
      ? raw.sort_order
      : 0;
  const image_url = raw.image_url_with_version
    ? safeUrl(raw.image_url_with_version, '')
    : applyCacheBust(raw.image_url, raw.image_version);
  return {
    ...raw,
    block_key: raw.block_key,
    title: raw.title,
    subtitle: raw.subtitle ?? raw.body ?? '',
    body: raw.body ?? raw.subtitle ?? '',
    button_text: raw.button_text,
    button_url: raw.button_url || raw.button_link || raw.buttonHref,
    image_url,
    image_url_with_version: image_url,
    image_version: raw.image_version,
    is_active: raw.is_active !== false,
    order,
  };
}

function safeUrl(url, fallback) {
  if (!url || typeof url !== 'string') return fallback;
  const trimmed = url.trim();
  if (!trimmed) return fallback;
  if (trimmed.startsWith('http://')) {
    return trimmed.replace('http://', 'https://');
  }
  if (trimmed.startsWith('https://') || trimmed.startsWith('http://')) return trimmed;
  if (trimmed.startsWith('/') || trimmed.startsWith('data:')) return trimmed;
  return fallback || trimmed;
}

function applyCacheBust(url, version) {
  const normalized = safeUrl(url, '');
  if (!normalized) return '';
  if (!version) return normalized;
  const separator = normalized.includes('?') ? '&' : '?';
  return `${normalized}${separator}v=${version}`;
}

function applyImageWithFallback(img, url) {
  if (!img) return;
  const fallback = safeUrl(img.dataset?.fallback, HOME_PLACEHOLDER) || HOME_PLACEHOLDER;
  const fallbackWithGradient = safeUrl(fallback, GRADIENT_PLACEHOLDER) || GRADIENT_PLACEHOLDER;
  img.onerror = () => {
    img.onerror = null;
    img.src = fallbackWithGradient;
    img.classList.add('image-fallback');
  };
  const resolvedUrl = safeUrl(url, fallbackWithGradient) || fallbackWithGradient;
  img.src = resolvedUrl;
  img.loading = 'lazy';
  if (DEBUG_HOME_IMAGES) {
    console.debug('[home:image]', img.alt || img.id || 'image', '=>', resolvedUrl);
  }
}

function applyBlockOrder(element, orderValue) {
  if (!element) return;
  const value = Number.isFinite(orderValue) ? orderValue : 0;
  element.style.order = String(value);
}

function applyHero(block) {
  if (!heroSection) return;
  heroSection.style.display = block?.is_active === false ? 'none' : '';
  if (block?.title && heroTitle) heroTitle.textContent = block.title;
  if (heroSubtitle) heroSubtitle.textContent = block?.subtitle || block?.body || heroSubtitle.textContent;
  if (heroButton) {
    heroButton.textContent = block?.button_text || 'Подробнее';
    heroButton.href = block?.button_url || heroButton.getAttribute('href') || '#story';
  }
  if (heroImage) {
    applyImageWithFallback(heroImage, block?.image_url || HOME_PLACEHOLDER);
    heroImage.alt = block?.title || 'Главный баннер';
  }
  applyBlockOrder(heroSection, block?.order);
}

function applyTile(tileEl, block) {
  if (!tileEl || !block) return;
  tileEl.style.display = block.is_active === false ? 'none' : '';
  const label = tileEl.querySelector('span');
  if (label && block.title) label.textContent = block.title;
  const img = tileEl.querySelector('img');
  if (img) {
    applyImageWithFallback(img, block.image_url || HOME_PLACEHOLDER);
    img.alt = block.title || img.alt || 'Плитка';
  }
  if (block.button_url) tileEl.href = block.button_url;
  applyBlockOrder(tileEl, block.order);
}

function applyAbout(block) {
  if (!aboutSection) return;
  aboutSection.style.display = block?.is_active === false ? 'none' : '';
  if (aboutTitle && block?.title) aboutTitle.textContent = block.title;
  if (aboutText && (block?.body || block?.subtitle)) {
    aboutText.textContent = block.body || block.subtitle || aboutText.textContent;
  }
  applyBlockOrder(aboutSection, block?.order);
}

function applyProcess(block) {
  if (!processSection) return;
  processSection.style.display = block?.is_active === false ? 'none' : '';
  if (processTitle && block?.title) processTitle.textContent = block.title;
  if (processText && (block?.body || block?.subtitle)) {
    processText.textContent = block.body || block.subtitle || processText.textContent;
  }
  applyBlockOrder(processSection, block?.order);
}

function applyCta(section, block) {
  if (!section || !block) return;
  section.style.display = block.is_active === false ? 'none' : '';
  const titleEl = section.querySelector('h3');
  const textEl = section.querySelector('p');
  const buttonEl = section.querySelector('.btn');
  const imageEl = section.querySelector('img');

  if (titleEl && block.title) titleEl.textContent = block.title;
  if (textEl && (block.body || block.subtitle)) {
    textEl.textContent = block.body || block.subtitle || textEl.textContent;
  }
  if (buttonEl) {
    buttonEl.textContent = block.button_text || buttonEl.textContent;
    if (block.button_url) buttonEl.href = block.button_url;
  }
  if (imageEl) {
    applyImageWithFallback(imageEl, block.image_url || HOME_PLACEHOLDER);
    imageEl.alt = block.title || imageEl.alt || '';
  }
  applyBlockOrder(section, block.order);
}

function buildBlockMap(items) {
  const map = new Map(DEFAULT_BLOCKS.map((item) => [item.block_key, { ...item }]));
  (items || []).forEach((block) => {
    const normalized = normalizeBlock(block);
    if (!normalized || !normalized.block_key) return;
    const existing = map.get(normalized.block_key) || {};
    map.set(normalized.block_key, { ...existing, ...normalized });
  });
  return map;
}

function applyBlocks(blocks) {
  const data = buildBlockMap(blocks);
  applyHero(data.get('hero_main'));
  applyTile(tileHomeKids, data.get('tile_home_kids'));
  applyTile(tileProcess, data.get('tile_process'));
  applyTile(tileBaskets, data.get('tile_baskets'));
  applyTile(tileLearning, data.get('tile_learning'));
  applyAbout(data.get('about_short'));
  applyProcess(data.get('process_text'));
  applyCta(shopEntry, data.get('shop_entry'));
  applyCta(learningEntry, data.get('learning_entry'));
  initRevealOnScroll();
}

function renderPosts(posts) {
  if (!homePostsSection || !homePostsGrid || !homePostsEmpty) return;
  if (!posts || !posts.length) {
    homePostsGrid.innerHTML = '';
    homePostsSection.style.display = 'block';
    homePostsEmpty.style.display = 'block';
    initRevealOnScroll();
    return;
  }

  const items = posts.slice(0, 4);
  homePostsGrid.innerHTML = '';
  items.forEach((post) => {
    const card = document.createElement('div');
    card.className = 'card home-post-card hover-lift reveal';
    card.innerHTML = `
      <h3>${post.title}</h3>
      <p>${post.short_text}</p>
      ${post.link ? `<a class="btn secondary" href="${post.link}" target="_blank" rel="noopener">Подробнее</a>` : ''}
    `;
    homePostsGrid.appendChild(card);
  });
  homePostsEmpty.style.display = 'none';
  homePostsSection.style.display = 'block';
  initRevealOnScroll();
}

function initRevealOnScroll() {
  const elements = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window) || !elements.length) {
    elements.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.2,
      rootMargin: '0px 0px -40px 0px',
    }
  );

  elements.forEach((el) => observer.observe(el));
}

async function loadHomeData() {
  let blocksLoaded = false;

  try {
    const blocksRes = await apiGet('/homepage/blocks');
    applyBlocks(blocksRes?.items || blocksRes || []);
    blocksLoaded = true;
  } catch (e) {
    console.warn('Не удалось загрузить блоки главной страницы', e);
    applyBlocks(DEFAULT_BLOCKS);
  }

  try {
    const data = await apiGet('/home');
    if (data?.posts) renderPosts(data.posts);
  } catch (e) {
    console.warn('Не удалось загрузить посты главной страницы', e);
    if (!blocksLoaded) {
      applyBlocks(DEFAULT_BLOCKS);
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initRevealOnScroll();
  if (homePostsSection) homePostsSection.style.order = '70';
  if (loginSection) loginSection.style.order = '80';
  if (authStatusSection) authStatusSection.style.order = '81';
  loadHomeData();
});
