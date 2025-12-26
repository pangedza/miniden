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

const DEFAULT_TYPES = ['product', 'course'];

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
    types: [],
    categories: {},
    items: {},
    filters: {},
    ui: {
        tabsContainer: null,
        panelsContainer: null,
        webappTab: null,
    },
    activeTab: null,
};

const defaultWebappSettings = {
    action_enabled: true,
    action_label: 'Оформить',
    min_selected: 1,
};

const homepageDefaults = {
    templateId: 'services',
    blocks: [],
};

let homepageConfig = homepageDefaults;

function getElementOrWarn(id) {
    const el = document.getElementById(id);
    if (!el) {
        console.warn(`[AdminSite constructor] Элемент #${id} не найден, часть UI может не работать корректно.`);
    }
    return el;
}

function bindElement(id, event, handler) {
    const el = getElementOrWarn(id);
    if (!el) return null;
    el.addEventListener(event, handler);
    return el;
}

const modalHistory = [];
let handlingPopState = false;

if (!window.history.state || !window.history.state.adminsiteRoot) {
    window.history.replaceState(
        { ...(window.history.state || {}), adminsiteRoot: true },
        '',
        window.location.pathname + window.location.search,
    );
}

function registerModal(modal) {
    modal.setCloseHandler((reason) => closeTrackedModal(modal, reason));
    modal.onClose(() => {
        const idx = modalHistory.lastIndexOf(modal);
        if (idx !== -1) {
            modalHistory.splice(idx, 1);
        }
    });
}

function closeTrackedModal(modal, reason = 'manual', { skipHistory = false } = {}) {
    if (!modal) return;
    const idx = modalHistory.lastIndexOf(modal);
    if (idx !== -1) {
        modalHistory.splice(idx, 1);
    }
    modal.close(reason);

    const currentState = window.history.state;
    if (
        !skipHistory &&
        !handlingPopState &&
        currentState?.adminsiteModal === modal.__adminsiteStateId
    ) {
        handlingPopState = true;
        window.history.back();
        handlingPopState = false;
    }
}

function openTrackedModal(modal, stateId) {
    if (!modal?.backdrop?.hidden) return;
    modal.__adminsiteStateId = stateId;
    modalHistory.push(modal);
    window.history.pushState({ adminsiteModal: stateId }, '', window.location.pathname + window.location.search);
    modal.open();
}

function closeTopModal(reason = 'manual', { skipHistory = false } = {}) {
    const modal = modalHistory.pop();
    if (modal) {
        closeTrackedModal(modal, reason, { skipHistory });
        return true;
    }
    return false;
}

window.addEventListener('popstate', () => {
    handlingPopState = true;
    try {
        if (closeTopModal('history', { skipHistory: true })) return;
        if (window.history.state?.adminsiteTab) {
            setActiveTab(window.history.state.adminsiteTab, { pushHistory: false });
            return;
        }
        if (!window.history.state?.adminsiteRoot) return;
        // Ensure there is always at least one state entry to prevent empty history stack
        window.history.replaceState(
            { ...(window.history.state || {}), adminsiteRoot: true },
            '',
            window.location.pathname + window.location.search,
        );
    } finally {
        handlingPopState = false;
    }
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeTopModal('escape');
    }
});

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

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

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

function normalizeSlugInput(value) {
    return slugify(value || '');
}

function normalizeSlugForSubmit(rawValue) {
    const trimmed = (rawValue || '').trim();
    if (!trimmed) return { value: '', error: '' };

    const normalized = normalizeSlugInput(trimmed);
    if (!normalized || !SLUG_PATTERN.test(normalized)) {
        return { value: '', error: 'Slug может содержать только латиницу, цифры и дефисы.' };
    }

    return { value: normalized, error: '' };
}

function ensureTypeState(type) {
    if (!state.types.includes(type)) {
        state.types.push(type);
    }
    if (!state.categories[type]) {
        state.categories[type] = [];
    }
    if (!state.items[type]) {
        state.items[type] = [];
    }
    if (!state.filters[type]) {
        state.filters[type] = { categoryId: '', search: '' };
    }
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

function attachSlugHelpers(modal) {
    if (!modal?.form) return;

    const titleInput = modal.form.querySelector('input[name="title"]');
    const slugInput = modal.form.querySelector('input[name="slug"]');
    if (!titleInput || !slugInput) return;

    let slugTouched = false;

    if (!slugInput.nextElementSibling?.classList?.contains('slug-hint')) {
        const hint = document.createElement('p');
        hint.className = 'muted slug-hint';
        hint.textContent = 'Slug: латиница, цифры и дефисы. Можно оставить пустым для автогенерации.';
        slugInput.insertAdjacentElement('afterend', hint);
    }

    titleInput.addEventListener('input', () => {
        const currentSlug = slugInput.value.trim();
        if (!slugTouched || !currentSlug) {
            slugInput.value = normalizeSlugInput(titleInput.value);
        }
    });

    slugInput.addEventListener('input', () => {
        slugTouched = true;
        const normalized = normalizeSlugInput(slugInput.value);
        if (slugInput.value !== normalized) {
            slugInput.value = normalized;
        }
    });

    slugInput.addEventListener('blur', () => {
        const normalized = normalizeSlugInput(slugInput.value);
        if (slugInput.value !== normalized) {
            slugInput.value = normalized;
        }
    });

    modal.onClose(() => {
        slugTouched = false;
    });
}

function normalizeWebappType(value, { statusTarget } = {}) {
    const available = state.types.length ? state.types : DEFAULT_TYPES;
    if (available.includes(value)) {
        return value;
    }
    const fallback = available[0];
    console.warn(
        `[AdminSite constructor] Некорректный type для WebApp настроек: ${value}, используем ${fallback}`,
    );
    if (statusTarget) {
        setStatus(statusTarget, `Некорректный тип, переключено на ${fallback}`, true);
    }
    return fallback;
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
    ensureTypeState(type);
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
        const publicUrl = category.slug ? `/c/${category.slug}` : '';
        const publicLink = publicUrl
            ? `<a href="${publicUrl}" class="link" target="_blank" rel="noopener">${publicUrl}</a>`
            : '<span class="muted">—</span>';
        const itemsLabel = type === 'course' ? 'Мастер-классы' : 'Товары';
        tr.innerHTML = `
            <td>${category.id}</td>
            <td>${category.title}</td>
            <td>${category.slug || ''}</td>
            <td>${publicLink}</td>
            <td>${category.is_active ? 'Да' : 'Нет'}</td>
            <td>${category.sort ?? ''}</td>
            <td>${category.created_at ? new Date(category.created_at).toLocaleString() : ''}</td>
            <td>
                <div class="table-actions">
                    <button class="btn-secondary" data-action="open-page" ${publicUrl ? '' : 'disabled'}>Страница</button>
                    <button class="btn-secondary" data-action="items">${itemsLabel}</button>
                    <button class="btn-secondary" data-action="edit">Редактировать</button>
                    <button class="btn-danger" data-action="delete">Удалить</button>
                </div>
            </td>
        `;
        tr.querySelector('[data-action="open-page"]')?.addEventListener('click', () => {
            if (publicUrl) window.open(publicUrl, '_blank', 'noopener');
        });
        tr.querySelector('[data-action="items"]')?.addEventListener('click', () => {
            const filter = document.getElementById(`items-filter-${type}`);
            if (filter) {
                filter.value = String(category.id);
            }
            state.filters[type].categoryId = String(category.id);
            loadItems(type);
            setActiveTab(`panel-${type}`);
        });
        tr.querySelector('[data-action="edit"]').addEventListener('click', () => openCategoryModal(type, category));
        tr.querySelector('[data-action="delete"]').addEventListener('click', () => deleteCategory(type, category.id));
        tbody.appendChild(tr);
    });
}

function renderCategorySelects(type) {
    ensureTypeState(type);
    if (!type || !state.categories[type]) {
        console.warn(`[AdminSite constructor] Неизвестный тип для категорий: ${type}`);
        return;
    }

    const filter = getElementOrWarn(`items-filter-${type}`);
    const selects = [];
    if (filter) {
        selects.push(filter);
    }
    const webappSelect = getElementOrWarn('webapp-category');
    const webappType = getElementOrWarn('webapp-type');
    if (webappSelect && webappType && webappType.value === type) {
        selects.push(webappSelect);
    }

    selects.forEach((select) => {
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
    const { value: normalizedSlug, error: slugError } = normalizeSlugForSubmit(payload.slug);
    if (slugError) throw new Error(slugError);

    const body = {
        type,
        title: payload.title,
        slug: normalizedSlug || null,
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
    ensureTypeState(type);
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
    const { value: normalizedSlug, error: slugError } = normalizeSlugForSubmit(payload.slug);
    if (slugError) throw new Error(slugError);

    const body = {
        type,
        category_id: payload.category_id,
        title: payload.title,
        slug: normalizedSlug || null,
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
    const typeSelect = getElementOrWarn('webapp-type');
    const scopeSelect = getElementOrWarn('webapp-scope');
    const categorySelect = getElementOrWarn('webapp-category');

    if (!typeSelect || !scopeSelect || !categorySelect) {
        console.warn('[AdminSite constructor] WebApp форма не найдена, пропускаем загрузку настроек.');
        return;
    }

    const type = normalizeWebappType(typeSelect.value, { statusTarget: 'status-webapp' });
    if (typeSelect.value !== type) {
        typeSelect.value = type;
    }
    const scope = scopeSelect.value;
    const params = new URLSearchParams({ type });
    if (scope === 'category') {
        if (!categorySelect.value) {
            setStatus('status-webapp', 'Выберите категорию для загрузки настроек', true);
            return;
        }
        params.append('category_id', categorySelect.value);
    }
    try {
        const data = await callApi(`/webapp-settings?${params.toString()}`);
        const enabled = getElementOrWarn('webapp-enabled');
        const label = getElementOrWarn('webapp-label');
        const minSelected = getElementOrWarn('webapp-min-selected');
        if (enabled) enabled.checked = data?.action_enabled ?? defaultWebappSettings.action_enabled;
        if (label) label.value = data?.action_label ?? defaultWebappSettings.action_label;
        if (minSelected) minSelected.value = data?.min_selected ?? defaultWebappSettings.min_selected;
        setStatus('status-webapp', 'Настройки загружены');
    } catch (error) {
        const enabled = getElementOrWarn('webapp-enabled');
        const label = getElementOrWarn('webapp-label');
        const minSelected = getElementOrWarn('webapp-min-selected');
        if (enabled) enabled.checked = defaultWebappSettings.action_enabled;
        if (label) label.value = defaultWebappSettings.action_label;
        if (minSelected) minSelected.value = defaultWebappSettings.min_selected;
        const message = error.status === 404
            ? 'Настройки не найдены, применены значения по умолчанию'
            : error.message;
        setStatus('status-webapp', message, error.status !== 404);
        if (error.status !== 404) {
            showToast(error.message, 'error');
        } else {
            setApiStatus('ok', message);
        }
    }
}

async function saveWebappSettings(event) {
    event.preventDefault();
    const button = event.submitter || event.target.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    const typeSelect = getElementOrWarn('webapp-type');
    const scopeSelect = getElementOrWarn('webapp-scope');
    const categorySelect = getElementOrWarn('webapp-category');
    const enabled = getElementOrWarn('webapp-enabled');
    const label = getElementOrWarn('webapp-label');
    const minSelected = getElementOrWarn('webapp-min-selected');

    if (!typeSelect || !scopeSelect || !categorySelect || !enabled || !label || !minSelected) {
        console.warn('[AdminSite constructor] WebApp форма неполная, сохранять нечего.');
        if (button) button.disabled = false;
        return;
    }

    const type = normalizeWebappType(typeSelect.value, { statusTarget: 'status-webapp' });
    if (typeSelect.value !== type) {
        typeSelect.value = type;
    }
    const scope = scopeSelect.value;
    if (scope === 'category' && !categorySelect.value) {
        setStatus('status-webapp', 'Выберите категорию перед сохранением', true);
        if (button) button.disabled = false;
        return;
    }
    const payload = {
        scope,
        type,
        category_id: scope === 'category' ? Number(categorySelect.value) : null,
        action_enabled: enabled.checked,
        action_label: label.value || null,
        min_selected: Number(minSelected.value) || 0,
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
    const scopeSelect = getElementOrWarn('webapp-scope');
    const wrapper = getElementOrWarn('webapp-category-wrapper');
    const categorySelect = getElementOrWarn('webapp-category');
    if (!scopeSelect || !wrapper) return;

    const scope = scopeSelect.value;
    wrapper.style.display = scope === 'category' ? 'block' : 'none';
    if (categorySelect) {
        categorySelect.toggleAttribute('disabled', scope !== 'category');
    }
}

function humanizeType(type) {
    if (!type) return 'Раздел';
    return type.charAt(0).toUpperCase() + type.slice(1);
}

function createTypeTab(type) {
    const tab = document.createElement('button');
    tab.className = 'tab';
    tab.dataset.target = `panel-${type}`;
    tab.textContent = humanizeType(type);
    tab.addEventListener('click', () => setActiveTab(tab.dataset.target));
    return tab;
}

function createTypePanel(type) {
    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.id = `panel-${type}`;
    const label = humanizeType(type);
    panel.innerHTML = `
        <div class="card">
            <div class="table-top">
                <div>
                    <h3 style="margin:0;">Категории (${label})</h3>
                    <p class="muted">Slug можно оставить пустым — сервер сгенерирует его.</p>
                </div>
                <button id="category-create-${type}" class="btn-primary" type="button">Создать</button>
            </div>
            <div class="status" id="status-categories-${type}"></div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Title</th>
                            <th>Slug</th>
                            <th>Страница</th>
                            <th>Active</th>
                            <th>Sort</th>
                            <th>Created</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody id="categories-list-${type}"></tbody>
                </table>
            </div>
        </div>
        <div class="card">
            <div class="table-top">
                <div>
                    <h3 style="margin:0;">Элементы (${label})</h3>
                    <p class="muted">CRUD для элементов типа ${type}.</p>
                </div>
                <div class="action-links">
                    <input type="search" id="items-search-${type}" class="search-input" placeholder="Поиск по названию">
                    <select id="items-filter-${type}"></select>
                    <button id="item-create-${type}" class="btn-primary" type="button">Создать</button>
                </div>
            </div>
            <div class="status" id="status-items-${type}"></div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Title</th>
                            <th>Category</th>
                            <th>Price</th>
                            <th>Active</th>
                            <th>Sort</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody id="items-list-${type}"></tbody>
                </table>
            </div>
        </div>
    `;
    return panel;
}

function setActiveTab(panelId, { pushHistory = true } = {}) {
    if (!panelId) return;
    const panel = document.getElementById(panelId);
    if (!panel) return;
    state.activeTab = panelId;
    document.querySelectorAll('.tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.target === panelId);
    });
    document.querySelectorAll('.panel').forEach((el) => {
        el.classList.toggle('active', el.id === panelId);
    });

    if (pushHistory) {
        const url = new URL(window.location.href);
        url.searchParams.set('tab', panelId);
        window.history.pushState(
            { ...(window.history.state || {}), adminsiteTab: panelId, adminsiteRoot: true },
            '',
            url.toString(),
        );
    }
}

function getInitialTab() {
    const url = new URL(window.location.href);
    const requested = url.searchParams.get('tab');
    if (requested && document.getElementById(requested)) {
        return requested;
    }
    if (state.types[0]) {
        return `panel-${state.types[0]}`;
    }
    if (document.getElementById('panel-homepage')) {
        return 'panel-homepage';
    }
    return document.getElementById('panel-webapp') ? 'panel-webapp' : null;
}

function renderTypeTabs() {
    const tabs = state.ui.tabsContainer;
    const panels = state.ui.panelsContainer;
    if (!tabs || !panels) return;

    tabs.innerHTML = '';
    panels.innerHTML = '';

    state.types.forEach((type) => {
        ensureTypeState(type);
        tabs.appendChild(createTypeTab(type));
        panels.appendChild(createTypePanel(type));
        bindTypeButtons(type);
    });

    const webappPanel = document.getElementById('panel-webapp');
    if (webappPanel) {
        webappPanel.classList.remove('active');
        panels.appendChild(webappPanel);
        const webappTab = document.createElement('button');
        webappTab.className = 'tab';
        webappTab.dataset.target = 'panel-webapp';
        webappTab.textContent = 'WebApp';
        webappTab.addEventListener('click', () => setActiveTab('panel-webapp'));
        tabs.appendChild(webappTab);
        state.ui.webappTab = webappTab;
    }

    const homepagePanel = document.getElementById('panel-homepage');
    if (homepagePanel) {
        homepagePanel.classList.remove('active');
        panels.appendChild(homepagePanel);
        const homepageTab = document.createElement('button');
        homepageTab.className = 'tab';
        homepageTab.dataset.target = 'panel-homepage';
        homepageTab.textContent = 'Главная';
        homepageTab.addEventListener('click', () => setActiveTab('panel-homepage'));
        tabs.appendChild(homepageTab);
    }

    const initialTab = getInitialTab();
    setActiveTab(initialTab, { pushHistory: false });
}

const categoryModals = {};
const itemModals = {};

function ensureCategoryModal(type) {
    if (!categoryModals[type]) {
        categoryModals[type] = new CategoryModal({
            title: `Категория (${humanizeType(type)})`,
            onSubmit: (payload) => upsertCategory(type, payload),
        });
        attachSlugHelpers(categoryModals[type]);
        registerModal(categoryModals[type]);
    }
    return categoryModals[type];
}

function ensureItemModal(type) {
    if (!itemModals[type]) {
        itemModals[type] = new ItemModal({
            title: humanizeType(type),
            categoriesProvider: (t) => categoryOptions(t),
            onSubmit: (payload) => upsertItem(type, payload),
        });
        attachSlugHelpers(itemModals[type]);
        registerModal(itemModals[type]);
    }
    return itemModals[type];
}

function openCategoryModal(type, category = null) {
    const modal = ensureCategoryModal(type);
    modal.setData(category);
    openTrackedModal(modal, `category-${type}-${category?.id || 'new'}`);
}

function openItemModal(type, item = null) {
    const modal = ensureItemModal(type);
    modal.setData(item, type);
    openTrackedModal(modal, `item-${type}-${item?.id || 'new'}`);
}

function bindTypeButtons(type) {
    ensureTypeState(type);
    bindElement(`category-create-${type}`, 'click', () => openCategoryModal(type));
    bindElement(`item-create-${type}`, 'click', () => openItemModal(type));
    bindElement(`items-filter-${type}`, 'change', (event) => {
        state.filters[type].categoryId = event.target.value;
        loadItems(type);
    });
    bindElement(`items-search-${type}`, 'input', (event) => {
        state.filters[type].search = event.target.value;
        renderItemsTable(type);
    });
}

function renderWebappTypeOptions() {
    const select = getElementOrWarn('webapp-type');
    if (!select) return;
    const types = state.types.length ? state.types : DEFAULT_TYPES;
    const current = select.value;
    select.innerHTML = '';
    types.forEach((type) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = `${type} — витрина`;
        select.appendChild(option);
    });
    if (current && types.includes(current)) {
        select.value = current;
    }
}

function setupWebappListeners() {
    const webappType = bindElement('webapp-type', 'change', async () => {
        renderCategorySelects(webappType?.value);
        toggleWebappCategory();
        await loadWebappSettings();
    });
    bindElement('webapp-scope', 'change', async () => {
        toggleWebappCategory();
        await loadWebappSettings();
    });
    bindElement('webapp-category', 'change', loadWebappSettings);
    bindElement('webapp-form', 'submit', saveWebappSettings);
    bindElement('webapp-reload', 'click', (e) => {
        e.preventDefault();
        loadWebappSettings();
    });
}

const homepageTemplateSelect = getElementOrWarn('homepage-template');
const homepageBlocksField = getElementOrWarn('homepage-blocks');
const homepageSaveButton = getElementOrWarn('homepage-save');
const homepageResetButton = getElementOrWarn('homepage-reset');
const homepageStatus = getElementOrWarn('status-homepage');

function setHomepageStatus(message, isError = false) {
    if (!homepageStatus) return;
    if (!message) {
        homepageStatus.textContent = '';
        homepageStatus.classList.remove('error');
        homepageStatus.style.display = 'none';
        return;
    }
    homepageStatus.textContent = message;
    homepageStatus.classList.toggle('error', isError);
    homepageStatus.style.display = 'block';
}

function renderHomepageForm(data = homepageDefaults) {
    const payload = { ...homepageDefaults, ...(data || {}) };
    homepageConfig = payload;
    if (homepageTemplateSelect) {
        homepageTemplateSelect.value = payload.templateId || 'services';
    }
    if (homepageBlocksField) {
        const blocksValue = Array.isArray(payload.blocks) ? payload.blocks : [];
        homepageBlocksField.value = JSON.stringify(blocksValue, null, 2);
    }
}

function resetHomepageForm() {
    renderHomepageForm(homepageConfig);
    setHomepageStatus('');
}

async function loadHomepageConfig() {
    try {
        setHomepageStatus('Загрузка страницы...');
        const data = await apiRequest(`${API_BASE}/pages/home`, { credentials: 'include' });
        homepageConfig = data || homepageDefaults;
        renderHomepageForm(homepageConfig);
        setHomepageStatus('Страница загружена');
    } catch (error) {
        setHomepageStatus(error.message || 'Не удалось загрузить страницу', true);
    }
}

async function saveHomepageConfig() {
    if (!homepageBlocksField) return;
    try {
        const raw = homepageBlocksField.value || '[]';
        const blocks = JSON.parse(raw);
        const payload = {
            templateId: homepageTemplateSelect?.value || 'services',
            blocks,
        };
        setHomepageStatus('Сохранение...');
        const data = await apiRequest(`${API_BASE}/pages/home`, {
            method: 'PUT',
            body: payload,
            credentials: 'include',
        });
        homepageConfig = data || payload;
        renderHomepageForm(homepageConfig);
        setHomepageStatus('Сохранено');
        showToast('Страница обновлена');
    } catch (error) {
        console.error(error);
        setHomepageStatus(error.message || 'Не удалось сохранить страницу', true);
    }
}

function setupHomepageListeners() {
    homepageSaveButton?.addEventListener('click', saveHomepageConfig);
    homepageResetButton?.addEventListener('click', resetHomepageForm);
}

async function loadTypesFromApi() {
    setStatus('global-status', 'Загрузка разделов...');
    try {
        const types = await callApi('/types');
        const normalized = Array.isArray(types) && types.length ? types : DEFAULT_TYPES;
        normalized.forEach((type) => ensureTypeState(type));
    } catch (error) {
        DEFAULT_TYPES.forEach((type) => ensureTypeState(type));
        setStatus('global-status', error.message || 'Не удалось загрузить типы', true);
        showToast(error.message || 'Не удалось загрузить список разделов', 'error');
    }
}

async function bootstrap() {
    state.ui.tabsContainer = getElementOrWarn('constructor-tabs');
    state.ui.panelsContainer = getElementOrWarn('constructor-panels');
    setupWebappListeners();
    setupHomepageListeners();
    toggleWebappCategory();
    try {
        await loadTypesFromApi();
        renderWebappTypeOptions();
        renderTypeTabs();
        for (const type of state.types) {
            await loadCategories(type);
            await loadItems(type);
        }
        await loadWebappSettings();
        await loadHomepageConfig();
        setStatus('global-status', 'Данные загружены');
    } catch (error) {
        setStatus('global-status', error.message, true);
        showToast(error.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', bootstrap);
