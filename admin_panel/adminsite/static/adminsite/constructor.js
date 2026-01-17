import { apiRequest } from './apiClient.js';

const statusMenu = document.getElementById('status-menu');
const statusSettings = document.getElementById('status-settings');
const statusMedia = document.getElementById('status-media');
const globalStatus = document.getElementById('global-status');

const categoryList = document.getElementById('category-list');
const categoryForm = document.getElementById('category-form');
const categoryAdd = document.getElementById('category-add');
const itemList = document.getElementById('item-list');
const itemForm = document.getElementById('item-form');
const itemAdd = document.getElementById('item-add');
const itemsCaption = document.getElementById('items-caption');
const menuRefresh = document.getElementById('menu-refresh');

const settingsSave = document.getElementById('settings-save');
const settingsBrand = document.getElementById('settings-brand');
const settingsLogo = document.getElementById('settings-logo');
const settingsPrimary = document.getElementById('settings-primary');
const settingsSecondary = document.getElementById('settings-secondary');
const settingsBackground = document.getElementById('settings-background');
const settingsHeroTitle = document.getElementById('settings-hero-title');
const settingsHeroSubtitle = document.getElementById('settings-hero-subtitle');
const settingsHeroImage = document.getElementById('settings-hero-image');
const settingsContacts = document.getElementById('settings-contacts');
const settingsSocial = document.getElementById('settings-social');

const mediaUploadInput = document.getElementById('media-upload-input');
const mediaUploadBtn = document.getElementById('media-upload-btn');
const mediaRefreshBtn = document.getElementById('media-refresh');
const mediaSearch = document.getElementById('media-search');
const mediaList = document.getElementById('media-list');
const mediaUploadStatus = document.getElementById('media-upload-status');

const panelTabs = document.querySelectorAll('[data-panel]');
const panels = document.querySelectorAll('.panel');

const API_MENU_CATEGORIES = '/api/admin/menu/categories';
const API_MENU_ITEMS = '/api/admin/menu/items';
const API_MENU_REORDER = '/api/admin/menu/reorder';
const API_SITE_SETTINGS = '/api/admin/site-settings';
const API_MEDIA = '/api/adminsite/media';
const API_MEDIA_UPLOAD = '/api/adminsite/media/upload';

let categories = [];
let items = [];
let selectedCategory = null;
let activeItemType = null;
let activeItemLabel = null;
let activeUrlType = null;

const TYPE_LABELS = {
  product: 'Товары',
  masterclass: 'Мастер-классы',
};

const URL_TYPE_DEFAULT = 'products';
const URL_TYPE_CONFIG = {
  products: { itemType: 'product', label: 'Товары' },
  masterclasses: { itemType: 'masterclass', label: 'Мастер-классы' },
  courses: { itemType: 'masterclass', label: 'Курсы' },
};

const SECTION_CONFIG = {
  products: { panel: 'panel-menu', type: 'product', label: 'Товары' },
  categories: { panel: 'panel-menu', type: null },
  courses: { panel: 'panel-menu', type: 'masterclass', label: 'Мастер-классы' },
  masterclasses: { panel: 'panel-menu', type: 'masterclass', label: 'Мастер-классы' },
  home: { panel: 'panel-settings', type: null },
  menu: { panel: 'panel-menu', type: null },
};

function setStatus(target, message = '', tone = 'muted') {
  if (!target) return;
  target.textContent = message;
  target.className = `status ${tone}`.trim();
}

function setActivePanel(panelId) {
  panels.forEach((panel) => {
    panel.classList.toggle('active', panel.id === panelId);
  });
  panelTabs.forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.panel === panelId);
  });
}

function resolveUrlType(value) {
  if (value && URL_TYPE_CONFIG[value]) {
    return value;
  }
  return URL_TYPE_DEFAULT;
}

function getUrlTypeConfig() {
  const params = new URLSearchParams(window.location.search);
  const urlType = resolveUrlType(params.get('type'));
  return { urlType, ...URL_TYPE_CONFIG[urlType] };
}

function resetMenuState() {
  selectedCategory = null;
  items = [];
  categories = [];
  renderCategories();
  renderItems();
}

function setActiveItemType(type, label) {
  activeItemType = type || null;
  activeItemLabel = label || (activeItemType ? TYPE_LABELS[activeItemType] || activeItemType : null);
  if (selectedCategory) {
    loadItems(selectedCategory.id);
  } else {
    renderItems();
  }
}

function applySectionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const section = params.get('section') || 'menu';
  const config = SECTION_CONFIG[section] || SECTION_CONFIG.menu;
  if (config?.panel) {
    setActivePanel(config.panel);
  }
  const { urlType, itemType, label } = getUrlTypeConfig();
  const typeChanged = activeUrlType !== urlType;
  activeUrlType = urlType;
  setActiveItemType(itemType ?? config?.type ?? null, label ?? config?.label ?? null);
  if (typeChanged) {
    resetMenuState();
  }
  return typeChanged;
}

function parseJsonInput(value, fallback = {}) {
  if (!value || !value.trim()) return fallback;
  return JSON.parse(value);
}

function parseImages(value) {
  if (!value) return [];
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function copyToClipboard(value) {
  if (!value) return false;
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch (error) {
    console.warn('Clipboard API недоступен', error);
    return false;
  }
}

function buildRow({
  title,
  subtitle,
  meta,
  isActive,
  onSelect,
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  linkUrl,
  selectLabel = 'Выбрать',
}) {
  const row = document.createElement('div');
  row.className = 'block-row';

  const main = document.createElement('div');
  const heading = document.createElement('div');
  heading.textContent = title || 'Без названия';
  heading.style.fontWeight = '700';
  const sub = document.createElement('div');
  sub.className = 'muted meta';
  sub.textContent = subtitle || meta || '';
  main.append(heading, sub);

  if (linkUrl) {
    const linkRow = document.createElement('div');
    linkRow.className = 'muted meta';
    const link = document.createElement('a');
    link.href = linkUrl;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = linkUrl;
    linkRow.appendChild(link);
    main.appendChild(linkRow);
  }

  const actions = document.createElement('div');
  actions.className = 'actions';

  if (onSelect) {
    const selectButton = document.createElement('button');
    selectButton.className = 'btn-secondary';
    selectButton.type = 'button';
    selectButton.textContent = selectLabel;
    selectButton.addEventListener('click', onSelect);
    actions.appendChild(selectButton);
  }

  const editButton = document.createElement('button');
  editButton.className = 'btn-secondary';
  editButton.type = 'button';
  editButton.textContent = 'Редактировать';
  editButton.addEventListener('click', onEdit);

  const upButton = document.createElement('button');
  upButton.className = 'btn-ghost';
  upButton.type = 'button';
  upButton.textContent = '↑';
  upButton.addEventListener('click', onMoveUp);

  const downButton = document.createElement('button');
  downButton.className = 'btn-ghost';
  downButton.type = 'button';
  downButton.textContent = '↓';
  downButton.addEventListener('click', onMoveDown);

  if (linkUrl) {
    const openLinkButton = document.createElement('button');
    openLinkButton.className = 'btn-secondary';
    openLinkButton.type = 'button';
    openLinkButton.textContent = 'Открыть';
    openLinkButton.addEventListener('click', () => {
      window.open(linkUrl, '_blank', 'noopener');
    });

    const copyButton = document.createElement('button');
    copyButton.className = 'btn-ghost';
    copyButton.type = 'button';
    copyButton.textContent = 'Копировать';
    copyButton.addEventListener('click', async () => {
      const copied = await copyToClipboard(linkUrl);
      if (copied) {
        setStatus(globalStatus, 'Ссылка скопирована', 'ok');
      } else {
        setStatus(globalStatus, 'Не удалось скопировать ссылку', 'error');
      }
    });

    actions.append(openLinkButton, copyButton);
  }

  const deleteButton = document.createElement('button');
  deleteButton.className = 'btn-danger';
  deleteButton.type = 'button';
  deleteButton.textContent = 'Удалить';
  deleteButton.addEventListener('click', onDelete);

  if (isActive === false) {
    row.classList.add('is-muted');
  }

  actions.append(editButton, upButton, downButton, deleteButton);
  row.append(main, actions);
  return row;
}

function renderCategoryForm(category = null) {
  if (!categoryForm) return;
  categoryForm.style.display = 'block';
  categoryForm.innerHTML = `
    <label>Название<input id="category-title" /></label>
    <label>Slug<input id="category-slug" placeholder="optional" /></label>
    <label>Описание<textarea id="category-description" rows="2"></textarea></label>
    <label>Тип<select id="category-type">
      <option value="product">Товары</option>
      <option value="masterclass">Мастер-классы</option>
    </select></label>
    <label>Родительская категория<select id="category-parent"></select></label>
    <label>Порядок<input id="category-order" type="number" value="0" /></label>
    <label><input id="category-active" type="checkbox" /> Активна</label>
    <div class="actions">
      <button class="btn-primary" type="button" id="category-save">Сохранить</button>
      <button class="btn-ghost" type="button" id="category-cancel">Отмена</button>
    </div>
  `;

  const titleInput = document.getElementById('category-title');
  const slugInput = document.getElementById('category-slug');
  const descriptionInput = document.getElementById('category-description');
  const typeInput = document.getElementById('category-type');
  const parentInput = document.getElementById('category-parent');
  const orderInput = document.getElementById('category-order');
  const activeInput = document.getElementById('category-active');

  const renderParentOptions = (typeValue, selectedParentId = null) => {
    parentInput.innerHTML = '<option value="">Без родителя</option>';
    categories
      .filter((entry) => entry.type === typeValue && entry.id !== category?.id)
      .forEach((entry) => {
        const option = document.createElement('option');
        option.value = String(entry.id);
        option.textContent = entry.title;
        if (selectedParentId && Number(selectedParentId) === entry.id) {
          option.selected = true;
        }
        parentInput.appendChild(option);
      });
  };

  titleInput.value = category?.title || '';
  slugInput.value = category?.slug || '';
  descriptionInput.value = category?.description || '';
  typeInput.value = category?.type || activeItemType || 'product';
  orderInput.value = category?.order_index ?? 0;
  activeInput.checked = category?.is_active ?? true;
  renderParentOptions(typeInput.value, category?.parent_id ?? null);

  typeInput.addEventListener('change', () => {
    renderParentOptions(typeInput.value);
  });

  document.getElementById('category-cancel').addEventListener('click', () => {
    categoryForm.style.display = 'none';
    categoryForm.innerHTML = '';
  });

  document.getElementById('category-save').addEventListener('click', async () => {
    try {
      const payload = {
        title: titleInput.value.trim(),
        slug: slugInput.value.trim() || null,
        description: descriptionInput.value.trim() || null,
        type: typeInput.value,
        parent_id: parentInput.value ? Number(parentInput.value) : null,
        order_index: Number(orderInput.value || 0),
        is_active: activeInput.checked,
      };

      if (!payload.title) {
        setStatus(statusMenu, 'Название категории обязательно', 'error');
        return;
      }

      if (category?.id) {
        await apiRequest(`${API_MENU_CATEGORIES}/${category.id}`, { method: 'PUT', body: payload });
      } else {
        await apiRequest(API_MENU_CATEGORIES, { method: 'POST', body: payload });
      }

      setStatus(statusMenu, 'Категория сохранена', 'ok');
      categoryForm.style.display = 'none';
      categoryForm.innerHTML = '';
      await loadCategories();
    } catch (error) {
      setStatus(statusMenu, error.message || 'Не удалось сохранить категорию', 'error');
    }
  });
}

function renderItemForm(item = null) {
  if (!itemForm) return;
  if (!selectedCategory) {
    setStatus(statusMenu, 'Сначала выберите категорию', 'error');
    return;
  }

  itemForm.style.display = 'block';
  itemForm.innerHTML = `
    <label>Название<input id="item-title" /></label>
    <label>Подзаголовок<input id="item-subtitle" /></label>
    <label>Slug<input id="item-slug" placeholder="optional" /></label>
    <label>Описание<textarea id="item-description" rows="3"></textarea></label>
    <label>Цена<input id="item-price" type="number" min="0" step="0.01" /></label>
    <label>Валюта<input id="item-currency" placeholder="RUB" /></label>
    <label>Тип<select id="item-type">
      <option value="product">product</option>
      <option value="masterclass">masterclass</option>
    </select></label>
    <label>Остаток<input id="item-stock" type="number" min="0" step="1" placeholder="не учитывать" /></label>
    <label>Image URL<input id="item-image" placeholder="/media/adminsite/..." /></label>
    <label>Images (через запятую или новую строку)<textarea id="item-images" rows="2"></textarea></label>
    <label>Meta (JSON)<textarea id="item-meta" rows="3"></textarea></label>
    <label>Порядок<input id="item-order" type="number" value="0" /></label>
    <label><input id="item-active" type="checkbox" /> Активна</label>
    <div class="actions">
      <button class="btn-primary" type="button" id="item-save">Сохранить</button>
      <button class="btn-ghost" type="button" id="item-cancel">Отмена</button>
    </div>
  `;

  const titleInput = document.getElementById('item-title');
  const subtitleInput = document.getElementById('item-subtitle');
  const slugInput = document.getElementById('item-slug');
  const descriptionInput = document.getElementById('item-description');
  const priceInput = document.getElementById('item-price');
  const currencyInput = document.getElementById('item-currency');
  const typeInput = document.getElementById('item-type');
  const stockInput = document.getElementById('item-stock');
  const imageInput = document.getElementById('item-image');
  const imagesInput = document.getElementById('item-images');
  const metaInput = document.getElementById('item-meta');
  const orderInput = document.getElementById('item-order');
  const activeInput = document.getElementById('item-active');

  titleInput.value = item?.title || '';
  subtitleInput.value = item?.subtitle || '';
  slugInput.value = item?.slug || '';
  descriptionInput.value = item?.description || '';
  priceInput.value = item?.price ?? '';
  currencyInput.value = item?.currency || '';
  typeInput.value = item?.type || selectedCategory?.type || activeItemType || 'product';
  typeInput.disabled = Boolean(selectedCategory?.type);
  stockInput.value = item?.stock_qty ?? '';
  imageInput.value = item?.image_url || '';
  imagesInput.value = (item?.images || []).join('\n');
  metaInput.value = item?.meta ? JSON.stringify(item.meta, null, 2) : '';
  orderInput.value = item?.order_index ?? 0;
  activeInput.checked = item?.is_active ?? true;

  document.getElementById('item-cancel').addEventListener('click', () => {
    itemForm.style.display = 'none';
    itemForm.innerHTML = '';
  });

  document.getElementById('item-save').addEventListener('click', async () => {
    try {
      const payload = {
        category_id: selectedCategory.id,
        title: titleInput.value.trim(),
        subtitle: subtitleInput.value.trim() || null,
        slug: slugInput.value.trim() || null,
        description: descriptionInput.value.trim() || null,
        price: priceInput.value ? Number(priceInput.value) : null,
        currency: currencyInput.value.trim() || null,
        type: typeInput.value,
        stock_qty: stockInput.value !== '' ? Number(stockInput.value) : null,
        image_url: imageInput.value.trim() || null,
        images: parseImages(imagesInput.value),
        meta: parseJsonInput(metaInput.value, {}),
        order_index: Number(orderInput.value || 0),
        is_active: activeInput.checked,
      };

      if (!payload.title) {
        setStatus(statusMenu, 'Название позиции обязательно', 'error');
        return;
      }

      if (item?.id) {
        await apiRequest(`${API_MENU_ITEMS}/${item.id}`, { method: 'PUT', body: payload });
      } else {
        await apiRequest(API_MENU_ITEMS, { method: 'POST', body: payload });
      }

      setStatus(statusMenu, 'Позиция сохранена', 'ok');
      itemForm.style.display = 'none';
      itemForm.innerHTML = '';
      await loadItems(selectedCategory.id);
    } catch (error) {
      setStatus(statusMenu, error.message || 'Не удалось сохранить позицию', 'error');
    }
  });
}

function renderCategories() {
  if (!categoryList) return;
  categoryList.innerHTML = '';
  if (!categories.length) {
    categoryList.innerHTML = '<p class="muted">Категории не созданы.</p>';
    return;
  }

  categories.forEach((category, index) => {
    const typeLabel = TYPE_LABELS[category.type] || category.type || '';
    const metaParts = [];
    if (typeLabel) metaParts.push(typeLabel);
    if (category.description) metaParts.push(category.description);
    const row = buildRow({
      title: category.title,
      subtitle: category.slug,
      meta: metaParts.join(' • '),
      isActive: category.is_active,
      onSelect: () => {
        selectedCategory = category;
        renderCategories();
        loadItems(category.id);
      },
      selectLabel: 'Позиции',
      linkUrl: category.public_url || (category.slug ? `/c/${category.slug}` : null),
      onEdit: () => renderCategoryForm(category),
      onDelete: async () => {
        if (!confirm('Удалить категорию?')) return;
        try {
          await apiRequest(`${API_MENU_CATEGORIES}/${category.id}`, { method: 'DELETE' });
          setStatus(statusMenu, 'Категория удалена', 'ok');
          await loadCategories();
        } catch (error) {
          setStatus(statusMenu, error.message || 'Не удалось удалить категорию', 'error');
        }
      },
      onMoveUp: () => reorderCategory(index, -1),
      onMoveDown: () => reorderCategory(index, 1),
    });

    if (selectedCategory?.id === category.id) {
      row.classList.add('active');
    }
    categoryList.appendChild(row);
  });
}

function renderItems() {
  if (!itemList) return;
  itemList.innerHTML = '';
  if (!selectedCategory) {
    itemsCaption.textContent = 'Выберите категорию слева.';
    return;
  }
  const labelSuffix = selectedCategory?.type ? ` • ${TYPE_LABELS[selectedCategory.type] || selectedCategory.type}` : '';
  itemsCaption.textContent = `Категория: ${selectedCategory.title}${labelSuffix}`;

  if (!items.length) {
    itemList.innerHTML = '<p class="muted">В категории пока нет позиций.</p>';
    return;
  }

  items.forEach((item, index) => {
    const typeLabel = TYPE_LABELS[item.type] || item.type || '';
    const stockLabel = item.stock_qty === null || item.stock_qty === undefined ? 'без учета остатка' : `остаток: ${item.stock_qty}`;
    const row = buildRow({
      title: item.title,
      subtitle: item.slug,
      meta: [typeLabel, stockLabel].filter(Boolean).join(' • '),
      isActive: item.is_active,
      linkUrl: item.public_url || (item.id ? `/i/${item.id}` : null),
      onEdit: () => renderItemForm(item),
      onDelete: async () => {
        if (!confirm('Удалить позицию?')) return;
        try {
          await apiRequest(`${API_MENU_ITEMS}/${item.id}`, { method: 'DELETE' });
          setStatus(statusMenu, 'Позиция удалена', 'ok');
          await loadItems(selectedCategory.id);
        } catch (error) {
          setStatus(statusMenu, error.message || 'Не удалось удалить позицию', 'error');
        }
      },
      onMoveUp: () => reorderItem(index, -1),
      onMoveDown: () => reorderItem(index, 1),
    });
    itemList.appendChild(row);
  });
}

async function reorderCategory(index, delta) {
  const targetIndex = index + delta;
  if (targetIndex < 0 || targetIndex >= categories.length) return;
  const next = [...categories];
  [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
  categories = next.map((category, idx) => ({ ...category, order_index: idx }));
  renderCategories();
  await apiRequest(API_MENU_REORDER, {
    method: 'POST',
    body: { categories: categories.map((category) => ({ id: category.id, order_index: category.order_index })) },
  });
}

async function reorderItem(index, delta) {
  const targetIndex = index + delta;
  if (targetIndex < 0 || targetIndex >= items.length) return;
  const next = [...items];
  [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
  items = next.map((item, idx) => ({ ...item, order_index: idx }));
  renderItems();
  await apiRequest(API_MENU_REORDER, {
    method: 'POST',
    body: { items: items.map((entry) => ({ id: entry.id, order_index: entry.order_index })) },
  });
}

async function loadCategories() {
  try {
    const typeParam = activeUrlType ? `?type=${encodeURIComponent(activeUrlType)}` : '';
    const response = await apiRequest(`${API_MENU_CATEGORIES}${typeParam}`, { method: 'GET' });
    categories = response.items || [];
    if (selectedCategory) {
      selectedCategory = categories.find((cat) => cat.id === selectedCategory.id) || null;
    }
    renderCategories();
    if (selectedCategory) {
      await loadItems(selectedCategory.id);
    }
  } catch (error) {
    setStatus(statusMenu, error.message || 'Не удалось загрузить категории', 'error');
  }
}

async function loadItems(categoryId) {
  if (!categoryId) return;
  try {
    const typeValue = activeItemType || selectedCategory?.type || '';
    const typeParam = typeValue ? `&type=${encodeURIComponent(typeValue)}` : '';
    const response = await apiRequest(
      `${API_MENU_ITEMS}?category_id=${categoryId}${typeParam}&include_inactive=true`,
      { method: 'GET' }
    );
    items = response.items || [];
    renderItems();
  } catch (error) {
    setStatus(statusMenu, error.message || 'Не удалось загрузить позиции', 'error');
  }
}

async function loadSettings() {
  try {
    const data = await apiRequest(API_SITE_SETTINGS, { method: 'GET' });
    settingsBrand.value = data?.brand_name || '';
    settingsLogo.value = data?.logo_url || '';
    settingsPrimary.value = data?.primary_color || '';
    settingsSecondary.value = data?.secondary_color || '';
    settingsBackground.value = data?.background_color || '';
    settingsHeroTitle.value = data?.hero_title || '';
    settingsHeroSubtitle.value = data?.hero_subtitle || '';
    settingsHeroImage.value = data?.hero_image_url || '';
    settingsContacts.value = JSON.stringify(data?.contacts || {}, null, 2);
    settingsSocial.value = JSON.stringify(data?.social_links || {}, null, 2);
  } catch (error) {
    setStatus(statusSettings, error.message || 'Не удалось загрузить настройки', 'error');
  }
}

async function saveSettings() {
  try {
    const payload = {
      brand_name: settingsBrand.value.trim() || null,
      logo_url: settingsLogo.value.trim() || null,
      primary_color: settingsPrimary.value.trim() || null,
      secondary_color: settingsSecondary.value.trim() || null,
      background_color: settingsBackground.value.trim() || null,
      hero_title: settingsHeroTitle.value.trim() || null,
      hero_subtitle: settingsHeroSubtitle.value.trim() || null,
      hero_image_url: settingsHeroImage.value.trim() || null,
      contacts: parseJsonInput(settingsContacts.value, {}),
      social_links: parseJsonInput(settingsSocial.value, {}),
    };

    await apiRequest(API_SITE_SETTINGS, { method: 'PUT', body: payload });
    setStatus(statusSettings, 'Настройки сохранены', 'ok');
  } catch (error) {
    setStatus(statusSettings, error.message || 'Не удалось сохранить настройки', 'error');
  }
}

function renderMediaList(items) {
  if (!mediaList) return;
  mediaList.innerHTML = '';
  if (!items.length) {
    mediaList.innerHTML = '<p class="muted">Файлы не найдены.</p>';
    return;
  }
  items.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'media-item';

    const img = document.createElement('img');
    img.src = item.url;
    img.alt = item.name;

    const info = document.createElement('div');
    info.className = 'media-info';
    info.innerHTML = `<strong>${item.name}</strong><div class="muted">${item.url}</div>`;

    const actions = document.createElement('div');
    actions.className = 'actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn-secondary';
    copyBtn.type = 'button';
    copyBtn.textContent = 'Скопировать URL';
    copyBtn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(item.url);
      setStatus(statusMedia, 'URL скопирован', 'ok');
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn-danger';
    deleteBtn.type = 'button';
    deleteBtn.textContent = 'Удалить';
    deleteBtn.addEventListener('click', async () => {
      if (!confirm('Удалить файл?')) return;
      try {
        await apiRequest(`${API_MEDIA}/${item.name}`, { method: 'DELETE' });
        await loadMedia();
      } catch (error) {
        setStatus(statusMedia, error.message || 'Не удалось удалить файл', 'error');
      }
    });

    actions.append(copyBtn, deleteBtn);
    card.append(img, info, actions);
    mediaList.appendChild(card);
  });
}

async function loadMedia(query = '') {
  try {
    const url = query ? `${API_MEDIA}?q=${encodeURIComponent(query)}` : API_MEDIA;
    const data = await apiRequest(url, { method: 'GET' });
    renderMediaList(data || []);
  } catch (error) {
    setStatus(statusMedia, error.message || 'Не удалось загрузить медиа', 'error');
  }
}

async function uploadMedia() {
  if (!mediaUploadInput?.files?.length) {
    setStatus(mediaUploadStatus, 'Выберите файл', 'error');
    return;
  }
  const file = mediaUploadInput.files[0];
  const formData = new FormData();
  formData.append('file', file);
  try {
    await apiRequest(API_MEDIA_UPLOAD, { method: 'POST', body: formData });
    setStatus(mediaUploadStatus, 'Файл загружен', 'ok');
    await loadMedia();
  } catch (error) {
    setStatus(mediaUploadStatus, error.message || 'Не удалось загрузить файл', 'error');
  }
}

categoryAdd?.addEventListener('click', () => renderCategoryForm());
itemAdd?.addEventListener('click', () => renderItemForm());
menuRefresh?.addEventListener('click', () => loadCategories());
settingsSave?.addEventListener('click', saveSettings);
mediaUploadBtn?.addEventListener('click', uploadMedia);
mediaRefreshBtn?.addEventListener('click', () => loadMedia(mediaSearch?.value || ''));
mediaSearch?.addEventListener('input', () => loadMedia(mediaSearch.value));
panelTabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    const panelId = tab.dataset.panel;
    if (panelId) {
      setActivePanel(panelId);
    }
  });
});

window.addEventListener('popstate', async () => {
  const typeChanged = applySectionFromUrl();
  if (typeChanged) {
    setStatus(globalStatus, 'Загрузка данных меню...', 'muted');
    await loadCategories();
    setStatus(globalStatus, 'Данные загружены', 'ok');
  }
});

async function bootstrap() {
  applySectionFromUrl();
  setStatus(globalStatus, 'Загрузка данных меню...', 'muted');
  await Promise.all([loadCategories(), loadSettings(), loadMedia()]);
  setStatus(globalStatus, 'Данные загружены', 'ok');
}

bootstrap();
