(function () {
  const root = document.getElementById('masterclass-details-root');
  const adminLink = document.getElementById('admin-link');
  const params = new URLSearchParams(window.location.search);
  const masterclassId = params.get('id');
  const reviewsList = document.getElementById('mc-reviews-list');
  const reviewsEmpty = document.getElementById('mc-reviews-empty');
  const reviewForm = document.getElementById('mc-review-form');
  const reviewMessage = document.getElementById('mc-review-message');

  let reviewFormInitialized = false;

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

  const escapeHtml = (value) => {
    const div = document.createElement('div');
    div.textContent = value ?? '';
    return div.innerHTML;
  };

  const formatDate = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
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

  const loadMasterclassReviews = async (mcId) => {
    if (!mcId || !reviewsList || !reviewsEmpty) return;

    reviewsList.innerHTML = '';
    reviewsEmpty.style.display = 'none';

    try {
      const res = await fetch(`/api/masterclasses/${mcId}/reviews`);
      if (!res.ok) {
        console.error('Failed to load masterclass reviews', res.status);
        return;
      }

      const reviews = await res.json();

      if (!reviews || !reviews.length) {
        reviewsEmpty.style.display = '';
        return;
      }

      reviews.forEach((review) => {
        const card = document.createElement('div');
        card.className = 'review-card mc-review-card';

        const header = document.createElement('div');
        header.className = 'review-card__header mc-review-header';

        const author = document.createElement('div');
        author.className = 'review-card__author';
        author.textContent = review.author_name || review.user_name || 'Ученик';

        const rating = document.createElement('div');
        rating.className = 'review-card__rating mc-review-rating';
        const safeRating = Math.max(0, Math.min(5, Number(review.rating) || 0));
        rating.textContent = `${'★'.repeat(safeRating)}${'☆'.repeat(5 - safeRating)}`;

        const date = document.createElement('div');
        date.className = 'review-card__date mc-review-date';
        date.textContent = formatDate(review.created_at);

        header.append(author, rating, date);

        const text = document.createElement('p');
        text.className = 'review-card__text mc-review-text';
        text.innerHTML = escapeHtml(review.text || '');

        card.append(header, text);
        reviewsList.appendChild(card);
      });
    } catch (err) {
      console.error(err);
    }
  };

  const loadMasterclass = async () => {
    if (!masterclassId) {
      renderMessage('Мастер-класс не найден (нет ID в ссылке).');
      return;
    }

    try {
      const masterclass = await apiGet(`/masterclasses/${masterclassId}`);
      renderMasterclass(masterclass);
      loadMasterclassReviews(masterclassId);
    } catch (error) {
      if (error.status === 404) {
        renderMessage('Мастер-класс не найден или недоступен.');
      } else {
        renderMessage('Произошла ошибка при загрузке мастер-класса');
      }
    }
  };

  const handleReviewSubmit = async (event) => {
    if (!reviewForm || !reviewMessage) return;
    event.preventDefault();
    reviewMessage.textContent = '';

    const formData = new FormData(reviewForm);
    const payload = {
      rating: Number(formData.get('rating')),
      text: formData.get('text')?.toString().trim(),
    };

    if (!masterclassId) {
      reviewMessage.textContent = 'Мастер-класс не найден.';
      return;
    }

    if (!payload.rating || payload.rating < 1 || payload.rating > 5) {
      reviewMessage.textContent = 'Поставьте оценку от 1 до 5.';
      return;
    }

    if (!payload.text) {
      reviewMessage.textContent = 'Пожалуйста, напишите текст отзыва.';
      return;
    }

    try {
      const res = await fetch(`/api/masterclasses/${masterclassId}/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || 'Не удалось отправить отзыв.';
        reviewMessage.textContent = msg;
        return;
      }

      reviewForm.reset();
      reviewMessage.textContent = 'Спасибо! Отзыв отправлен.';
      await loadMasterclassReviews(masterclassId);
    } catch (err) {
      console.error(err);
      reviewMessage.textContent = 'Ошибка сети. Попробуйте позже.';
    }
  };

  const initReviewForm = () => {
    if (reviewFormInitialized || !reviewForm || !masterclassId) return;
    reviewForm.addEventListener('submit', handleReviewSubmit);
    reviewFormInitialized = true;
  };

  updateAdminLinkVisibility();
  loadMasterclass();
  initReviewForm();
})();
