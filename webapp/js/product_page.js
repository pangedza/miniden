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
