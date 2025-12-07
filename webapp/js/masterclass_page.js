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

    const card = document.createElement('article');
    card.className = 'catalog-card detail-card';

    const imageWrapper = document.createElement('div');
    imageWrapper.className = 'catalog-card-image detail-card__image';

    const mainImage = document.createElement('img');
    mainImage.alt = masterclass.name || 'Мастер-класс';

    const placeholder = document.createElement('div');
    placeholder.className = 'catalog-card-placeholder';
    placeholder.textContent = masterclass.category_name || 'Мастер-класс';

    const images = normalizeImages(masterclass);
    if (images.length) {
      mainImage.src = images[0];
      imageWrapper.appendChild(mainImage);
    } else {
      placeholder.style.display = 'flex';
      imageWrapper.appendChild(placeholder);
    }

    const body = document.createElement('div');
    body.className = 'catalog-card-body detail-card__body';

    const title = document.createElement('h1');
    title.className = 'catalog-card-title';
    title.textContent = masterclass.name;

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = masterclass.category_name || '';

    const price = document.createElement('div');
    price.className = 'price';
    price.textContent = formatPrice(masterclass.price);

    const level = document.createElement('div');
    level.className = 'muted';
    level.textContent = [masterclass.level, masterclass.duration, masterclass.format].filter(Boolean).join(' · ');

    const shortDesc = document.createElement('p');
    shortDesc.className = 'muted';
    shortDesc.textContent = masterclass.short_description || '';

    const description = document.createElement('div');
    description.className = 'product-detail__description';
    description.textContent = masterclass.description || '';

    const actions = document.createElement('div');
    actions.className = 'detail-card__actions';

    if (Number(masterclass.price || 0) === 0 && (masterclass.masterclass_url || masterclass.detail_url)) {
      const link = document.createElement('a');
      link.className = 'btn';
      link.href = masterclass.masterclass_url || masterclass.detail_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Записаться';
      actions.appendChild(link);
    } else {
      const addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'btn';
      addBtn.textContent = 'Добавить в корзину';
      addBtn.addEventListener('click', () => handleAddToCart(masterclass));
      actions.appendChild(addBtn);
    }

    const backLink = document.createElement('a');
    backLink.href = 'masterclasses.html';
    backLink.className = 'btn secondary';
    backLink.textContent = 'Назад к мастер-классам';

    actions.appendChild(backLink);

    body.append(title, meta, price, level, shortDesc, description, actions);
    card.append(imageWrapper, body);
    root.appendChild(card);
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
