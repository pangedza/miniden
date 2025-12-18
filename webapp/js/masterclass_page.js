(function () {
  const root = document.getElementById('masterclass-details-root');
  const adminLink = document.getElementById('admin-link');
  const params = new URLSearchParams(window.location.search);
  const masterclassId = params.get('id');
  const reviewsRoot = document.getElementById('masterclass-reviews-root');
  let reviewsWidgetInitialized = false;

  if (!root) return;

  const formatPrice = (value) => {
    const num = Number(value) || 0;
    return num > 0 ? `${num.toLocaleString('ru-RU')} ₽` : 'Бесплатный';
  };

  const renderMessage = (text) => {
    root.innerHTML = '';
    const note = document.createElement('div');
    note.className = 'note';
    note.textContent = text;
    root.appendChild(note);
  };

  const normalizeImages = (item) => {
    const urls = new Set();
    const push = (value) => {
      if (!value) return;
      if (typeof value === 'string') {
        urls.add(value);
      } else if (typeof value === 'object') {
        const maybe = value.image_url || value.url || value.path;
        if (maybe) urls.add(maybe);
      }
    };

    push(item?.image_url || item?.image);
    (Array.isArray(item?.images) ? item.images : []).forEach(push);
    return Array.from(urls);
  };

  const updateAdminLinkVisibility = async () => {
    if (!adminLink) return;
    try {
      const profile = await getCurrentUserProfile();
      adminLink.style.display = profile?.is_admin ? '' : 'none';
    } catch (error) {
      adminLink.style.display = 'none';
    }
  };

  const handleAddToCart = async (masterclass) => {
    const currentProfile = await getCurrentUserProfile();

    try {
      if (currentProfile?.telegram_id) {
        await apiPost('/cart/add', {
          user_id: currentProfile.telegram_id,
          product_id: masterclass.id,
          qty: 1,
          type: 'course',
        });
        showToast('Мастер-класс добавлен в корзину');
      } else {
        addToGuestCart(masterclass.id, 'course', 1);
        showToast('Мастер-класс добавлен. Оформить заказ можно после входа через Telegram.');
      }
    } catch (error) {
      showToast('Не удалось добавить мастер-класс. Попробуйте ещё раз.');
    }
  };

  const renderMasterclass = (masterclass) => {
    root.innerHTML = '';

    const container = document.createElement('article');
    container.className = 'product-detail';

    const top = document.createElement('div');
    top.className = 'product-detail__top';

    const gallery = document.createElement('div');
    gallery.className = 'product-gallery';

    const mainFrame = document.createElement('div');
    mainFrame.className = 'product-gallery__main';

    const mainImage = document.createElement('img');
    mainImage.className = 'product-gallery__image';
    mainImage.alt = masterclass.name || 'Мастер-класс';

    const placeholder = document.createElement('div');
    placeholder.className = 'product-gallery__placeholder';
    placeholder.textContent = masterclass.category_name || 'Мастер-класс';

    const images = normalizeImages(masterclass);
    let currentIndex = 0;

    const setMainImage = (index) => {
      currentIndex = index;
      const src = images[index];
      if (src) {
        mainImage.src = src;
        mainImage.style.display = 'block';
        placeholder.style.display = 'none';
      } else {
        mainImage.removeAttribute('src');
        mainImage.style.display = 'none';
        placeholder.style.display = 'flex';
      }
      Array.from(gallery.querySelectorAll('.product-gallery__thumb')).forEach((btn, btnIndex) => {
        btn.classList.toggle('is-active', btnIndex === currentIndex);
      });
    };

    mainFrame.append(mainImage, placeholder);
    gallery.appendChild(mainFrame);

    if (images.length > 1) {
      const thumbs = document.createElement('div');
      thumbs.className = 'product-gallery__thumbs';

      images.forEach((src, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'product-gallery__thumb';

        const img = document.createElement('img');
        img.src = src;
        img.alt = masterclass.name || 'Мастер-класс';
        img.loading = 'lazy';

        btn.appendChild(img);
        btn.addEventListener('click', () => setMainImage(index));
        thumbs.appendChild(btn);
      });

      gallery.appendChild(thumbs);
    }

    setMainImage(0);

    const info = document.createElement('div');
    info.className = 'product-info';

    const title = document.createElement('h1');
    title.className = 'product-info__title';
    title.textContent = masterclass.name;

    const meta = document.createElement('div');
    meta.className = 'product-info__meta';
    if (masterclass.category_slug) {
      const link = document.createElement('a');
      link.href = `/category/${encodeURIComponent(masterclass.category_slug)}`;
      link.className = 'category-link';
      link.textContent = masterclass.category_name || 'Категория';
      meta.appendChild(link);
    } else {
      meta.textContent = masterclass.category_name || '';
    }

    const shortDesc = document.createElement('p');
    shortDesc.className = 'product-info__intro muted';
    shortDesc.textContent = masterclass.short_description || '';

    const details = document.createElement('div');
    details.className = 'product-info__meta muted';
    details.textContent = [masterclass.level, masterclass.duration, masterclass.format].filter(Boolean).join(' · ');

    const priceRow = document.createElement('div');
    priceRow.className = 'product-info__price-row';

    const price = document.createElement('div');
    price.className = 'product-info__price';
    price.textContent = formatPrice(masterclass.price);

    const cta = document.createElement('div');
    cta.className = 'product-info__cta';

    if (Number(masterclass.price || 0) === 0 && (masterclass.masterclass_url || masterclass.detail_url)) {
      const link = document.createElement('a');
      link.className = 'btn product-info__add';
      link.href = masterclass.masterclass_url || masterclass.detail_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Записаться';
      cta.appendChild(link);
    } else {
      const addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'btn product-info__add';
      addBtn.textContent = 'Добавить в корзину';
      addBtn.addEventListener('click', () => handleAddToCart(masterclass));
      cta.appendChild(addBtn);
    }

    const backLink = document.createElement('a');
    backLink.href = 'masterclasses.html';
    backLink.className = 'btn secondary';
    backLink.textContent = 'Назад к мастер-классам';

    cta.appendChild(backLink);
    priceRow.append(price, cta);

    info.append(title, meta, shortDesc, details, priceRow);

    const tabs = document.createElement('div');
    tabs.className = 'product-tabs';

    const tabsNav = document.createElement('div');
    tabsNav.className = 'product-tabs__nav';

    const descriptionTabBtn = document.createElement('button');
    descriptionTabBtn.type = 'button';
    descriptionTabBtn.className = 'product-tabs__btn is-active';
    descriptionTabBtn.textContent = 'Описание';

    const reviewsTabBtn = document.createElement('button');
    reviewsTabBtn.type = 'button';
    reviewsTabBtn.className = 'product-tabs__btn';
    reviewsTabBtn.textContent = 'Отзывы';

    tabsNav.append(descriptionTabBtn, reviewsTabBtn);

    const panels = document.createElement('div');
    panels.className = 'product-tabs__panels';

    const descriptionPanel = document.createElement('section');
    descriptionPanel.className = 'product-tab is-active';

    const description = document.createElement('div');
    description.className = 'product-detail__description';
    description.textContent = masterclass.description || '';

    descriptionPanel.appendChild(description);

    const reviewsPanel = document.createElement('section');
    reviewsPanel.className = 'product-tab';

    if (reviewsRoot) {
      reviewsPanel.appendChild(reviewsRoot);
    }

    panels.append(descriptionPanel, reviewsPanel);

    const switchTab = (target) => {
      [descriptionTabBtn, reviewsTabBtn].forEach((btn) => btn.classList.toggle('is-active', btn === target));
      [descriptionPanel, reviewsPanel].forEach((panel) => panel.classList.toggle('is-active', panel === (target === descriptionTabBtn ? descriptionPanel : reviewsPanel)));
    };

    descriptionTabBtn.addEventListener('click', () => switchTab(descriptionTabBtn));
    reviewsTabBtn.addEventListener('click', () => switchTab(reviewsTabBtn));

    tabs.append(tabsNav, panels);

    top.append(gallery, info);
    container.append(top, tabs);
    root.appendChild(container);
  };

  const initReviewsWidget = () => {
    if (reviewsWidgetInitialized || !reviewsRoot || !window.initReviewsWidget || !masterclassId) return;
    window.initReviewsWidget({
      rootEl: reviewsRoot,
      type: 'masterclass',
      itemId: masterclassId,
    });
    reviewsWidgetInitialized = true;
  };

  const loadMasterclass = async () => {
    if (!masterclassId) {
      renderMessage('Мастер-класс не найден (нет ID в ссылке).');
      return;
    }

    try {
      const masterclass = await apiGet(`/masterclasses/${masterclassId}`);
      renderMasterclass(masterclass);
      initReviewsWidget();
    } catch (error) {
      if (error.status === 404) {
        renderMessage('Мастер-класс не найден или недоступен.');
      } else {
        renderMessage('Произошла ошибка при загрузке мастер-класса');
      }
    }
  };

  updateAdminLinkVisibility();
  loadMasterclass();
})();
