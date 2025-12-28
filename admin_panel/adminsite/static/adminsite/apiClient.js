const defaultHeaders = { 'Content-Type': 'application/json' };

function parseValidationErrors(detail) {
    if (!Array.isArray(detail)) return null;

    const messages = [];
    detail.forEach((item) => {
        const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null;
        const message = item?.msg || item?.message;

        if (item?.type === 'string_pattern_mismatch' && field === 'slug') {
            messages.push('Slug может содержать только латиницу, цифры и дефисы.');
            return;
        }

        if (message && field) {
            messages.push(`${field}: ${message}`);
        } else if (message) {
            messages.push(message);
        }
    });

    if (!messages.length) return null;
    return messages.join('; ');
}

function parseErrorDetail(detail) {
    if (!detail) return 'Ошибка запроса';
    if (typeof detail === 'string') return detail;

    if (detail.error_id) {
        return `${detail.detail || detail.message || 'Internal Error'} (error_id: ${detail.error_id})`;
    }

    if (detail.detail) {
        const validation = parseValidationErrors(detail.detail);
        return validation || parseErrorDetail(detail.detail);
    }

    const validation = parseValidationErrors(detail);
    if (validation) return validation;

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
        if (payload?.error_id) {
            error.errorId = payload.error_id;
        }
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
