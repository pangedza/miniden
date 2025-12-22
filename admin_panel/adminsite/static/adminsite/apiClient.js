const defaultHeaders = { 'Content-Type': 'application/json' };

function parseErrorDetail(detail) {
    if (!detail) return 'Ошибка запроса';
    if (typeof detail === 'string') return detail;
    if (detail.detail) return parseErrorDetail(detail.detail);
    return JSON.stringify(detail);
}

export async function apiRequest(url, options = {}) {
    const opts = { credentials: 'same-origin', ...options };
    if (opts.body && !(opts.body instanceof FormData)) {
        opts.headers = { ...defaultHeaders, ...(opts.headers || {}) };
        opts.body = JSON.stringify(opts.body);
    }

    const response = await fetch(url, opts);
    let payload = null;
    try {
        if (response.status !== 204) {
            payload = await response.json();
        }
    } catch (_) {
        /* ignore parse errors */
    }

    if (!response.ok) {
        const message = payload ? parseErrorDetail(payload) : `HTTP ${response.status}`;
        throw new Error(message);
    }

    return payload;
}
