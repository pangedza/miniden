(function () {
  const page = document.querySelector('[data-shop-page]');
  if (!page) return;

  const type = page.dataset.shopType === 'course' ? 'course' : 'product';
  const isCourse = type === 'course';

  const titleEl = document.getElementById('category-title');
  const descriptionEl = document.getElementById('category-description');
  const gridEl = document.getElementById('items-grid');
  const loadingEl = document.getElementById('page-loading');
  const emptyEl = document.getElementById('empty-state');
  const errorEl = document.getElementById('error-state');
  const actionBarEl = document.getElementById('action-bar');
  const actionBtn = document.getElementById('action-button');
  const selectedCountEl = document.getElementById('selected-count');

  const quantities = new Map();
  let settings = { action_enabled: true, action_label: null, min_selected: 0 };
  let category = null;

  function getCategorySlug() {
    const url = new URL(window.location.href);
    const byQuery = url.searchParams.get('category') || url.searchParams.get('slug');
    if (byQuery) return byQuery;

    const parts = window.location.pathname.split('/').filter(Boolean);
    const anchor = isCourse ? 'courses' : 'products';
    const anchorIndex = parts.lastIndexOf(anchor);
    if (anchorIndex !== -1 && parts.length > anchorIndex + 1) {
      const slugParts = parts.slice(anchorIndex + 1);
      return slugParts.join('/').replace(/\.html?$/i, '');
    }

    return null;
  }

  function formatPrice(value) {
    const num = Number(value) || 0;
    if (num === 0) return 'Бесплатно';
    return `${num.toLocaleString('ru-RU')} ₽`;
  }

  function updateSelectedCount() {
    const total = Array.from(quantities.values()).reduce((acc, value) => acc + value, 0);
    selectedCountEl.textContent = total;

    const minRequired = settings?.min_selected ?? 0;
    const enabledByAdmin = settings?.action_enabled !== false;
    const meetsMin = total >= minRequired;

    actionBtn.disabled = !enabledByAdmin || !meetsMin;
  }

  function buildCard(item) {
    const card = document.createElement('article');
    card.className = 'telegram-shop__card';

    const imageWrapper = document.createElement('div');
    imageWrapper.className = 'telegram-shop__card-image';
    if (item.image_url) {
      const img = document.createElement('img');
      img.src = item.image_url;
      img.alt = item.title || 'Изображение';
      imageWrapper.appendChild(img);
    }

    const body = document.createElement('div');
    body.className = 'telegram-shop__card-body';

    const title = document.createElement('h3');
    title.className = 'telegram-shop__card-title';
    title.textContent = item.title || 'Без названия';

    const text = document.createElement('p');
    text.className = 'telegram-shop__card-text';
    text.textContent = item.short_text || '';

    const footer = document.createElement('div');
    footer.className = 'telegram-shop__card-footer';

    const price = document.createElement('div');
    price.className = 'telegram-shop__price';
    price.textContent = formatPrice(item.price);

    const qtyBadge = document.createElement('div');
    qtyBadge.className = 'telegram-shop__qty-badge';
    qtyBadge.dataset.itemId = String(item.id);
    qtyBadge.textContent = '0';

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'telegram-shop__qty-btn';
    addBtn.textContent = '+';
    addBtn.addEventListener('click', () => {
      const current = quantities.get(item.id) || 0;
      const next = current + 1;
      quantities.set(item.id, next);
      qtyBadge.textContent = String(next);
      updateSelectedCount();
    });

    const controls = document.createElement('div');
    controls.style.display = 'flex';
    controls.style.alignItems = 'center';
    controls.style.gap = '10px';
    controls.append(qtyBadge, addBtn);

    footer.append(price, controls);
    body.append(title, text, footer);
    card.append(imageWrapper, body);
    return card;
  }

  function renderItems(items) {
    loadingEl?.setAttribute('hidden', '');
    errorEl?.setAttribute('hidden', '');
    gridEl.innerHTML = '';

    if (!items || !items.length) {
      gridEl.setAttribute('hidden', '');
      emptyEl?.removeAttribute('hidden');
      actionBarEl?.setAttribute('hidden', '');
      return;
    }

    emptyEl?.setAttribute('hidden', '');
    gridEl.removeAttribute('hidden');
    actionBarEl?.removeAttribute('hidden');

    items.forEach((item) => {
      quantities.set(item.id, 0);
      gridEl.appendChild(buildCard(item));
    });

    updateSelectedCount();
  }

  function showError(message) {
    loadingEl?.setAttribute('hidden', '');
    emptyEl?.setAttribute('hidden', '');
    gridEl?.setAttribute('hidden', '');
    if (errorEl) {
      errorEl.textContent = message || 'Не удалось загрузить данные';
      errorEl.removeAttribute('hidden');
    }
  }

  function applySettings(nextSettings) {
    settings = {
      action_enabled: nextSettings?.action_enabled !== false,
      action_label: nextSettings?.action_label || null,
      min_selected: Number.isFinite(nextSettings?.min_selected)
        ? nextSettings.min_selected
        : 0,
    };

    actionBtn.textContent = settings.action_label || 'Продолжить';
    updateSelectedCount();
  }

  async function loadSettings(categoryId) {
    try {
      const data = await apiGet('/adminsite/webapp-settings', {
        type,
        category_id: categoryId,
      });
      applySettings(data);
    } catch (error) {
      console.warn('Failed to load webapp settings, using defaults', error);
      applySettings(settings);
    }
  }

  async function loadCategory(slug) {
    const categories = await apiGet('/adminsite/categories', { type });
    const found = (categories || []).find((item) => item.slug === slug);
    if (!found) {
      const err = new Error('Категория не найдена');
      err.status = 404;
      throw err;
    }
    return found;
  }

  async function loadItems(categoryId) {
    return apiGet('/adminsite/items', { type, category_id: categoryId });
  }

  async function loadPage() {
    const slug = getCategorySlug();
    if (!slug) {
      showError('Не удалось определить категорию из адреса страницы.');
      return;
    }

    try {
      loadingEl?.removeAttribute('hidden');
      category = await loadCategory(slug);
      titleEl.textContent = category.title || 'Категория';
      descriptionEl.textContent = category.description || 'Выберите понравившиеся позиции';

      await loadSettings(category.id);
      const items = await loadItems(category.id);
      renderItems(items || []);
    } catch (error) {
      console.error('Failed to load webapp catalog page', error);
      showError(error?.message || 'Произошла ошибка при загрузке каталога');
    }
  }

  actionBtn?.addEventListener('click', () => {
    const total = Array.from(quantities.values()).reduce((sum, qty) => sum + qty, 0);
    const minRequired = settings?.min_selected ?? 0;
    if (total < minRequired) return;

    const payload = {
      source: 'adminsite',
      type,
      categorySlug: getCategorySlug(),
      items: Array.from(quantities.entries())
        .filter(([, qty]) => qty > 0)
        .map(([id, qty]) => ({ id, qty })),
    };

    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.sendData(JSON.stringify(payload));
      window.Telegram.WebApp.close();
    } else {
      showToast('Откройте страницу через Telegram');
    }
  });

  loadPage();
})();
