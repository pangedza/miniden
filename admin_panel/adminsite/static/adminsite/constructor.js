import { apiRequest } from './apiClient.js';
import { CategoryModal, ItemModal } from './modals.js';

console.log('[AdminSite] constructor.js loaded');
document.documentElement.setAttribute('data-adminsite-js', 'loaded');

const API_BASE = '/api/adminsite';
const diagnosticState = {
    jsLoaded: true,
    apiStatus: 'pending',
    apiMessage: 'Проверка API...',
};

const statusBanner = document.getElementById('constructor-status-bar') || (() => {
    const banner = document.createElement('div');
    banner.id = 'constructor-status-bar';
    document.body.prepend(banner);
    return banner;
})();

function renderDiagnostics() {
    if (!statusBanner) return;
    statusBanner.innerHTML = '';

    const pillRow = document.createElement('div');
    pillRow.className = 'diag-pills';

    const jsPill = document.createElement('span');
    jsPill.className = `diag-pill ${diagnosticState.jsLoaded ? 'ok' : 'error'}`;
    jsPill.textContent = diagnosticState.jsLoaded ? 'JS: LOADED' : 'JS: ERROR';
    pillRow.appendChild(jsPill);

    const apiPill = document.createElement('span');
    const apiOk = diagnosticState.apiStatus === 'ok';
    apiPill.className = `diag-pill ${apiOk ? 'ok' : diagnosticState.apiStatus === 'pending' ? 'muted' : 'error'}`;
    apiPill.textContent = apiOk ? 'API: OK' : diagnosticState.apiStatus === 'pending' ? 'API: CHECKING' : 'API: ERROR';
    pillRow.appendChild(apiPill);

    statusBanner.appendChild(pillRow);

    if (diagnosticState.apiMessage) {
        const text = document.createElement('div');
        text.className = `diag-message ${diagnosticState.apiStatus === 'ok' ? 'ok' : 'error'}`;
        text.textContent = diagnosticState.apiMessage;
        statusBanner.appendChild(text);
    }
}

function setApiStatus(status, message) {
    diagnosticState.apiStatus = status;
    diagnosticState.apiMessage = message;
    renderDiagnostics();
}

function reportApiFailure(error) {
    if (!error) return;
    if (error.status === 401) {
        setApiStatus('error', `API вернул 401: ${error.message}`);
        return;
    }
    if (error.status) {
        setApiStatus('error', `API недоступен: HTTP ${error.status} ${error.message || ''}`.trim());
        return;
    }
    if (error.message) {
        setApiStatus('error', error.message);
    }
}

async function checkApiHealth() {
    try {
        setApiStatus('pending', 'Проверка API...');
        const response = await fetch(`${API_BASE}/health`, { credentials: 'include' });
        const text = await response.text();

        let payload = null;
        if (text) {
            try {
                payload = JSON.parse(text);
            } catch (error) {
                setApiStatus('error', `API ответил не-JSON (${response.status}): ${text}`);
                return;
            }
        }

        if (!response.ok) {
            setApiStatus('error', `API недоступен: HTTP ${response.status} ${text}`.trim());
            return;
        }

        if (!payload?.ok) {
            setApiStatus('error', `API ответил без ok=true: ${text || 'пустой ответ'}`);
            return;
        }

        setApiStatus('ok', 'API: OK');
    } catch (error) {
        const prefix = error?.status ? `HTTP ${error.status} ` : '';
        const message = error?.message || 'API недоступен';
        setApiStatus('error', `API недоступен: ${prefix}${message}`.trim());
    }
}

renderDiagnostics();
checkApiHealth();

const state = {
    categories: { product: [], course: [] },
    items: { product: [], course: [] },
    filters: {
        product: { categoryId: '', search: '' },
        course: { categoryId: '', search: '' },
    },
};

const toastContainer = document.createElement('div');
toastContainer.className = 'toast-container';
document.body.appendChild(toastContainer);

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'error' : type === 'success' ? 'success' : ''}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

const translitMap = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
    'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ъ': '', 'ь': ''
};

function transliterate(value) {
    return value
        .split('')
        .map((ch) => {
            const lower = ch.toLowerCase();
            const mapped = translitMap[lower];
            if (mapped === undefined) return ch;
            return ch === lower ? mapped : mapped.toUpperCase();
        })
        .join('');
}

function slugify(value) {
    const transliterated = transliterate(value);
    const normalized = transliterated.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
    return normalized
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '')
        .replace(/-{2,}/g, '-');
}

function setStatus(targetId, message, isError = false) {
    const el = document.getElementById(targetId);
    if (!el) return;
    el.textContent = message || '';
    el.classList.remove('error', 'success');
    if (message) {
        el.classList.add(isError ? 'error' : 'success');
    }
}

async function callApi(path, options) {
    try {
        return await apiRequest(`${API_BASE}${path}`, options);
    } catch (error) {
        reportApiFailure(error);
        throw error;
    }
}

function categoryOptions(type) {
    return state.categories[type] || [];
}

async function loadCategories(type) {
    const target = `status-categories-${type}`;
    setStatus(target, 'Загрузка...');
    try {
        const data = await callApi(`/categories?type=${type}`);
        state.categories[type] = data;
        renderCategoryTable(type);
        renderCategorySelects(type);
        setStatus(target, `Загружено: ${data.length}`);
    } catch (error) {
        setStatus(target, error.message, true);
        showToast(error.message, 'error');
    }
}

function renderCategoryTable(type) {
    const tbody = document.getElementById(`categories-list-${type}`);
    tbody.innerHTML = '';
    state.categories[type].forEach((category) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${category.id}</td>
            <td>${category.title}</td>
            <td>${category.slug || ''}</td>
            <td>${category.is_active ? 'Да' : 'Нет'}</td>
            <td>${category.sort ?? ''}</td>
            <td>${category.created_at ? new Date(category.created_at).toLocaleString() : ''}</td>
            <td>
                <div class="table-actions">
                    <button class="btn-secondary" data-action="edit">Редактировать</button>
                    <button class="btn-danger" data-action="delete">Удалить</button>
                </div>
            </td>
        `;
        tr.querySelector('[data-action="edit"]').addEventListener('click', () => openCategoryModal(type, category));
        tr.querySelector('[data-action="delete"]').addEventListener('click', () => deleteCategory(type, category.id));
        tbody.appendChild(tr);
    });
}

function renderCategorySelects(type) {
    const filter = document.getElementById(`items-filter-${type}`);
    const selects = [filter];
    const webappSelect = document.getElementById('webapp-category');
    const webappType = document.getElementById('webapp-type');
    if (webappSelect && webappType.value === type) {
        selects.push(webappSelect);
    }

    selects.forEach((select) => {
        if (!select) return;
        select.innerHTML = '';
        if (select === filter) {
            const allOption = document.createElement('option');
            allOption.value = '';
            allOption.textContent = 'Все категории';
            select.appendChild(allOption);
        }
        state.categories[type].forEach((cat) => {
            const option = document.createElement('option');
            option.value = cat.id;
            option.textContent = cat.title;
            select.appendChild(option);
        });
    });
}

async function deleteCategory(type, id) {
    if (!confirm('Удалить категорию?')) return;
    try {
        await callApi(`/categories/${id}`, { method: 'DELETE' });
        showToast('Категория удалена', 'success');
        await loadCategories(type);
    } catch (error) {
        setStatus(`status-categories-${type}`, error.message, true);
        showToast(error.message, 'error');
    }
}

async function upsertCategory(type, payload) {
    const body = {
        type,
        title: payload.title,
        slug: payload.slug || slugify(payload.title),
        is_active: payload.is_active,
        sort: payload.sort ?? 0,
    };
    const method = payload.id ? 'PUT' : 'POST';
    const url = payload.id ? `/categories/${payload.id}` : '/categories';
    await callApi(url, { method, body });
    await loadCategories(type);
    showToast('Категория сохранена', 'success');
}

async function loadItems(type) {
    const filter = state.filters[type];
    const params = new URLSearchParams({ type });
    if (filter.categoryId) {
        params.append('category_id', filter.categoryId);
    }
    const target = `status-items-${type}`;
    setStatus(target, 'Загрузка...');
    try {
        const data = await callApi(`/items?${params.toString()}`);
        state.items[type] = data;
        renderItemsTable(type);
        setStatus(target, `Загружено: ${data.length}`);
    } catch (error) {
        state.items[type] = [];
        renderItemsTable(type);
        setStatus(target, error.message, true);
        showToast(error.message, 'error');
    }
}

function renderItemsTable(type) {
    const tbody = document.getElementById(`items-list-${type}`);
    tbody.innerHTML = '';
    const filter = state.filters[type];
    const search = filter.search.toLowerCase();
    const rows = state.items[type].filter((item) => {
        const title = item.title || '';
        return !search || title.toLowerCase().includes(search);
    });
    rows.forEach((item) => {
        const categoryTitle = state.categories[type].find((c) => c.id === item.category_id)?.title || '';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.id}</td>
            <td>${item.title}</td>
            <td>${categoryTitle}</td>
            <td>${item.price ?? ''}</td>
            <td>${item.is_active ? 'Да' : 'Нет'}</td>
            <td>${item.sort ?? ''}</td>
            <td>
                <div class="table-actions">
                    <button class="btn-secondary" data-action="edit">Редактировать</button>
                    <button class="btn-danger" data-action="delete">Удалить</button>
                </div>
            </td>
        `;
        tr.querySelector('[data-action="edit"]').addEventListener('click', () => openItemModal(type, item));
        tr.querySelector('[data-action="delete"]').addEventListener('click', () => deleteItem(type, item.id));
        tbody.appendChild(tr);
    });
}

async function deleteItem(type, id) {
    if (!confirm('Удалить элемент?')) return;
    try {
        await callApi(`/items/${id}`, { method: 'DELETE' });
        await loadItems(type);
        showToast('Элемент удалён', 'success');
    } catch (error) {
        setStatus(`status-items-${type}`, error.message, true);
        showToast(error.message, 'error');
    }
}

async function upsertItem(type, payload) {
    const body = {
        type,
        category_id: payload.category_id,
        title: payload.title,
        slug: payload.slug || slugify(payload.title),
        price: payload.price ?? 0,
        image_url: payload.image_url,
        short_text: payload.short_text,
        description: payload.description,
        is_active: payload.is_active,
        sort: payload.sort ?? 0,
    };
    const method = payload.id ? 'PUT' : 'POST';
    const url = payload.id ? `/items/${payload.id}` : '/items';
    await callApi(url, { method, body });
    await loadItems(type);
    showToast('Элемент сохранён', 'success');
}

async function loadWebappSettings() {
    const type = document.getElementById('webapp-type').value;
    const scope = document.getElementById('webapp-scope').value;
    const categorySelect = document.getElementById('webapp-category');
    const params = new URLSearchParams({ type });
    if (scope === 'category' && categorySelect.value) {
        params.append('category_id', categorySelect.value);
    }
    try {
        const data = await callApi(`/webapp-settings?${params.toString()}`);
        document.getElementById('webapp-enabled').checked = data.action_enabled;
        document.getElementById('webapp-label').value = data.action_label || '';
        document.getElementById('webapp-min-selected').value = data.min_selected ?? 0;
        setStatus('status-webapp', 'Настройки загружены');
    } catch (error) {
        document.getElementById('webapp-enabled').checked = false;
        document.getElementById('webapp-label').value = '';
        document.getElementById('webapp-min-selected').value = 0;
        setStatus('status-webapp', error.message, true);
        showToast(error.message, 'error');
    }
}

async function saveWebappSettings(event) {
    event.preventDefault();
    const button = event.submitter || event.target.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    const type = document.getElementById('webapp-type').value;
    const scope = document.getElementById('webapp-scope').value;
    const categorySelect = document.getElementById('webapp-category');
    const payload = {
        scope,
        type,
        category_id: scope === 'category' ? Number(categorySelect.value) : null,
        action_enabled: document.getElementById('webapp-enabled').checked,
        action_label: document.getElementById('webapp-label').value || null,
        min_selected: Number(document.getElementById('webapp-min-selected').value) || 0,
    };
    try {
        await callApi('/webapp-settings', { method: 'PUT', body: payload });
        setStatus('status-webapp', 'Настройки сохранены');
        showToast('Настройки сохранены', 'success');
        await loadWebappSettings();
    } catch (error) {
        setStatus('status-webapp', error.message, true);
        showToast(error.message, 'error');
    } finally {
        if (button) button.disabled = false;
    }
}

function toggleWebappCategory() {
    const scope = document.getElementById('webapp-scope').value;
    document.getElementById('webapp-category-wrapper').style.display = scope === 'category' ? 'block' : 'none';
}

function setupTabs() {
    document.querySelectorAll('.tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
            document.querySelectorAll('.panel').forEach((panel) => {
                panel.classList.toggle('active', panel.id === `panel-${target}`);
            });
            tab.classList.add('active');
        });
    });
}

const categoryModals = {
    product: new CategoryModal({ title: 'Категория товара', onSubmit: (payload) => upsertCategory('product', payload) }),
    course: new CategoryModal({ title: 'Категория мастер-классов', onSubmit: (payload) => upsertCategory('course', payload) }),
};

const itemModals = {
    product: new ItemModal({
        title: 'Товар',
        categoriesProvider: (type) => categoryOptions(type),
        onSubmit: (payload) => upsertItem('product', payload),
    }),
    course: new ItemModal({
        title: 'Мастер-класс',
        categoriesProvider: (type) => categoryOptions(type),
        onSubmit: (payload) => upsertItem('course', payload),
    }),
};

function openCategoryModal(type, category = null) {
    categoryModals[type].setData(category);
    categoryModals[type].open();
}

function openItemModal(type, item = null) {
    itemModals[type].setData(item, type);
    itemModals[type].open();
}

function setupButtons() {
    ['product', 'course'].forEach((type) => {
        document.getElementById(`category-create-${type}`).addEventListener('click', () => openCategoryModal(type));
        document.getElementById(`item-create-${type}`).addEventListener('click', () => openItemModal(type));
        document.getElementById(`items-filter-${type}`).addEventListener('change', (event) => {
            state.filters[type].categoryId = event.target.value;
            loadItems(type);
        });
        document.getElementById(`items-search-${type}`).addEventListener('input', (event) => {
            state.filters[type].search = event.target.value;
            renderItemsTable(type);
        });
    });

    document.getElementById('webapp-type').addEventListener('change', async () => {
        renderCategorySelects(document.getElementById('webapp-type').value);
        toggleWebappCategory();
        await loadWebappSettings();
    });
    document.getElementById('webapp-scope').addEventListener('change', async () => {
        toggleWebappCategory();
        await loadWebappSettings();
    });
    document.getElementById('webapp-category').addEventListener('change', loadWebappSettings);
    document.getElementById('webapp-form').addEventListener('submit', saveWebappSettings);
    document.getElementById('webapp-reload').addEventListener('click', (e) => {
        e.preventDefault();
        loadWebappSettings();
    });
}

async function bootstrap() {
    setupTabs();
    setupButtons();
    toggleWebappCategory();
    try {
        await loadCategories('product');
        await loadCategories('course');
        await loadItems('product');
        await loadItems('course');
        await loadWebappSettings();
        setStatus('global-status', 'Данные загружены');
    } catch (error) {
        setStatus('global-status', error.message, true);
        showToast(error.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', bootstrap);
