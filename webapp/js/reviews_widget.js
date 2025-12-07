(function () {
  const DEFAULT_RATING = 5;

  const formatDate = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
  };

  const createStars = (rating) => {
    const safeRating = Math.max(0, Math.min(5, Number(rating) || 0));
    return `${'★'.repeat(safeRating)}${'☆'.repeat(5 - safeRating)}`;
  };

  const updateActiveStars = (starsEl, rating) => {
    if (!starsEl) return;
    const value = Number(rating) || 0;
    starsEl.querySelectorAll('span').forEach((star) => {
      const starValue = Number(star.dataset.value) || 0;
      if (starValue <= value) {
        star.classList.add('reviews-star--active');
      } else {
        star.classList.remove('reviews-star--active');
      }
    });
  };

  const renderPhotosPreview = (container, files) => {
    if (!container) return;
    container.innerHTML = '';

    Array.from(files || []).forEach((file) => {
      const url = URL.createObjectURL(file);
      const img = document.createElement('img');
      img.src = url;
      img.alt = file.name || 'Фото отзыва';
      container.appendChild(img);
    });
  };

  const buildWidgetHtml = () => {
    return `
      <section class="reviews-widget">
        <div class="reviews-header">
          <h2>Отзывы</h2>
          <button type="button" class="reviews-toggle-btn">Оставить отзыв</button>
        </div>

        <div class="reviews-accordion reviews-accordion--collapsed">
          <form class="reviews-form">
            <div class="reviews-rating">
              <span class="reviews-rating-label">Оценка</span>
              <div class="reviews-stars" data-value="${DEFAULT_RATING}">
                <span data-value="1" aria-label="1 звезда">★</span>
                <span data-value="2" aria-label="2 звезды">★</span>
                <span data-value="3" aria-label="3 звезды">★</span>
                <span data-value="4" aria-label="4 звезды">★</span>
                <span data-value="5" aria-label="5 звёзд">★</span>
              </div>
            </div>

            <label class="reviews-field">
              <span>Отзыв</span>
              <textarea name="text" rows="4" required placeholder="Расскажите, что понравилось или что можно улучшить"></textarea>
            </label>

            <label class="reviews-field">
              <span>Фотографии (по желанию)</span>
              <input type="file" name="photos" accept="image/*" multiple>
            </label>

            <div class="reviews-photos-preview"></div>

            <button type="submit" class="btn-primary reviews-submit-btn">Отправить отзыв</button>
            <div class="reviews-form-message" aria-live="polite"></div>
          </form>
        </div>

        <div class="reviews-list-wrapper">
          <div class="reviews-empty">Пока нет отзывов. Будьте первым!</div>
          <div class="reviews-list"></div>
        </div>
      </section>
    `;
  };

  const initReviewsWidget = (options) => {
    const { rootEl, type, itemId } = options || {};
    if (!rootEl || !type || !itemId) return;

    const apiUrl = type === 'masterclass'
      ? `/api/masterclasses/${itemId}/reviews`
      : `/api/products/${itemId}/reviews`;

    rootEl.innerHTML = buildWidgetHtml();

    const accordion = rootEl.querySelector('.reviews-accordion');
    const toggleBtn = rootEl.querySelector('.reviews-toggle-btn');
    const form = rootEl.querySelector('.reviews-form');
    const starsEl = rootEl.querySelector('.reviews-stars');
    const textarea = rootEl.querySelector('textarea[name="text"]');
    const fileInput = rootEl.querySelector('input[name="photos"]');
    const preview = rootEl.querySelector('.reviews-photos-preview');
    const messageEl = rootEl.querySelector('.reviews-form-message');
    const reviewsList = rootEl.querySelector('.reviews-list');
    const reviewsEmpty = rootEl.querySelector('.reviews-empty');

    let rating = DEFAULT_RATING;
    updateActiveStars(starsEl, rating);

    const toggleAccordion = () => {
      if (!accordion) return;
      accordion.classList.toggle('reviews-accordion--collapsed');
    };

    toggleBtn?.addEventListener('click', toggleAccordion);

    starsEl?.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const value = Number(target.dataset.value);
      if (!value) return;
      rating = value;
      starsEl.dataset.value = String(rating);
      updateActiveStars(starsEl, rating);
    });

    fileInput?.addEventListener('change', (event) => {
      const input = event.target;
      renderPhotosPreview(preview, input.files || []);
    });

    const renderReviews = (items) => {
      if (!reviewsList || !reviewsEmpty) return;
      reviewsList.innerHTML = '';
      reviewsEmpty.style.display = 'none';

      const reviews = Array.isArray(items) ? items : Array.isArray(items?.items) ? items.items : [];
      if (!reviews.length) {
        reviewsEmpty.style.display = '';
        return;
      }

      reviews.forEach((review) => {
        const card = document.createElement('article');
        card.className = 'review-card';

        const header = document.createElement('header');
        header.className = 'review-card-header';

        const author = document.createElement('strong');
        author.className = 'review-author';
        author.textContent = review.author_name || review.user_name || 'Пользователь';

        const ratingEl = document.createElement('span');
        ratingEl.className = 'review-rating';
        ratingEl.textContent = createStars(review.rating);

        header.append(author, ratingEl);

        const text = document.createElement('div');
        text.className = 'review-text';
        text.textContent = review.text || '';

        const photosWrapper = document.createElement('div');
        photosWrapper.className = 'review-photos';
        const photos = Array.isArray(review?.photos) ? review.photos : [];
        photos.forEach((url) => {
          if (!url) return;
          const img = document.createElement('img');
          img.src = url;
          img.alt = 'Фото отзыва';
          photosWrapper.appendChild(img);
        });

        const footer = document.createElement('div');
        footer.className = 'review-date';
        footer.textContent = formatDate(review.created_at);

        card.append(header, text);
        if (photosWrapper.childElementCount) {
          card.appendChild(photosWrapper);
        }
        card.appendChild(footer);
        reviewsList.appendChild(card);
      });
    };

    const loadReviews = async () => {
      if (!apiUrl) return;
      try {
        const res = await fetch(apiUrl);
        if (!res.ok) {
          console.error('Failed to load reviews', res.status);
          return;
        }
        const data = await res.json();
        renderReviews(data);
      } catch (error) {
        console.error('Failed to load reviews', error);
      }
    };

    const submitReview = async (event) => {
      event.preventDefault();
      if (!form || !textarea) return;
      messageEl.textContent = '';

      const textValue = textarea.value.trim();
      if (!textValue) {
        messageEl.textContent = 'Пожалуйста, напишите текст отзыва.';
        return;
      }

      const formData = new FormData();
      formData.append('rating', String(rating));
      formData.append('text', textValue);

      if (fileInput?.files?.length) {
        Array.from(fileInput.files).forEach((file) => formData.append('photos', file));
      }

      try {
        const res = await fetch(apiUrl, {
          method: 'POST',
          body: formData,
        });

        const data = await res.json().catch(() => null);

        if (!res.ok) {
          const msg = (data && (data.detail || data.message)) || 'Не удалось отправить отзыв.';
          messageEl.textContent = msg;
          return;
        }

        form.reset();
        rating = DEFAULT_RATING;
        updateActiveStars(starsEl, rating);
        renderPhotosPreview(preview, []);
        messageEl.textContent = 'Отзыв отправлен и появится после модерации';
        await loadReviews();
      } catch (error) {
        console.error('Failed to submit review', error);
        messageEl.textContent = 'Ошибка сети. Попробуйте позже.';
      }
    };

    form?.addEventListener('submit', submitReview);
    loadReviews();
  };

  window.initReviewsWidget = initReviewsWidget;
})();
