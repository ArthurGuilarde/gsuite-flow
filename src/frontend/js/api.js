import {state} from './state.js';
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
        const error = new Error(body.detail || `HTTP ${response.status}`);
        error.status = response.status;
        throw error;
    }
    return response.status === 204 ? null : response.json();
}
