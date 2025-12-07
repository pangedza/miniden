(function () {
  const root = document.getElementById('product-details-root');
  const adminLink = document.getElementById('admin-link');
  const reviewSection = document.getElementById('product-reviews');
  const reviewsList = document.getElementById('product-reviews-list');
  const reviewsEmpty = document.getElementById('product-reviews-empty');
  const reviewForm = document.getElementById('product-review-form');
  const reviewMessage = document.getElementById('product-review-message');
  const params = new URLSearchParams(window.location.search);
  const productId = params.get('id');
  let reviewFormInitialized = false;

  if (!root) return;

  const formatPrice = (value) => {
    const num = Number(value) || 0;
    return num > 0 ? `${num.toLocaleString('ru-RU')} ₽` : 'Бесплатно';
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

  const renderProduct = (product) => {
    root.innerHTML = '';

    const card = document.createElement('article');
    card.className = 'catalog-card detail-card';

    const imageWrapper = document.createElement('div');
    imageWrapper.className = 'catalog-card-image detail-card__image';

    const mainImage = document.createElement('img');
    mainImage.alt = product.name || 'Товар';

    const placeholder = document.createElement('div');
    placeholder.className = 'catalog-card-placeholder';
    placeholder.textContent = product.category_name || 'Товар';

    const images = normalizeImages(product);
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
    title.textContent = product.name;

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = product.category_name || '';

    const price = document.createElement('div');
    price.className = 'price';
    price.textContent = formatPrice(product.price);

    const shortDesc = document.createElement('p');
    shortDesc.className = 'muted';
    shortDesc.textContent = product.short_description || '';

    const description = document.createElement('div');
    description.className = 'product-detail__description';
    description.textContent = product.description || '';

    const actions = document.createElement('div');
    actions.className = 'detail-card__actions';

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'btn';
    addBtn.textContent = 'В корзину';
    addBtn.addEventListener('click', () => handleAddToCart(product));

    const backLink = document.createElement('a');
    backLink.href = 'products.html';
    backLink.className = 'btn secondary';
    backLink.textContent = 'Назад к товарам';

    actions.append(addBtn, backLink);
    body.append(title, meta, price, shortDesc, description, actions);
    card.append(imageWrapper, body);
    root.appendChild(card);
  };

  const renderReviews = (items) => {
    if (!reviewsList || !reviewsEmpty) return;

    reviewsList.innerHTML = '';
    reviewsEmpty.style.display = 'none';

    const reviews = Array.isArray(items) ? items : [];
    if (!reviews.length) {
      reviewsEmpty.style.display = '';
      return;
    }

    reviews.forEach((review) => {
      const card = document.createElement('article');
      card.className = 'review-card product-review-card';

      const header = document.createElement('div');
      header.className = 'review-card__header product-review-header';

      const author = document.createElement('div');
      author.className = 'review-card__author';
      author.textContent = review.user_name || review.author_name || 'Покупатель';

      const rating = document.createElement('div');
      rating.className = 'review-card__rating product-review-rating';
      const safeRating = Math.max(0, Math.min(5, Number(review.rating) || 0));
      rating.textContent = `${'★'.repeat(safeRating)}${'☆'.repeat(5 - safeRating)}`;

      const date = document.createElement('div');
      date.className = 'review-card__date product-review-date';
      date.textContent = formatDate(review.created_at);

      header.append(author, rating, date);

      const text = document.createElement('p');
      text.className = 'review-card__text product-review-text';
      text.innerHTML = escapeHtml(review.text || '');

      card.append(header, text);
      reviewsList.appendChild(card);
    });
  };

  const loadProductReviews = async (id) => {
    if (!id || !reviewSection) return;
    if (reviewsList) reviewsList.innerHTML = '';
    if (reviewsEmpty) reviewsEmpty.style.display = 'none';

    try {
      const res = await fetch(`/api/products/${id}/reviews`);
      if (!res.ok) {
        console.error('Failed to load reviews', res.status);
        return;
      }

      const data = await res.json();
      const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
      renderReviews(items);
    } catch (error) {
      console.error('Failed to load reviews', error);
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

    if (!productId) {
      reviewMessage.textContent = 'Товар не найден.';
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
      const res = await fetch(`/api/products/${productId}/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        let msg = (data && (data.detail || data.message)) || 'Не удалось отправить отзыв.';
        if (res.status === 401 || res.status === 403) {
          msg = 'Только авторизованные пользователи могут оставлять отзывы.';
        }
        reviewMessage.textContent = msg;
        return;
      }

      reviewForm.reset();
      reviewMessage.textContent = 'Спасибо! Отзыв отправлен.';
      await loadProductReviews(productId);
    } catch (err) {
      console.error(err);
      reviewMessage.textContent = 'Ошибка сети. Попробуйте позже.';
    }
  };

  const initReviewForm = () => {
    if (reviewFormInitialized || !reviewForm || !productId) return;
    reviewForm.addEventListener('submit', handleReviewSubmit);
    reviewFormInitialized = true;
  };

  const loadProduct = async () => {
    if (!productId) {
      renderMessage('Товар не найден');
      return;
    }

    try {
      const product = await apiGet(`/products/${productId}`);
      renderProduct(product);
      initReviewForm();
      await loadProductReviews(product.id);
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
