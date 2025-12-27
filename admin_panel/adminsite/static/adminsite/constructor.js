import { apiRequest } from './apiClient.js';
import { BaseModal, CategoryModal, ItemModal } from './modals.js';

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

function buildDefaultBlocks() {
    return [
        {
            type: 'hero',
            title: 'Витрина AdminSite',
            subtitle: 'Настройте оформление и блоки под свои задачи.',
            imageUrl: '/static/img/home-placeholder.svg',
            background: {
                type: 'gradient',
                value: 'linear-gradient(135deg, rgba(255,255,255,0.12), rgba(0,0,0,0.04))',
            },
        },
        {
            type: 'cards',
            title: 'Подборка',
            subtitle: 'Карточки можно использовать для товаров, услуг или ссылок.',
            layout: { columns: 2 },
            items: [],
        },
        {
            type: 'text',
            title: 'Описание',
            text: 'Добавьте короткое описание компании или продукта.',
        },
        { type: 'social', items: [] },
    ];
}

const homepageDefaults = {
    templateId: 'services',
    blocks: buildDefaultBlocks(),
};

let homepageConfig = homepageDefaults;
let homepageSelectedIndex = 0;
let developerMode = false;

function copyToClipboard(value, fallbackMessage = 'Скопировано') {
    if (!value) return;
    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(value).then(
            () => showToast(fallbackMessage),
            () => {
                showToast('Не удалось скопировать', 'error');
            },
        );
        return;
    }

    const input = document.createElement('input');
    input.value = value;
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    document.body.removeChild(input);
    showToast(fallbackMessage);
}

function normalizeBackground(background = {}) {
    const type = ['color', 'gradient', 'image'].includes(background?.type) ? background.type : 'color';
    return {
        type,
        value: background?.value || null,
    };
}

function normalizeLayout(layout = {}) {
    const columns = Number(layout?.columns) || 2;
    const safeColumns = Math.min(3, Math.max(1, columns));
    return { columns: safeColumns };
}

function normalizeCardItem(item = {}) {
    return {
        title: item?.title || 'Карточка',
        imageUrl: item?.imageUrl || item?.image_url || null,
        href: item?.href || '',
        icon: item?.icon || null,
    };
}

function normalizeSocialItem(item = {}) {
    const allowed = ['telegram', 'whatsapp', 'vk', 'instagram', 'website', 'phone', 'email'];
    const type = allowed.includes(item?.type) ? item.type : 'telegram';
    return {
        type,
        label: item?.label || 'Связаться',
        href: item?.href || '',
        icon: item?.icon || null,
    };
}

function normalizeBlock(block = {}) {
    if (!block?.type) return null;
    if (block.type === 'hero') {
        return {
            type: 'hero',
            title: block.title || 'Витрина AdminSite',
            subtitle: block.subtitle || '',
            imageUrl: block.imageUrl || block.image_url || '',
            background: normalizeBackground(block.background),
        };
    }
    if (block.type === 'cards') {
        const items = Array.isArray(block.items) ? block.items.map(normalizeCardItem) : [];
        return {
            type: 'cards',
            title: block.title || '',
            subtitle: block.subtitle || '',
            items,
            layout: normalizeLayout(block.layout),
        };
    }
    if (block.type === 'text') {
        return {
            type: 'text',
            title: block.title || '',
            text: block.text || '',
        };
    }
    if (block.type === 'social') {
        const items = Array.isArray(block.items) ? block.items.map(normalizeSocialItem) : [];
        return {
            type: 'social',
            items,
        };
    }
    return null;
}

function normalizeHomepageConfig(data = homepageDefaults) {
    const templateId = data?.templateId || data?.template_id || 'services';
    const blocksRaw = Array.isArray(data?.blocks) ? data.blocks : [];
    const normalizedBlocks = blocksRaw.map(normalizeBlock).filter(Boolean);
    const safeBlocks = normalizedBlocks.length ? normalizedBlocks : buildDefaultBlocks();
    return { templateId, blocks: safeBlocks };
}

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
    if (document.getElementById('panel-media')) {
        return 'panel-media';
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

    const mediaPanel = document.getElementById('panel-media');
    if (mediaPanel) {
        mediaPanel.classList.remove('active');
        panels.appendChild(mediaPanel);
        const mediaTab = document.createElement('button');
        mediaTab.className = 'tab';
        mediaTab.dataset.target = 'panel-media';
        mediaTab.textContent = 'Медиа';
        mediaTab.addEventListener('click', () => setActiveTab('panel-media'));
        tabs.appendChild(mediaTab);
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

const homepageTemplateCards = Array.from(document.querySelectorAll('#homepage-template .template-card'));
const homepageBlocksField = getElementOrWarn('homepage-blocks');
const homepageSaveButton = getElementOrWarn('homepage-save');
const homepageResetButton = getElementOrWarn('homepage-reset');
const homepageStatus = getElementOrWarn('status-homepage');
const homepageBlocksList = getElementOrWarn('homepage-blocks-list');
const homepageBlockEditor = getElementOrWarn('homepage-block-editor');
const homepageEditorTitle = getElementOrWarn('homepage-editor-title');
const homepageEditorSubtitle = getElementOrWarn('homepage-editor-subtitle');
const homepageBlockMeta = getElementOrWarn('homepage-block-meta');
const homepageDevToggle = getElementOrWarn('homepage-dev-toggle');
const homepageDevTools = getElementOrWarn('homepage-devtools');
const homepageDevStatus = getElementOrWarn('homepage-dev-status');
const homepageDevApply = getElementOrWarn('homepage-dev-apply');
const homepageDevHide = getElementOrWarn('homepage-dev-hide');
const homepageAddBlockButton = getElementOrWarn('homepage-add-block');

let homepageLoadedConfig = normalizeHomepageConfig(homepageDefaults);
let blockPickerModal = null;

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

function setDevStatus(message, isError = false) {
    if (!homepageDevStatus) return;
    homepageDevStatus.textContent = message || '';
    homepageDevStatus.classList.toggle('error', Boolean(message && isError));
    homepageDevStatus.style.display = message ? 'block' : 'none';
}

function syncDevTextarea() {
    if (homepageBlocksField) {
        homepageBlocksField.value = JSON.stringify(homepageConfig.blocks || [], null, 2);
    }
}

function setTemplateActive(templateId) {
    homepageTemplateCards.forEach((card) => {
        card.classList.toggle('active', card.dataset.template === templateId);
    });
}

function setTemplate(templateId) {
    homepageConfig = { ...homepageConfig, templateId: templateId || 'services' };
    setTemplateActive(homepageConfig.templateId);
}

function createBlockOfType(type) {
    if (type === 'cards') {
        return normalizeBlock({ type: 'cards', title: 'Подборка', subtitle: '', items: [], layout: { columns: 2 } });
    }
    if (type === 'text') {
        return normalizeBlock({ type: 'text', title: 'Текстовый блок', text: '' });
    }
    if (type === 'social') {
        return normalizeBlock({ type: 'social', items: [] });
    }
    return normalizeBlock({
        type: 'hero',
        title: 'Витрина AdminSite',
        subtitle: 'Добавьте описание и картинку',
        imageUrl: '/static/img/home-placeholder.svg',
        background: { type: 'gradient', value: 'linear-gradient(135deg, rgba(255,255,255,0.12), rgba(0,0,0,0.04))' },
    });
}

function ensureBlocksPresent() {
    if (!Array.isArray(homepageConfig.blocks) || !homepageConfig.blocks.length) {
        homepageConfig.blocks = buildDefaultBlocks();
        homepageSelectedIndex = 0;
    }
}

function selectBlock(index = 0) {
    ensureBlocksPresent();
    const safeIndex = Math.min(Math.max(0, index), homepageConfig.blocks.length - 1);
    homepageSelectedIndex = safeIndex;
    renderBlocksList();
    renderBlockEditor();
}

function moveBlock(index, delta) {
    const targetIndex = index + delta;
    if (targetIndex < 0 || targetIndex >= homepageConfig.blocks.length) return;
    const [item] = homepageConfig.blocks.splice(index, 1);
    homepageConfig.blocks.splice(targetIndex, 0, item);
    selectBlock(targetIndex);
    syncDevTextarea();
}

function deleteBlock(index) {
    if (!homepageConfig.blocks[index]) return;
    homepageConfig.blocks.splice(index, 1);
    if (!homepageConfig.blocks.length) {
        homepageConfig.blocks = buildDefaultBlocks();
    }
    selectBlock(Math.max(0, index - 1));
    syncDevTextarea();
}

function addBlock(type) {
    const block = createBlockOfType(type);
    if (!block) return;
    homepageConfig.blocks.push(block);
    selectBlock(homepageConfig.blocks.length - 1);
    syncDevTextarea();
    showToast('Блок добавлен');
}

function ensureBlockPicker() {
    if (blockPickerModal) return blockPickerModal;
    blockPickerModal = new BaseModal('Добавить блок');
    const wrapper = document.createElement('div');
    wrapper.className = 'block-list';
    [
        { type: 'hero', title: 'Hero', text: 'Крупный блок с заголовком и картинкой' },
        { type: 'cards', title: 'Карточки', text: 'Сетка карточек с картинками' },
        { type: 'text', title: 'Текст', text: 'Абзац текста и заголовок' },
        { type: 'social', title: 'Социальные ссылки', text: 'Ссылки и контакты' },
    ].forEach((item) => {
        const row = document.createElement('div');
        row.className = 'block-row';
        const info = document.createElement('div');
        const title = document.createElement('div');
        title.textContent = item.title;
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = item.text;
        info.append(title, meta);
        const btn = document.createElement('button');
        btn.className = 'btn-primary';
        btn.type = 'button';
        btn.textContent = 'Добавить';
        btn.addEventListener('click', () => {
            addBlock(item.type);
            closeTrackedModal(blockPickerModal, 'block-added');
        });
        row.append(info, btn);
        wrapper.appendChild(row);
    });
    blockPickerModal.modal.appendChild(wrapper);
    registerModal(blockPickerModal);
    return blockPickerModal;
}

function openBlockPicker() {
    const modal = ensureBlockPicker();
    openTrackedModal(modal, 'block-picker');
}

function renderBlocksList() {
    if (!homepageBlocksList) return;
    homepageBlocksList.innerHTML = '';
    ensureBlocksPresent();

    homepageConfig.blocks.forEach((block, index) => {
        const row = document.createElement('div');
        row.className = 'block-row';
        if (index === homepageSelectedIndex) {
            row.classList.add('active');
        }
        row.addEventListener('click', () => selectBlock(index));

        const info = document.createElement('div');
        const title = document.createElement('div');
        title.textContent = block.title || block.type;
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = block.type;
        info.append(title, meta);

        const actions = document.createElement('div');
        actions.className = 'actions';

        const up = document.createElement('button');
        up.className = 'btn-ghost';
        up.type = 'button';
        up.textContent = '↑';
        up.title = 'Вверх';
        up.addEventListener('click', (event) => {
            event.stopPropagation();
            moveBlock(index, -1);
        });

        const down = document.createElement('button');
        down.className = 'btn-ghost';
        down.type = 'button';
        down.textContent = '↓';
        down.title = 'Вниз';
        down.addEventListener('click', (event) => {
            event.stopPropagation();
            moveBlock(index, 1);
        });

        const remove = document.createElement('button');
        remove.className = 'btn-danger';
        remove.type = 'button';
        remove.textContent = 'Удалить';
        remove.addEventListener('click', (event) => {
            event.stopPropagation();
            deleteBlock(index);
        });

        actions.append(up, down, remove);
        row.append(info, actions);
        homepageBlocksList.appendChild(row);
    });
}

function createInput(labelText, value, onChange, { type = 'text', placeholder = '', textarea = false } = {}) {
    const label = document.createElement('label');
    label.textContent = labelText;
    const input = textarea ? document.createElement('textarea') : document.createElement('input');
    if (!textarea) {
        input.type = type;
    }
    input.placeholder = placeholder;
    if (value !== undefined && value !== null) input.value = value;
    input.addEventListener('input', (event) => {
        onChange(event.target.value);
    });
    label.appendChild(input);
    return { label, input };
}

function renderHeroEditor(block, index) {
    const container = document.createElement('div');
    const titleField = createInput('Заголовок', block.title, (val) => updateBlock(index, { ...block, title: val || 'Hero' }));
    const subtitleField = createInput('Подзаголовок', block.subtitle || '', (val) => updateBlock(index, { ...block, subtitle: val }));
    const imageField = createInput('Картинка (URL)', block.imageUrl || '', (val) => updateBlock(index, { ...block, imageUrl: val }));
    const imageActions = document.createElement('div');
    imageActions.className = 'inline-actions';
    const pickBtn = document.createElement('button');
    pickBtn.className = 'btn-secondary';
    pickBtn.type = 'button';
    pickBtn.textContent = 'Выбрать из медиа';
    pickBtn.addEventListener('click', async (event) => {
        event.preventDefault();
        await openMediaPicker((url) => {
            imageField.input.value = url;
            updateBlock(index, { ...block, imageUrl: url });
        });
    });
    imageActions.appendChild(pickBtn);

    const bgTypeWrapper = document.createElement('div');
    bgTypeWrapper.className = 'field-row';
    const bgTypeLabel = document.createElement('label');
    bgTypeLabel.textContent = 'Фон';
    const bgTypeSelect = document.createElement('select');
    ['gradient', 'color', 'image'].forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option;
        bgTypeSelect.appendChild(opt);
    });
    bgTypeSelect.value = block.background?.type || 'gradient';

    const bgValueField = createInput('Значение фона', block.background?.value || '', (val) => {
        updateBlock(index, { ...block, background: { type: bgTypeSelect.value, value: val } });
    });

    bgTypeSelect.addEventListener('change', (event) => {
        const nextType = event.target.value;
        updateBlock(index, { ...block, background: { type: nextType, value: bgValueField.input.value } });
    });
    bgTypeLabel.appendChild(bgTypeSelect);
    bgTypeWrapper.append(bgTypeLabel, bgValueField.label);

    container.append(titleField.label, subtitleField.label, imageField.label, imageActions, bgTypeWrapper);
    return container;
}

function renderCardItems(block, index) {
    const wrapper = document.createElement('div');
    wrapper.className = 'block-list';

    const addBtn = document.createElement('button');
    addBtn.className = 'btn-secondary';
    addBtn.type = 'button';
    addBtn.textContent = '+ Добавить карточку';
    addBtn.addEventListener('click', () => {
        const nextItems = [...(block.items || []), normalizeCardItem({ title: 'Карточка', href: '' })];
        updateBlock(index, { ...block, items: nextItems });
    });

    (block.items || []).forEach((item, itemIndex) => {
        const row = document.createElement('div');
        row.className = 'list-item';

        const body = document.createElement('div');
        const titleField = createInput('Заголовок', item.title, (val) => {
            const next = [...block.items];
            next[itemIndex] = { ...item, title: val };
            updateBlock(index, { ...block, items: next });
        });
        const hrefField = createInput('Ссылка', item.href || '', (val) => {
            const next = [...block.items];
            next[itemIndex] = { ...item, href: val };
            updateBlock(index, { ...block, items: next });
        });
        const imageField = createInput('Картинка', item.imageUrl || '', (val) => {
            const next = [...block.items];
            next[itemIndex] = { ...item, imageUrl: val };
            updateBlock(index, { ...block, items: next });
        });
        const mediaBtn = document.createElement('button');
        mediaBtn.className = 'btn-secondary';
        mediaBtn.type = 'button';
        mediaBtn.textContent = 'Медиа';
        mediaBtn.addEventListener('click', async () => {
            await openMediaPicker((url) => {
                imageField.input.value = url;
                const next = [...block.items];
                next[itemIndex] = { ...item, imageUrl: url };
                updateBlock(index, { ...block, items: next });
            });
        });

        body.append(titleField.label, hrefField.label, imageField.label, mediaBtn);

        const actions = document.createElement('div');
        actions.className = 'actions';
        const up = document.createElement('button');
        up.className = 'btn-ghost';
        up.type = 'button';
        up.textContent = '↑';
        up.addEventListener('click', () => {
            if (itemIndex === 0) return;
            const next = [...block.items];
            next.splice(itemIndex, 1);
            next.splice(itemIndex - 1, 0, item);
            updateBlock(index, { ...block, items: next });
        });
        const down = document.createElement('button');
        down.className = 'btn-ghost';
        down.type = 'button';
        down.textContent = '↓';
        down.addEventListener('click', () => {
            const next = [...block.items];
            if (itemIndex >= next.length - 1) return;
            next.splice(itemIndex, 1);
            next.splice(itemIndex + 1, 0, item);
            updateBlock(index, { ...block, items: next });
        });
        const remove = document.createElement('button');
        remove.className = 'btn-danger';
        remove.type = 'button';
        remove.textContent = 'Удалить';
        remove.addEventListener('click', () => {
            const next = [...block.items];
            next.splice(itemIndex, 1);
            updateBlock(index, { ...block, items: next });
        });
        actions.append(up, down, remove);

        row.append(body, actions);
        wrapper.appendChild(row);
    });

    wrapper.appendChild(addBtn);
    return wrapper;
}

function renderSocialItems(block, index) {
    const wrapper = document.createElement('div');
    wrapper.className = 'block-list';

    const addBtn = document.createElement('button');
    addBtn.className = 'btn-secondary';
    addBtn.type = 'button';
    addBtn.textContent = '+ Добавить ссылку';
    addBtn.addEventListener('click', () => {
        const nextItems = [...(block.items || []), normalizeSocialItem({ href: '' })];
        updateBlock(index, { ...block, items: nextItems });
    });

    (block.items || []).forEach((item, itemIndex) => {
        const row = document.createElement('div');
        row.className = 'list-item';
        const body = document.createElement('div');

        const typeLabel = document.createElement('label');
        typeLabel.textContent = 'Тип';
        const typeSelect = document.createElement('select');
        ['telegram', 'whatsapp', 'vk', 'instagram', 'website', 'phone', 'email'].forEach((value) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = value;
            typeSelect.appendChild(opt);
        });
        typeSelect.value = item.type;
        typeSelect.addEventListener('change', (event) => {
            const next = [...block.items];
            next[itemIndex] = { ...item, type: event.target.value };
            updateBlock(index, { ...block, items: next });
        });
        typeLabel.appendChild(typeSelect);

        const labelField = createInput('Текст', item.label || '', (val) => {
            const next = [...block.items];
            next[itemIndex] = { ...item, label: val };
            updateBlock(index, { ...block, items: next });
        });
        const hrefField = createInput('Ссылка', item.href || '', (val) => {
            const next = [...block.items];
            next[itemIndex] = { ...item, href: val };
            updateBlock(index, { ...block, items: next });
        });

        body.append(typeLabel, labelField.label, hrefField.label);

        const actions = document.createElement('div');
        actions.className = 'actions';
        const remove = document.createElement('button');
        remove.className = 'btn-danger';
        remove.type = 'button';
        remove.textContent = 'Удалить';
        remove.addEventListener('click', () => {
            const next = [...block.items];
            next.splice(itemIndex, 1);
            updateBlock(index, { ...block, items: next });
        });
        actions.appendChild(remove);

        row.append(body, actions);
        wrapper.appendChild(row);
    });

    wrapper.appendChild(addBtn);
    return wrapper;
}

function updateBlock(index, nextValue) {
    const current = homepageConfig.blocks[index];
    if (!current) return;
    const updated = normalizeBlock(typeof nextValue === 'function' ? nextValue(current) : nextValue) || current;
    homepageConfig.blocks[index] = updated;
    renderBlocksList();
    renderBlockEditor();
    syncDevTextarea();
}

function renderBlockEditor() {
    if (!homepageBlockEditor) return;
    ensureBlocksPresent();
    const block = homepageConfig.blocks[homepageSelectedIndex];
    homepageBlockEditor.innerHTML = '';

    if (!block) {
        homepageBlockEditor.innerHTML = '<p class="muted">Добавьте блок, чтобы начать редактирование.</p>';
        return;
    }

    homepageEditorTitle.textContent = block.title || 'Блок';
    homepageEditorSubtitle.textContent = block.type === 'hero' ? 'Крупный блок с картинкой' : block.type;
    if (homepageBlockMeta) {
        homepageBlockMeta.innerHTML = '';
        const pill = document.createElement('span');
        pill.className = 'pill';
        pill.textContent = block.type;
        homepageBlockMeta.appendChild(pill);
    }

    let editorContent = document.createElement('div');
    if (block.type === 'hero') {
        editorContent = renderHeroEditor(block, homepageSelectedIndex);
    } else if (block.type === 'cards') {
        const header = new DocumentFragment();
        const titleField = createInput('Заголовок', block.title || '', (val) => updateBlock(homepageSelectedIndex, { ...block, title: val }));
        const subtitleField = createInput('Подзаголовок', block.subtitle || '', (val) => updateBlock(homepageSelectedIndex, { ...block, subtitle: val }));

        const columnsLabel = document.createElement('label');
        columnsLabel.textContent = 'Колонки';
        const columns = document.createElement('select');
        [1, 2, 3].forEach((col) => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = `${col}`;
            columns.appendChild(opt);
        });
        columns.value = block.layout?.columns || 2;
        columns.addEventListener('change', (event) => {
            const nextColumns = Number(event.target.value) || 2;
            updateBlock(homepageSelectedIndex, { ...block, layout: { columns: nextColumns } });
        });
        columnsLabel.appendChild(columns);

        editorContent.append(titleField.label, subtitleField.label, columnsLabel, renderCardItems(block, homepageSelectedIndex));
    } else if (block.type === 'text') {
        const titleField = createInput('Заголовок', block.title || '', (val) => updateBlock(homepageSelectedIndex, { ...block, title: val }));
        const textField = createInput('Текст', block.text || '', (val) => updateBlock(homepageSelectedIndex, { ...block, text: val }), { textarea: true });
        editorContent.append(titleField.label, textField.label);
    } else if (block.type === 'social') {
        editorContent.appendChild(renderSocialItems(block, homepageSelectedIndex));
    }

    homepageBlockEditor.appendChild(editorContent);
}

function toggleDeveloperMode(enabled) {
    developerMode = enabled;
    if (homepageDevToggle) homepageDevToggle.checked = enabled;
    if (homepageDevTools) homepageDevTools.hidden = !enabled;
    if (enabled) {
        syncDevTextarea();
    } else {
        setDevStatus('');
    }
}

function applyDevJson({ silent = false } = {}) {
    if (!homepageBlocksField) return true;
    try {
        const raw = homepageBlocksField.value || '[]';
        const parsed = JSON.parse(raw);
        const normalized = Array.isArray(parsed) ? parsed.map(normalizeBlock).filter(Boolean) : [];
        if (!normalized.length) {
            throw new Error('JSON не содержит валидных блоков');
        }
        homepageConfig.blocks = normalized;
        homepageSelectedIndex = 0;
        renderBlocksList();
        renderBlockEditor();
        setDevStatus('JSON применён');
        return true;
    } catch (error) {
        setDevStatus(error.message || 'Ошибка JSON', true);
        if (!silent) setHomepageStatus('Исправьте JSON', true);
        return false;
    }
}

function renderHomepageForm(data = homepageDefaults) {
    const payload = normalizeHomepageConfig(data);
    homepageConfig = JSON.parse(JSON.stringify(payload));
    homepageSelectedIndex = 0;
    setTemplateActive(homepageConfig.templateId);
    syncDevTextarea();
    toggleDeveloperMode(false);
    renderBlocksList();
    renderBlockEditor();
}

function resetHomepageForm() {
    renderHomepageForm(homepageLoadedConfig);
    setHomepageStatus('');
    setDevStatus('');
}

async function loadHomepageConfig() {
    try {
        setHomepageStatus('Загрузка страницы...');
        const data = await apiRequest(`${API_BASE}/pages/home`, { credentials: 'include' });
        homepageLoadedConfig = normalizeHomepageConfig(data || homepageDefaults);
        renderHomepageForm(homepageLoadedConfig);
        setHomepageStatus('Страница загружена');
    } catch (error) {
        setHomepageStatus(error.message || 'Не удалось загрузить страницу', true);
    }
}

async function saveHomepageConfig() {
    if (developerMode && !applyDevJson({ silent: true })) {
        return;
    }
    try {
        setHomepageStatus('Сохранение...');
        const payload = {
            templateId: homepageConfig.templateId || 'services',
            blocks: homepageConfig.blocks || [],
        };
        console.debug('[AdminSite constructor] Отправка страницы', payload);
        const data = await apiRequest(`${API_BASE}/pages/home`, {
            method: 'PUT',
            body: payload,
            credentials: 'include',
        });
        if (!data || typeof data !== 'object') {
            throw new Error('API вернул пустой ответ, страница не сохранена');
        }

        homepageLoadedConfig = normalizeHomepageConfig(data || payload);
        renderHomepageForm(homepageLoadedConfig);
        setHomepageStatus('Сохранено');
        showToast('Страница обновлена');
        console.debug('[AdminSite constructor] Страница сохранена', homepageLoadedConfig);
    } catch (error) {
        console.error('[AdminSite constructor] Сохранение страницы не удалось', error);
        setHomepageStatus(error.message || 'Не удалось сохранить страницу', true);
        showToast(error.message || 'Не удалось сохранить страницу', 'error');
    }
}

function setupHomepageListeners() {
    homepageSaveButton?.addEventListener('click', saveHomepageConfig);
    homepageResetButton?.addEventListener('click', resetHomepageForm);
    homepageAddBlockButton?.addEventListener('click', openBlockPicker);
    homepageTemplateCards.forEach((card) => {
        card.addEventListener('click', () => setTemplate(card.dataset.template));
    });
    homepageDevToggle?.addEventListener('change', (event) => toggleDeveloperMode(event.target.checked));
    homepageDevHide?.addEventListener('click', () => toggleDeveloperMode(false));
    homepageDevApply?.addEventListener('click', () => applyDevJson());
}

const mediaStatus = getElementOrWarn('status-media');
const mediaUploadStatus = getElementOrWarn('media-upload-status');
const mediaUploadInput = getElementOrWarn('media-upload-input');
const mediaUploadButton = getElementOrWarn('media-upload-btn');
const mediaRefreshButton = getElementOrWarn('media-refresh');
const mediaList = getElementOrWarn('media-list');
const mediaSearch = getElementOrWarn('media-search');

const mediaState = {
    items: [],
    filter: '',
};

let mediaPickerModal = null;

function setMediaStatus(message, isError = false) {
    if (!mediaStatus) return;
    mediaStatus.textContent = message || '';
    mediaStatus.classList.toggle('error', Boolean(message && isError));
    mediaStatus.style.display = message ? 'block' : 'none';
}

function setMediaUploadStatus(message, isError = false) {
    if (!mediaUploadStatus) return;
    mediaUploadStatus.textContent = message || '';
    mediaUploadStatus.classList.toggle('error', Boolean(message && isError));
    mediaUploadStatus.style.display = message ? 'block' : 'none';
}

function formatFileSize(bytes = 0) {
    if (!bytes) return '0 Б';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} КБ`;
    return `${(kb / 1024).toFixed(1)} МБ`;
}

function buildMediaCard(item, { selectable = false, onSelect } = {}) {
    const card = document.createElement('div');
    card.className = 'media-card';

    const preview = document.createElement('div');
    const img = document.createElement('img');
    img.src = item.url;
    img.alt = item.name;
    preview.appendChild(img);

    const body = document.createElement('div');
    const title = document.createElement('h4');
    title.style.margin = '0 0 6px';
    title.textContent = item.name;
    const meta = document.createElement('div');
    meta.className = 'muted';
    const updated = item.modified ? new Date(item.modified * 1000).toLocaleString('ru-RU') : '';
    meta.textContent = `${formatFileSize(item.size)}${updated ? ` · ${updated}` : ''}`;

    const urlInput = document.createElement('input');
    urlInput.value = item.url;
    urlInput.readOnly = true;
    urlInput.addEventListener('focus', (event) => event.target.select());

    const actions = document.createElement('div');
    actions.className = 'actions';
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn-secondary';
    copyBtn.type = 'button';
    copyBtn.textContent = 'Копировать';
    copyBtn.addEventListener('click', () => copyToClipboard(item.url));
    actions.appendChild(copyBtn);

    if (selectable && typeof onSelect === 'function') {
        const selectBtn = document.createElement('button');
        selectBtn.className = 'btn-primary';
        selectBtn.type = 'button';
        selectBtn.textContent = 'Выбрать';
        selectBtn.addEventListener('click', () => {
            onSelect(item.url);
            closeTrackedModal(mediaPickerModal, 'media-select');
        });
        actions.appendChild(selectBtn);
    }

    if (!selectable) {
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-danger';
        deleteBtn.type = 'button';
        deleteBtn.textContent = 'Удалить';
        deleteBtn.addEventListener('click', async () => {
            if (!confirm('Удалить файл?')) return;
            await deleteMediaFile(item.name);
        });
        actions.appendChild(deleteBtn);
    }

    body.append(title, meta, urlInput, actions);
    card.append(preview, body);
    return card;
}

function renderMediaList() {
    if (!mediaList) return;
    mediaList.innerHTML = '';
    const filtered = mediaState.items.filter((item) =>
        !mediaState.filter || item.name.toLowerCase().includes(mediaState.filter.toLowerCase()),
    );
    if (!filtered.length) {
        const empty = document.createElement('div');
        empty.className = 'muted';
        empty.textContent = 'Файлы ещё не загружены.';
        mediaList.appendChild(empty);
        return;
    }
    filtered.forEach((item) => mediaList.appendChild(buildMediaCard(item)));
}

function ensureMediaPickerModal() {
    if (mediaPickerModal) return mediaPickerModal;
    mediaPickerModal = new BaseModal('Выбрать из медиа');
    mediaPickerModal.listContainer = document.createElement('div');
    mediaPickerModal.listContainer.className = 'media-list';
    mediaPickerModal.modal.appendChild(mediaPickerModal.listContainer);
    mediaPickerModal.onClose(() => {
        if (mediaPickerModal?.listContainer) mediaPickerModal.listContainer.innerHTML = '';
    });
    registerModal(mediaPickerModal);
    return mediaPickerModal;
}

async function openMediaPicker(onSelect) {
    const modal = ensureMediaPickerModal();
    await loadMediaLibrary({ silent: true });
    if (modal.listContainer) {
        modal.listContainer.innerHTML = '';
        mediaState.items.forEach((item) => {
            modal.listContainer.appendChild(buildMediaCard(item, { selectable: true, onSelect }));
        });
    }
    openTrackedModal(modal, 'media-picker');
}

async function loadMediaLibrary({ silent = false } = {}) {
    try {
        if (!silent) setMediaStatus('Загрузка медиа...');
        const query = mediaState.filter ? `?q=${encodeURIComponent(mediaState.filter)}` : '';
        const items = await apiRequest(`${API_BASE}/media${query}`, { credentials: 'include' });
        mediaState.items = Array.isArray(items) ? items : [];
        renderMediaList();
        if (!silent) setMediaStatus('Готово');
    } catch (error) {
        setMediaStatus(error.message || 'Не удалось загрузить медиа', true);
    }
}

async function uploadMediaFile() {
    const file = mediaUploadInput?.files?.[0];
    if (!file) {
        setMediaUploadStatus('Выберите файл', true);
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    try {
        setMediaUploadStatus('Загружаем...');
        const result = await apiRequest(`${API_BASE}/media/upload`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        });
        setMediaUploadStatus('Готово');
        showToast('Файл загружен');
        copyToClipboard(result?.url);
        if (mediaUploadInput) mediaUploadInput.value = '';
        await loadMediaLibrary();
    } catch (error) {
        setMediaUploadStatus(error.message || 'Не удалось загрузить файл', true);
    }
}

async function deleteMediaFile(filename) {
    try {
        setMediaStatus('Удаляем...');
        await apiRequest(`${API_BASE}/media/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
            credentials: 'include',
        });
        await loadMediaLibrary({ silent: true });
        setMediaStatus('Файл удалён');
    } catch (error) {
        setMediaStatus(error.message || 'Не удалось удалить', true);
    }
}

function setupMediaListeners() {
    mediaUploadButton?.addEventListener('click', uploadMediaFile);
    mediaRefreshButton?.addEventListener('click', () => loadMediaLibrary());
    mediaSearch?.addEventListener('input', (event) => {
        mediaState.filter = event.target.value || '';
        renderMediaList();
    });
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
    setupMediaListeners();
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
        await loadMediaLibrary({ silent: true });
        setStatus('global-status', 'Данные загружены');
    } catch (error) {
        setStatus('global-status', error.message, true);
        showToast(error.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', bootstrap);
