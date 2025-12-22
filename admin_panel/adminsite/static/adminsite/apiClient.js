const defaultHeaders = { 'Content-Type': 'application/json' };

function parseErrorDetail(detail) {
    if (!detail) return 'Ошибка запроса';
    if (typeof detail === 'string') return detail;
    if (detail.detail) return parseErrorDetail(detail.detail);
    return JSON.stringify(detail);
}

export async function apiRequest(url, options = {}) {
    const opts = { credentials: 'include', ...options };
    if (opts.body && !(opts.body instanceof FormData)) {
        opts.headers = { ...defaultHeaders, ...(opts.headers || {}) };
        opts.body = JSON.stringify(opts.body);
    }

    const response = await fetch(url, opts);
    const responseText = response.status === 204 ? '' : await response.text();

    let payload = null;
    let parseError = null;
    if (responseText) {
        try {
            payload = JSON.parse(responseText);
        } catch (error) {
            parseError = error;
        }
    }

    if (!response.ok) {
        const message = payload ? parseErrorDetail(payload) : responseText || `HTTP ${response.status}`;
        const error = new Error(message);
        error.status = response.status;
        error.body = responseText;
        throw error;
    }

    if (parseError) {
        const error = new Error(responseText || 'Ответ не похож на JSON');
        error.status = response.status;
        error.body = responseText;
        throw error;
    }

    return payload;
}
