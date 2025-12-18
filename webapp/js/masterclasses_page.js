(function () {
  const adminLink = document.getElementById('admin-link');
  const noteEl = document.getElementById('note');
  const categoriesNavEl = document.getElementById('masterclasses-categories-nav');
  const masterclassesContainer = document.getElementById('masterclasses-by-category');
  const searchInput = document.getElementById('mc-search-input');
  const searchClearBtn = document.getElementById('mc-search-clear');

  const mcsByCategory = new Map();
  let categories = [];
  let allMasterclasses = [];
  let profile = null;
  let debounceTimer = null;
  let currentSearchValue = '';

  const metaBySlug = {
    paid: 'Доступ навсегда + материалы',
    free: 'Пробные уроки и мини-гайды',
  };

  if (isTelegramWebApp && window.Telegram?.WebApp?.ready) {
    window.Telegram.WebApp.ready();
  }

  function formatPrice(value) {
    const num = Number(value) || 0;
    if (num === 0) return 'Бесплатно';
    return `${num.toLocaleString('ru-RU')} ₽`;
  }

  function truncateText(text, limit = 160) {
    if (!text) return '';
    return text.length > limit ? `${text.slice(0, limit)}…` : text;
  }

  function shortDescription(item) {
    if (item?.short_description) return item.short_description;
    const fallback = item?.description ? truncateText(item.description, 140) : '';
    return fallback || 'Описание появится позже.';
  }

  function normalizeImages(item, extraFields = []) {
    const urls = [];
    const pushUrl = (value) => {
      if (!value) return;
      if (typeof value === 'string') {
        urls.push(value);
        return;
      }
      if (typeof value === 'object') {
        const maybe = value.image_url || value.url || value.path;
        if (maybe) urls.push(maybe);
      }
    };

    pushUrl(item.image_url || item.image);
    (Array.isArray(item.images) ? item.images : []).forEach(pushUrl);
    (extraFields || []).forEach((field) => {
      const value = item[field];
      if (Array.isArray(value)) value.forEach(pushUrl);
    });

    const unique = Array.from(new Set(urls.filter(Boolean)));
    item.images = unique;
    return item;
  }

  function updateAdminLinkVisibility() {
    if (!adminLink) return;
    adminLink.style.display = profile?.is_admin ? '' : 'none';
  }

  function matchesSearch(item, filter) {
    if (!filter) return true;
    const haystacks = [
      item.name,
      item.title,
      item.short_description,
      item.description,
      item.category_name,
      item.level,
      item.format,
    ];

    return haystacks.some((value) => typeof value === 'string' && value.toLowerCase().includes(filter));
  }

  function createMasterclassCard(item) {
    const card = document.createElement('article');
    card.className = 'catalog-card course-card';

    const cover = document.createElement('div');
    cover.className = 'course-card__image-wrapper catalog-card-image';
    const coverImage = document.createElement('img');
    coverImage.className = 'course-card__image';
    const coverPlaceholder = document.createElement('div');
    coverPlaceholder.className = 'course-card__placeholder';
    coverPlaceholder.textContent = item.category_name || 'Мастер-классы';
    cover.append(coverImage, coverPlaceholder);

    const images = item.images && item.images.length ? item.images : [];
    let currentImageIndex = 0;

    const prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = 'course-card__nav course-card__nav--prev';
    prevBtn.textContent = '‹';

    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = 'course-card__nav course-card__nav--next';
    nextBtn.textContent = '›';

    if (images.length > 1) {
      cover.append(prevBtn, nextBtn);
    }

    const updateCardImage = () => {
      if (images.length) {
        currentImageIndex = (currentImageIndex + images.length) % images.length;
        coverImage.src = images[currentImageIndex];
        coverImage.style.display = 'block';
        coverPlaceholder.style.display = 'none';
      } else {
        coverImage.removeAttribute('src');
        coverImage.style.display = 'none';
        coverPlaceholder.style.display = 'flex';
      }

      const showNav = images.length > 1;
      prevBtn.style.display = showNav ? '' : 'none';
      nextBtn.style.display = showNav ? '' : 'none';
    };

    prevBtn.addEventListener('click', () => {
      if (!images.length) return;
      currentImageIndex = (currentImageIndex - 1 + images.length) % images.length;
      updateCardImage();
    });

    nextBtn.addEventListener('click', () => {
      if (!images.length) return;
      currentImageIndex = (currentImageIndex + 1) % images.length;
      updateCardImage();
    });

    updateCardImage();

    const body = document.createElement('div');
    body.className = 'catalog-card-body course-card-body';

    const title = document.createElement('h3');
    title.className = 'catalog-card-title';
    title.textContent = item.name;

    const meta = document.createElement('div');
    meta.className = 'meta';
    const categoryLabel = item.category_name || metaBySlug[item.category_slug] || '';
    if (item.category_slug) {
      const link = document.createElement('a');
      link.href = `/category/${encodeURIComponent(item.category_slug)}`;
      link.className = 'category-link';
      link.textContent = categoryLabel || 'Категория';
      meta.appendChild(link);
    } else {
      meta.textContent = categoryLabel;
    }

    const desc = document.createElement('p');
    desc.className = 'catalog-card-description course-card__short-desc';
    desc.textContent = shortDescription(item);

    const footer = document.createElement('div');
    footer.className = 'course-card__footer';

    const price = document.createElement('div');
    price.className = 'price';
    price.textContent = formatPrice(item.price);

    const hasAccess = profile?.courses?.some((c) => c.id === item.id) ?? false;

    const actions = document.createElement('div');
    actions.className = 'catalog-card-actions';

    const buttonsRow = document.createElement('div');
    buttonsRow.className = 'course-card__buttons';

    const openBtn = document.createElement('a');
    openBtn.className = 'btn btn-primary';
    openBtn.textContent = 'Перейти к мастер-классу';
    openBtn.style.textAlign = 'center';
    openBtn.href = `masterclass.html?id=${encodeURIComponent(item.id)}`;

    if (Number(item.price || 0) !== 0 && !hasAccess) {
      const addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'btn';
      addBtn.textContent = 'Добавить в корзину';
      addBtn.addEventListener('click', () => handleAddToCart(item));

      const note = document.createElement('div');
      note.style.color = 'var(--muted)';
      note.textContent = profile ? 'Доступ появится после оплаты' : 'Войдите и оплатите, чтобы открыть уроки';

      buttonsRow.append(addBtn, openBtn);
      actions.appendChild(note);
    } else {
      buttonsRow.append(openBtn);
    }

    footer.append(price);
    actions.append(footer, buttonsRow);

    body.append(title, meta, desc, actions);
    card.append(cover, body);

    return card;
  }

  async function handleAddToCart(course) {
    const currentProfile = await getCurrentUserProfile();

    try {
      if (currentProfile?.telegram_id) {
        await apiPost('/cart/add', { user_id: currentProfile.telegram_id, product_id: course.id, qty: 1, type: 'course' });
        showToast('Курс добавлен в корзину');
      } else {
        addToGuestCart(course.id, 'course', 1);
        showToast('Курс добавлен в корзину. Оформить заказ можно после входа через Telegram.');
      }
    } catch (e) {
      showToast('Не удалось добавить курс. Попробуйте ещё раз.');
    }
  }

  function buildCategoriesMap() {
    mcsByCategory.clear();
    const categoriesById = new Map();
    (categories || []).forEach((cat) => {
      const key = cat.id ?? cat.slug ?? cat.name;
      categoriesById.set(key, cat);
    });

    allMasterclasses.forEach((item) => {
      const categoryId = item.category_id ?? item.category?.id ?? item.category_slug ?? item.category ?? 'other';
      const categoryMeta = categoriesById.get(categoryId);
      const categoryName = categoryMeta?.name || item.category_name || item.category?.name || 'Мастер-классы';
      const categorySlug = categoryMeta?.slug || item.category_slug || null;
      const categoryType = categoryMeta?.type || null;
      const key = categoryId ?? 'other';
      const group = mcsByCategory.get(key) || { categoryId: key, categoryName, items: [], slug: categorySlug, type: categoryType };
      group.categoryName = categoryName;
      group.slug = group.slug || categorySlug;
      group.type = group.type || categoryType;
      group.items.push(item);
      mcsByCategory.set(key, group);
    });
  }

  function orderedGroups() {
    const used = new Set();
    const ordered = [];

    (categories || []).forEach((cat) => {
      const key = cat.id ?? cat.slug ?? cat.name;
      if (mcsByCategory.has(key)) {
        ordered.push(mcsByCategory.get(key));
        used.add(key);
      }
    });

    mcsByCategory.forEach((group, key) => {
      if (!used.has(key)) ordered.push(group);
    });

    return ordered;
  }

  function renderCategoriesNav() {
    if (!categoriesNavEl) return;
    categoriesNavEl.innerHTML = '';

    const groups = orderedGroups().filter((group) => (group.items || []).length);
    if (!groups.length) return;

    groups.forEach((group) => {
      const link = document.createElement('a');
      link.className = 'products-categories-nav__item mc-categories-nav__item';
      link.dataset.categoryId = group.categoryId;
      link.textContent = group.categoryName || 'Мастер-классы';
      if (group.slug) {
        link.href = `/category/${encodeURIComponent(group.slug)}`;
      } else {
        link.href = '#';
        link.addEventListener('click', (event) => {
          event.preventDefault();
          handleCategoryNavClick(group.categoryId);
        });
      }
      categoriesNavEl.appendChild(link);
    });
  }

  function handleCategoryNavClick(categoryId) {
    const sectionId = `mc-category-${categoryId}`;
    const sectionExists = !!document.getElementById(sectionId);

    if (!sectionExists && currentSearchValue) {
      currentSearchValue = '';
      if (searchInput) searchInput.value = '';
      renderMasterclassesByCategory('');
    }

    requestAnimationFrame(() => {
      const section = document.getElementById(sectionId);
      section?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function renderMasterclassesByCategory(filterText = '') {
    if (!masterclassesContainer) return;
    masterclassesContainer.innerHTML = '';
    currentSearchValue = filterText || '';

    const normalizedFilter = (filterText || '').trim().toLowerCase();
    const groups = orderedGroups();
    let totalRendered = 0;

    groups.forEach((group) => {
      const filteredItems = (group.items || []).filter((item) => matchesSearch(item, normalizedFilter));
      if (!filteredItems.length) return;

      const section = document.createElement('section');
      section.className = 'products-by-category__section';
      section.id = `mc-category-${group.categoryId}`;

      const header = document.createElement('div');
      header.className = 'products-by-category__section-header';
      const title = document.createElement('h2');
      if (group.slug) {
        const titleLink = document.createElement('a');
        titleLink.href = `/category/${encodeURIComponent(group.slug)}`;
        titleLink.className = 'category-link';
        titleLink.textContent = group.categoryName || 'Мастер-классы';
        title.appendChild(titleLink);
      } else {
        title.textContent = group.categoryName || 'Мастер-классы';
      }
      header.appendChild(title);
      section.appendChild(header);

      const grid = document.createElement('div');
      grid.className = 'catalog-grid courses-grid';

      filteredItems.forEach((item) => {
        grid.appendChild(createMasterclassCard(item));
        totalRendered += 1;
      });

      section.appendChild(grid);
      masterclassesContainer.appendChild(section);
    });

    if (totalRendered === 0) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Мастер-классы по вашему запросу не найдены';
      masterclassesContainer.appendChild(empty);
    }
  }

  function debounce(fn, delay = 350) {
    return (...args) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => fn(...args), delay);
    };
  }

  async function loadMasterclassesData() {
    if (noteEl) noteEl.textContent = '';

    try {
      categories = await apiGet('/categories', { type: 'course' });
    } catch (e) {
      categories = [];
    }

    try {
      allMasterclasses = (await apiGet('/products', { type: 'course' })).map((item) => normalizeImages(item, ['masterclass_images']));
    } catch (e) {
      allMasterclasses = [];
      mcsByCategory.clear();
      if (noteEl) noteEl.textContent = 'Не удалось загрузить мастер-классы. Попробуйте обновить страницу.';
      return;
    }

    buildCategoriesMap();
    renderCategoriesNav();
    renderMasterclassesByCategory(currentSearchValue);
  }

  function attachSearchHandlers() {
    if (searchInput) {
      searchInput.addEventListener(
        'input',
        debounce((event) => {
          renderMasterclassesByCategory(event.target.value);
        }, 350)
      );
    }

    searchClearBtn?.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      renderMasterclassesByCategory('');
      searchInput?.focus();
    });
  }

  async function initMasterclassesPage() {
    profile = await getCurrentUserProfile();
    updateAdminLinkVisibility();

    await loadMasterclassesData();
    attachSearchHandlers();

    if (!profile && noteEl) {
      noteEl.textContent = 'Каталог доступен в режиме просмотра. Чтобы оформить заказ, войдите через Telegram.';
    }
  }

  initMasterclassesPage().catch(console.error);
})();
