import {api} from './api.js';
import {state} from './state.js';
const el = id => document.getElementById(id);
const status = message => { el('status').textContent = message; };
let selectionVersion = 0;
async function selectTenant(tenantId) {
    const version = ++selectionVersion;
    state.tenantId = tenantId;
    state.context = null;
    el('content').replaceChildren();
    if (!tenantId) { status('Nenhum espaço autorizado para esta aplicação.'); return; }
    status('Carregando espaço…');
    try {
        const context = await api('/api/v1/context');
        if (version !== selectionVersion) return;
        state.context = context;
        status('Espaço selecionado.');
    } catch (error) { if (version === selectionVersion) status(error.message); }
}
el('tenant').addEventListener('change', event => selectTenant(event.target.value));
el('logout').addEventListener('click', async () => {
    try { await api('/auth/logout', {method: 'POST'}); location.replace('/'); }
    catch (error) { status(error.message); }
});
try {
    state.session = await api('/auth/session');
    const {tenants} = await api('/auth/tenants');
    for (const tenant of tenants) {
        const option = document.createElement('option');
        option.value = tenant.id; option.textContent = tenant.name;
        el('tenant').append(option);
    }
    el('workspace').hidden = false;
    await selectTenant(tenants[0]?.id ?? null);
} catch (error) {
    el('login').hidden = error.status !== 401;
    status(error.status === 401 ? 'Entre para selecionar seu espaço.' : error.message);
}
