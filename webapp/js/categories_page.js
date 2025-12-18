(function () {
  const adminLink = document.getElementById('admin-link');
  const gridEl = document.getElementById('categories-grid');
  const emptyEl = document.getElementById('categories-empty');
  const noteEl = document.getElementById('categories-note');

  let profile = null;

  function updateAdminLinkVisibility() {
    if (!adminLink) return;
    adminLink.style.display = profile?.is_admin ? '' : 'none';
  }

  function buildPill(text) {
    const pill = document.createElement('span');
    pill.className = 'pill';
    pill.textContent = text;
    return pill;
  }

  function renderCategories(items) {
    if (!gridEl) return;
    gridEl.innerHTML = '';

    const activeItems = (items || []).filter((item) => item?.is_active);

    if (!activeItems.length) {
      if (emptyEl) emptyEl.style.display = '';
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    activeItems.forEach((item) => {
      const card = document.createElement('article');
      card.className = 'category-card';

      const link = document.createElement('a');
      link.href = `/category/${encodeURIComponent(item.slug)}`;
      link.style.textDecoration = 'none';
      link.style.color = 'inherit';

      const imageWrap = document.createElement('div');
      imageWrap.className = 'category-card__image';
      if (item.image_url) {
        const img = document.createElement('img');
        img.src = item.image_url;
        img.alt = item.name || 'Категория';
        imageWrap.appendChild(img);
      } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'catalog-card-meta';
        placeholder.textContent = 'Изображение появится позже';
        imageWrap.appendChild(placeholder);
      }

      const body = document.createElement('div');
      body.className = 'category-card__body';

      const title = document.createElement('h3');
      title.className = 'category-card__title';
      title.textContent = item.name || 'Категория';

      const description = document.createElement('p');
      description.className = 'category-card__description';
      description.textContent = item.description || 'Описание появится позже.';

      const footer = document.createElement('div');
      footer.className = 'category-card__footer';
      const typePill = buildPill(item.type === 'course' ? 'Мастер-классы' : 'Товары');
      footer.appendChild(typePill);

      body.append(title, description, footer);
      link.append(imageWrap, body);
      card.appendChild(link);

      gridEl.appendChild(card);
    });
  }

  async function loadCategories() {
    try {
      const items = await apiGet('/categories');
      renderCategories(items);
    } catch (error) {
      console.error('Failed to load categories', error);
      if (noteEl) {
        noteEl.textContent = 'Не удалось загрузить категории. Попробуйте обновить страницу.';
      }
      if (emptyEl) emptyEl.style.display = '';
    }
  }

  async function init() {
    try {
      profile = await getCurrentUser();
      updateAdminLinkVisibility();
    } catch (e) {
      console.warn('Не удалось загрузить профиль', e);
    }

    await loadCategories();
  }

  init();
})();
