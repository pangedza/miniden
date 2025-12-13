const homePostsSection = document.getElementById('home-posts');
const homePostsGrid = document.getElementById('home-posts-grid');
const homePostsEmpty = document.getElementById('home-posts-empty');

function renderPosts(posts) {
  if (!homePostsSection || !homePostsGrid || !homePostsEmpty) return;
  if (!posts || !posts.length) {
    homePostsGrid.innerHTML = '';
    homePostsSection.style.display = 'block';
    homePostsEmpty.style.display = 'block';
    initRevealOnScroll();
    return;
  }

  const items = posts.slice(0, 4);
  homePostsGrid.innerHTML = '';
  items.forEach((post) => {
    const card = document.createElement('div');
    card.className = 'card home-post-card hover-lift reveal';
    card.innerHTML = `
      <h3>${post.title}</h3>
      <p>${post.short_text}</p>
      ${post.link ? `<a class="btn secondary" href="${post.link}" target="_blank" rel="noopener">Подробнее</a>` : ''}
    `;
    homePostsGrid.appendChild(card);
  });
  homePostsEmpty.style.display = 'none';
  homePostsSection.style.display = 'block';
  initRevealOnScroll();
}

function initRevealOnScroll() {
  const elements = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window) || !elements.length) {
    elements.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.2,
      rootMargin: '0px 0px -40px 0px',
    }
  );

  elements.forEach((el) => observer.observe(el));
}

async function loadHomeData() {
  try {
    const data = await apiGet('/home');
    if (data?.posts) {
      renderPosts(data.posts);
    }
  } catch (e) {
    console.warn('Не удалось загрузить данные главной страницы', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initRevealOnScroll();
  loadHomeData();
});
