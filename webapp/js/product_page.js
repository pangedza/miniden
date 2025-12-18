(function () {
  const root = document.getElementById('product-details-root');
  const adminLink = document.getElementById('admin-link');
  const reviewsRoot = document.getElementById('product-reviews-root');
  const params = new URLSearchParams(window.location.search);
  const productId = params.get('id');
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

  const handleAddToCart = async (product) => {
    const currentProfile = await getCurrentUserProfile();
    const productType = product?.type || 'basket';

    try {
      if (currentProfile?.telegram_id) {
        await apiPost('/cart/add', {
          user_id: currentProfile.telegram_id,
          product_id: product.id,
          qty: 1,
          type: productType,
        });
        showToast('Товар добавлен в корзину');
      } else {
        addToGuestCart(product.id, productType, 1);
        showToast('Товар добавлен в корзину. Войдите через Telegram, чтобы оформить заказ.');
      }
    } catch (error) {
      showToast('Не удалось добавить товар. Попробуйте ещё раз.');
    }
  };

  const createDetailsLayout = ({
    title,
    meta,
    intro,
    details,
    price,
    images,
    placeholder,
    description,
    onPrimary,
    primaryLabel,
    secondaryHref,
    secondaryLabel,
  }) => {
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
    mainImage.alt = title || 'Товар';

    const galleryPlaceholder = document.createElement('div');
    galleryPlaceholder.className = 'product-gallery__placeholder';
    galleryPlaceholder.textContent = placeholder || 'Товар';

    let currentIndex = 0;

    const setMainImage = (index) => {
      currentIndex = index;
      const src = images[index];
      if (src) {
        mainImage.src = src;
        mainImage.style.display = 'block';
        galleryPlaceholder.style.display = 'none';
      } else {
        mainImage.removeAttribute('src');
        mainImage.style.display = 'none';
        galleryPlaceholder.style.display = 'flex';
      }
      Array.from(gallery.querySelectorAll('.product-gallery__thumb')).forEach((btn, btnIndex) => {
        btn.classList.toggle('is-active', btnIndex === currentIndex);
      });
    };

    mainFrame.append(mainImage, galleryPlaceholder);
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
        img.alt = title || 'Товар';
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

    const titleEl = document.createElement('h1');
    titleEl.className = 'product-info__title';
    titleEl.textContent = title;

    const metaEl = document.createElement('div');
    metaEl.className = 'product-info__meta';
    metaEl.textContent = meta;

    const introEl = document.createElement('p');
    introEl.className = 'product-info__intro muted';
    introEl.textContent = intro;

    const detailsEl = document.createElement('div');
    detailsEl.className = 'product-info__meta muted';
    detailsEl.textContent = details;

    const priceRow = document.createElement('div');
    priceRow.className = 'product-info__price-row';

    const priceEl = document.createElement('div');
    priceEl.className = 'product-info__price';
    priceEl.textContent = price;

    const cta = document.createElement('div');
    cta.className = 'product-info__cta';

    if (onPrimary) {
      const addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'btn product-info__add';
      addBtn.textContent = primaryLabel;
      addBtn.addEventListener('click', onPrimary);
      cta.appendChild(addBtn);
    }

    if (secondaryHref) {
      const backLink = document.createElement('a');
      backLink.href = secondaryHref;
      backLink.className = 'btn secondary';
      backLink.textContent = secondaryLabel;
      cta.appendChild(backLink);
    }

    priceRow.append(priceEl, cta);

    info.append(titleEl, metaEl, introEl, detailsEl, priceRow);

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

    const descriptionEl = document.createElement('div');
    descriptionEl.className = 'product-detail__description';
    descriptionEl.textContent = description;

    descriptionPanel.appendChild(descriptionEl);

    const reviewsPanel = document.createElement('section');
    reviewsPanel.className = 'product-tab';

    if (reviewsRoot) {
      reviewsPanel.appendChild(reviewsRoot);
    }

    panels.append(descriptionPanel, reviewsPanel);

    const switchTab = (target) => {
      [descriptionTabBtn, reviewsTabBtn].forEach((btn) => btn.classList.toggle('is-active', btn === target));
      [descriptionPanel, reviewsPanel].forEach((panel) =>
        panel.classList.toggle('is-active', panel === (target === descriptionTabBtn ? descriptionPanel : reviewsPanel))
      );
    };

    descriptionTabBtn.addEventListener('click', () => switchTab(descriptionTabBtn));
    reviewsTabBtn.addEventListener('click', () => switchTab(reviewsTabBtn));

    tabs.append(tabsNav, panels);

    top.append(gallery, info);
    container.append(top, tabs);
    root.appendChild(container);
  };

  const renderProduct = (product) => {
    const detailParts = [];
    if (product.type === 'basket') {
      detailParts.push('Готовая корзинка');
    } else if (product.type === 'course') {
      detailParts.push('Мастер-класс');
    }

    const marketplaces = [
      product.wb_url ? 'Wildberries' : null,
      product.ozon_url ? 'Ozon' : null,
      product.yandex_url ? 'Яндекс.Маркет' : null,
      product.avito_url ? 'Avito' : null,
    ].filter(Boolean);

    if (marketplaces.length) {
      detailParts.push(`Маркетплейсы: ${marketplaces.join(', ')}`);
    }

    createDetailsLayout({
      title: product.name,
      meta: product.category_name || '',
      intro: product.short_description || '',
      details: detailParts.join(' · '),
      price: formatPrice(product.price),
      images: normalizeImages(product),
      placeholder: product.category_name || 'Товар',
      description: product.description || '',
      onPrimary: () => handleAddToCart(product),
      primaryLabel: 'В корзину',
      secondaryHref: 'products.html',
      secondaryLabel: 'Назад к товарам',
    });
  };

  const initReviewsWidget = () => {
    if (reviewsWidgetInitialized || !reviewsRoot || !window.initReviewsWidget || !productId) return;
    window.initReviewsWidget({
      rootEl: reviewsRoot,
      type: 'product',
      itemId: productId,
    });
    reviewsWidgetInitialized = true;
  };

  const loadProduct = async () => {
    if (!productId) {
      renderMessage('Товар не найден');
      return;
    }

    try {
      const product = await apiGet(`/products/${productId}`);
      renderProduct(product);
      initReviewsWidget();
    } catch (error) {
      if (error.status === 404) {
        renderMessage('Товар не найден или недоступен');
      } else {
        renderMessage('Произошла ошибка при загрузке товара');
      }
    }
  };

  updateAdminLinkVisibility();
  loadProduct();
})();
