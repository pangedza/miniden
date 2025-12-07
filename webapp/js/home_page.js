const homeBannerCard = document.getElementById('home-banner-card');
const homeBannerCover = document.getElementById('home-banner-cover');
const homeBannerTitle = document.getElementById('home-banner-title');
const homeBannerSubtitle = document.getElementById('home-banner-subtitle');
const homeBannerButton = document.getElementById('home-banner-button');
const whyContainer = document.getElementById('why-list');
const howIntro = document.getElementById('how-intro');
const howContainer = document.getElementById('how-list');
const homePostsSection = document.getElementById('home-posts');
const homePostsGrid = document.getElementById('home-posts-grid');
const homePostsEmpty = document.getElementById('home-posts-empty');

let homeBanners = [];
let bannerIndex = 0;
let bannerTimer = null;

function applyBanner(banner) {
  if (!banner || !homeBannerCard) return;
  if (homeBannerTitle) homeBannerTitle.textContent = banner.title || 'Популярный набор';
  if (homeBannerSubtitle) homeBannerSubtitle.textContent = banner.subtitle || 'Тёплый подарок от MiniDeN';

  if (homeBannerCover) {
    if (banner.image_url) {
      homeBannerCover.style.backgroundImage = `url(${banner.image_url})`;
      homeBannerCover.classList.add('with-image');
      homeBannerCover.textContent = '';
    } else {
      homeBannerCover.style.backgroundImage = '';
      homeBannerCover.classList.remove('with-image');
      homeBannerCover.textContent = '🧺 Популярный набор';
    }
  }

  if (homeBannerButton) {
    homeBannerButton.textContent = banner.button_text || 'Смотреть в каталоге';
    homeBannerButton.href = banner.button_link || 'products.html';
  }
}

function startBannerRotation() {
  if (bannerTimer) {
    clearInterval(bannerTimer);
    bannerTimer = null;
  }
  if (homeBanners.length <= 1) return;
  bannerTimer = window.setInterval(() => {
    bannerIndex = (bannerIndex + 1) % homeBanners.length;
    applyBanner(homeBanners[bannerIndex]);
  }, 7000);
}

function renderSections(sections) {
  if (!Array.isArray(sections)) return;
  const whySections = sections.filter((s) => String(s.slug || '').startsWith('why'));
  const howSections = sections.filter((s) => String(s.slug || '').startsWith('how'));

  if (whyContainer && whySections.length) {
    whyContainer.innerHTML = '';
    whySections.forEach((item) => {
      const node = document.createElement('div');
      node.className = 'benefit';
      node.innerHTML = `<strong>${item.icon || '✨'} ${item.title}</strong><p>${item.text}</p>`;
      whyContainer.appendChild(node);
    });
  }

  if (howSections.length) {
    const [intro, ...steps] = howSections;
    if (howIntro && intro) {
      const strong = howIntro.querySelector('strong');
      const p = howIntro.querySelector('p');
      if (strong) strong.textContent = intro.title;
      if (p) p.textContent = intro.text;
    }
    if (howContainer) {
      howContainer.innerHTML = '';
      steps.forEach((item, index) => {
        const step = document.createElement('div');
        step.className = 'step';
        const order = item.sort_order ?? index + 1;
        step.innerHTML = `<strong>${order}) ${item.title}</strong><p>${item.text}</p>`;
        howContainer.appendChild(step);
      });
    }
  }
}

function renderPosts(posts) {
  if (!homePostsSection || !homePostsGrid || !homePostsEmpty) return;
  if (!posts || !posts.length) {
    homePostsGrid.innerHTML = '';
    homePostsSection.style.display = 'block';
    homePostsEmpty.style.display = 'block';
    return;
  }

  const items = posts.slice(0, 4);
  homePostsGrid.innerHTML = '';
  items.forEach((post) => {
    const card = document.createElement('div');
    card.className = 'card home-post-card';
    card.innerHTML = `
      <h3>${post.title}</h3>
      <p>${post.short_text}</p>
      ${post.link ? `<a class="btn secondary" href="${post.link}" target="_blank" rel="noopener">Подробнее</a>` : ''}
    `;
    homePostsGrid.appendChild(card);
  });
  homePostsEmpty.style.display = 'none';
  homePostsSection.style.display = 'block';
}

async function loadHomeData() {
  try {
    const data = await apiGet('/home');
    if (data?.banners?.length) {
      homeBanners = data.banners;
      bannerIndex = 0;
      applyBanner(homeBanners[0]);
      startBannerRotation();
    }
    if (data?.sections?.length) {
      renderSections(data.sections);
    }
    if (data?.posts) {
      renderPosts(data.posts);
    }
  } catch (e) {
    console.warn('Не удалось загрузить данные главной страницы', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadHomeData();
});

