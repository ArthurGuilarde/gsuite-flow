import {state} from './state.js';

function mensagemDeErro(body, status) {
    const detail = body?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (typeof detail?.mensagem === 'string' && detail.mensagem) return detail.mensagem;
    if (Array.isArray(detail) && detail.length) {
        return detail.map(item => {
            if (typeof item === 'string') return item;
            const campo = Array.isArray(item?.loc) ? item.loc.filter(parte => parte !== 'body').join('.') : '';
            const texto = item?.msg ?? 'valor inválido';
            return campo ? `${campo}: ${texto}` : texto;
        }).join('; ');
    }
    return `HTTP ${status}`;
}

export async function api(path, options = {}) {
    const headers = new Headers(options.headers);
    if (state.tenantId) headers.set('X-Tenant-ID', state.tenantId);
    if (options.method && !['GET', 'HEAD'].includes(options.method)) {
        headers.set('X-CSRF-Token', state.session?.csrf_token ?? '');
        headers.set('Content-Type', 'application/json');
    }
    const response = await fetch(path, {...options, headers, credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const error = new Error(mensagemDeErro(body, response.status));
        error.status = response.status;
        throw error;
    }
    return response.status === 204 ? null : response.json();
}

function comQuery(path, query) {
    const params = new URLSearchParams();
    for (const [chave, valor] of Object.entries(query ?? {})) {
        if (valor !== undefined && valor !== null && valor !== '') params.set(chave, valor);
    }
    const texto = params.toString();
    return texto ? `${path}?${texto}` : path;
}

const corpo = (method, body, signal) => ({method, signal, ...(body === undefined ? {} : {body: JSON.stringify(body)})});

export const get = (path, query, signal) => api(comQuery(path, query), {signal});
export const post = (path, body = {}, signal) => api(path, corpo('POST', body, signal));
export const patch = (path, body, signal) => api(path, corpo('PATCH', body, signal));
export const put = (path, body, signal) => api(path, corpo('PUT', body, signal));
export const del = (path, signal) => api(path, corpo('DELETE', undefined, signal));
