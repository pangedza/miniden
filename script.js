const STORAGE_KEY = 'handmade-baskets-cart';
const cart = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

const saveCart = () => localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
const getItemsCount = () => cart.reduce((total, item) => total + item.quantity, 0);

const cartCountBadge = document.getElementById('cart-count');
const updateCartCount = () => {
  if (cartCountBadge) {
    cartCountBadge.textContent = getItemsCount();
  }
};

updateCartCount();

const openModal = () => {
  const modal = document.getElementById('addedModal');
  if (!modal) return;
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');

  const closeButton = document.getElementById('closeModal');
  const closeModal = () => {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  };

  if (closeButton) {
    closeButton.addEventListener('click', closeModal, { once: true });
  }

  modal.addEventListener(
    'click',
    (event) => {
      if (event.target === modal) {
        closeModal();
      }
    },
    { once: true }
  );
};

const addButtons = document.querySelectorAll('.add-to-cart');
addButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const name = button.dataset.name;
    const price = Number.parseInt(button.dataset.price, 10);

    if (!name || Number.isNaN(price)) return;

    const existingItem = cart.find((item) => item.name === name);

    if (existingItem) {
      existingItem.quantity += 1;
    } else {
      cart.push({ name, price, quantity: 1 });
    }

    saveCart();
    updateCartCount();
    openModal();
  });
});

const cartTableBody = document.querySelector('#cart-table tbody');
const totalPriceElement = document.getElementById('total-price');
const checkoutButton = document.getElementById('checkout');

const renderCart = () => {
  if (!cartTableBody || !totalPriceElement) {
    updateCartCount();
    return;
  }

  cartTableBody.innerHTML = '';

  if (cart.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = '<td colspan="4">Корзина пока пуста — возвращайтесь в каталог!</td>';
    cartTableBody.appendChild(emptyRow);
    totalPriceElement.textContent = '0';
    if (checkoutButton) checkoutButton.disabled = true;
    updateCartCount();
    return;
  }

  let total = 0;

  cart.forEach((item, index) => {
    const row = document.createElement('tr');
    const subtotal = item.price * item.quantity;
    total += subtotal;

    row.innerHTML = `
      <td>${item.name}</td>
      <td>
        <div class="quantity-control">
          <button class="qty-btn decrease" data-index="${index}" aria-label="Убавить количество">−</button>
          <span>${item.quantity}</span>
          <button class="qty-btn increase" data-index="${index}" aria-label="Добавить количество">+</button>
        </div>
      </td>
      <td>${subtotal.toLocaleString('ru-RU')} ₽</td>
      <td><button class="remove-btn" data-index="${index}" aria-label="Удалить товар">✖</button></td>
    `;

    cartTableBody.appendChild(row);
  });

  totalPriceElement.textContent = total.toLocaleString('ru-RU');
  if (checkoutButton) checkoutButton.disabled = cart.length === 0;
  updateCartCount();
};

if (cartTableBody) {
  renderCart();

  cartTableBody.addEventListener('click', (event) => {
    const target = event.target;
    const index = Number.parseInt(target.dataset.index, 10);

    if (Number.isNaN(index)) return;

    if (target.classList.contains('increase')) {
      cart[index].quantity += 1;
    } else if (target.classList.contains('decrease')) {
      cart[index].quantity -= 1;
      if (cart[index].quantity <= 0) {
        cart.splice(index, 1);
      }
    } else if (target.classList.contains('remove-btn')) {
      cart.splice(index, 1);
    } else {
      return;
    }

    saveCart();
    renderCart();
  });
}

if (checkoutButton) {
  checkoutButton.addEventListener('click', () => {
    if (cart.length === 0) return;

    alert('Спасибо! Мы свяжемся с вами для подтверждения заказа.');
    cart.splice(0, cart.length);
    saveCart();
    renderCart();
  });
}
