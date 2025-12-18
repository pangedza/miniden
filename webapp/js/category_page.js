(function () {
  const adminLink = document.getElementById('admin-link');
  const noteEl = document.getElementById('category-note');
  const heroTitle = document.getElementById('category-title');
  const heroDescription = document.getElementById('category-description');
  const heroImage = document.getElementById('category-image');
  const breadcrumbsEl = document.getElementById('category-breadcrumbs');
  const productsSection = document.getElementById('category-products');
  const masterclassesSection = document.getElementById('category-masterclasses');

  let profile = null;

  function updateAdminLinkVisibility() {
    if (!adminLink) return;
    adminLink.style.display = profile?.is_admin ? '' : 'none';
  }

  function formatPrice(value) {
    const num = Number(value) || 0;
    if (num === 0) return 'Бесплатно';
    return `${num.toLocaleString('ru-RU')} ₽`;
  }

  function versionedImageUrl(entity) {
    if (!entity?.image_url) return '';
    const version = entity.image_version || (entity.updated_at ? new Date(entity.updated_at).getTime() : null);
    return window.withCacheBusting ? window.withCacheBusting(entity.image_url, version) : entity.image_url;
  }

  function normalizeImages(item) {
    const urls = [];
    const push = (value) => {
      if (!value) return;
      if (typeof value === 'string') urls.push(value);
      else if (typeof value === 'object') {
        if (Array.isArray(value)) value.forEach(push);
        else if (value.image_url) urls.push(value.image_url);
      }
    };
    push(item.image_url || item.image);
    push(item.images || []);
    return Array.from(new Set(urls.filter(Boolean)));
  }

  function buildProductCard(item) {
    const card = document.createElement('article');
    card.className = 'catalog-card product-card';

    const cover = document.createElement('div');
    cover.className = 'catalog-card-image product-card__image';
    const img = document.createElement('img');
    img.alt = item.name || 'Товар';
    const images = normalizeImages(item);
    if (images.length) {
      img.src = images[0];
      cover.appendChild(img);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'catalog-card-meta';
      placeholder.textContent = 'Фото появится позже';
      cover.appendChild(placeholder);
    }

    const body = document.createElement('div');
    body.className = 'catalog-card-body product-card-body';

    const categoryMeta = document.createElement('div');
    categoryMeta.className = 'catalog-card-meta';
    if (item.category_slug) {
      const link = document.createElement('a');
      link.href = `/category/${encodeURIComponent(item.category_slug)}`;
      link.className = 'category-link';
      link.textContent = item.category_name || 'Категория';
      categoryMeta.appendChild(link);
    } else {
      categoryMeta.textContent = item.category_name || 'Категория';
    }

    const title = document.createElement('h3');
    title.className = 'catalog-card-title';
    title.textContent = item.name || 'Товар';

    const desc = document.createElement('p');
    desc.className = 'catalog-card-description';
    desc.textContent = item.short_description || '';

    const footer = document.createElement('div');
    footer.className = 'product-card__actions';
    const price = document.createElement('div');
    price.className = 'price';
    price.textContent = formatPrice(item.price);

    const moreBtn = document.createElement('a');
    moreBtn.href = `product.html?id=${encodeURIComponent(item.id)}`;
    moreBtn.className = 'btn secondary btn-secondary';
    moreBtn.textContent = 'Подробнее';

    footer.append(price, moreBtn);

    body.append(categoryMeta, title, desc, footer);
    card.append(cover, body);
    return card;
  }

  function buildMasterclassCard(item) {
    const card = document.createElement('article');
    card.className = 'catalog-card course-card';

    const cover = document.createElement('div');
    cover.className = 'course-card__image-wrapper catalog-card-image';
    const img = document.createElement('img');
    img.className = 'course-card__image';
    img.alt = item.name || 'Мастер-класс';
    const images = normalizeImages(item);
    if (images.length) {
      img.src = images[0];
      cover.appendChild(img);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'catalog-card-meta';
      placeholder.textContent = 'Изображение появится позже';
      cover.appendChild(placeholder);
    }

    const body = document.createElement('div');
    body.className = 'catalog-card-body course-card-body';

    const meta = document.createElement('div');
    meta.className = 'meta';
    if (item.category_slug) {
      const link = document.createElement('a');
      link.href = `/category/${encodeURIComponent(item.category_slug)}`;
      link.className = 'category-link';
      link.textContent = item.category_name || 'Категория';
      meta.appendChild(link);
    } else {
      meta.textContent = item.category_name || '';
    }

    const title = document.createElement('h3');
    title.className = 'catalog-card-title';
    title.textContent = item.name;

    const desc = document.createElement('p');
    desc.className = 'catalog-card-description course-card__short-desc';
    desc.textContent = item.short_description || item.description || '';

    const footer = document.createElement('div');
    footer.className = 'course-card__footer';
    const price = document.createElement('div');
    price.className = 'price';
    price.textContent = formatPrice(item.price);

    const openBtn = document.createElement('a');
    openBtn.href = `masterclass.html?id=${encodeURIComponent(item.id)}`;
    openBtn.className = 'btn btn-primary';
    openBtn.textContent = 'Открыть';

    footer.append(price, openBtn);

    body.append(meta, title, desc, footer);
    card.append(cover, body);
    return card;
  }

  function renderList(sectionEl, items, titleText, builder) {
    if (!sectionEl) return;
    sectionEl.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.className = 'category-layout__section';

    const title = document.createElement('h2');
    title.textContent = titleText;
    wrapper.appendChild(title);

    if (!items || !items.length) {
      const empty = document.createElement('div');
      empty.className = 'category-layout__empty';
      empty.textContent = 'Пока пусто, но скоро появится.';
      wrapper.appendChild(empty);
      sectionEl.appendChild(wrapper);
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'products-grid catalog-grid';
    items.forEach((item) => grid.appendChild(builder(item)));

    wrapper.appendChild(grid);
    sectionEl.appendChild(wrapper);
  }

  function setBreadcrumbs(category) {
    if (!breadcrumbsEl) return;
    breadcrumbsEl.innerHTML = '';
    const home = document.createElement('a');
    home.href = '/';
    home.textContent = 'Главная';

    const sep1 = document.createElement('span');
    sep1.textContent = '→';

    const categoriesLink = document.createElement('a');
    categoriesLink.href = '/categories';
    categoriesLink.textContent = 'Категории';

    const sep2 = document.createElement('span');
    sep2.textContent = '→';

    const current = document.createElement('span');
    current.textContent = category.name || 'Категория';

    breadcrumbsEl.append(home, sep1, categoriesLink, sep2, current);
  }

  function renderCategory(category) {
    if (heroTitle) heroTitle.textContent = category.name || 'Категория';
    if (heroDescription) heroDescription.textContent = category.description || 'Описание появится позже.';
    if (heroImage) {
      const heroUrl = versionedImageUrl(category);
      if (heroUrl) {
        heroImage.src = heroUrl;
        heroImage.alt = category.name || 'Категория';
        heroImage.style.display = 'block';
      } else {
        heroImage.removeAttribute('src');
        heroImage.style.display = 'none';
      }
    }
    setBreadcrumbs(category);
  }

  function getSlugFromUrl() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('slug')) return params.get('slug');
    const parts = (window.location.pathname || '').split('/').filter(Boolean);
    if (parts[0] === 'category' && parts[1]) return parts[1];
    return null;
  }

  async function loadCategory() {
    const slug = getSlugFromUrl();
    if (!slug) {
      if (noteEl) noteEl.textContent = 'Категория не найдена.';
      return;
    }

    try {
      const data = await apiGet(`/categories/${encodeURIComponent(slug)}`);
      const category = data.category || {};
      const combinedItems = Array.isArray(data.items) ? data.items : [];
      const products = (data.products && data.products.length ? data.products : combinedItems.filter((item) => item.type === 'basket')) || [];
      const masterclasses = (data.masterclasses && data.masterclasses.length
        ? data.masterclasses
        : combinedItems.filter((item) => item.type === 'course')) || [];
      renderCategory(category);
      renderList(productsSection, products, 'Товары этой категории', buildProductCard);
      renderList(masterclassesSection, masterclasses, 'Мастер-классы', buildMasterclassCard);
    } catch (error) {
      console.error('Failed to load category', error);
      if (noteEl) noteEl.textContent = 'Категория не найдена или выключена.';
    }
  }

  async function init() {
    try {
      profile = await getCurrentUser();
      updateAdminLinkVisibility();
    } catch (e) {
      console.warn('Не удалось загрузить профиль', e);
    }

    await loadCategory();
  }

  init();
})();
