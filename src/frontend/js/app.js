import {api} from './api.js';
import {state} from './state.js';
import {registrarRotas, iniciarRouter, renderizar, limparConteudo} from './router.js';
import {painel} from './pages/painel.js';
import {lancamentos} from './pages/lancamentos.js';
import {grupos} from './pages/grupos.js';
import {semanas} from './pages/semanas.js';
import {rotinas} from './pages/rotinas.js';
import {rotinasCatalogo} from './pages/rotinas-catalogo.js';
import {finopsPainel} from './pages/finops-painel.js';
import {finopsIniciativas} from './pages/finops-iniciativas.js';
import {finopsFaturas} from './pages/finops-faturas.js';
import {despesasPainel} from './pages/despesas-painel.js';
import {despesasInventario} from './pages/despesas-inventario.js';
import {despesasOrcamento} from './pages/despesas-orcamento.js';
import {perfis} from './pages/perfis.js';
import {meuDia} from './pages/meu-dia.js';

const el = id => document.getElementById(id);
const status = message => { el('status').textContent = message; };
let selectionVersion = 0;
let routerIniciado = false;

registrarRotas({
    '/meu-dia': meuDia,
    '/': painel,
    '/rotinas': rotinas,
    '/lancamentos': lancamentos,
    '/finops': finopsPainel,
    '/finops/iniciativas': finopsIniciativas,
    '/finops/faturas': finopsFaturas,
    '/despesas': despesasPainel,
    '/despesas/inventario': despesasInventario,
    '/despesas/orcamento': despesasOrcamento,
    '/config/grupos': grupos,
    '/config/semanas': semanas,
    '/config/rotinas': rotinasCatalogo,
    '/config/perfis': perfis
});

async function selectTenant(tenantId) {
    const version = ++selectionVersion;
    state.tenantId = tenantId;
    state.context = null;
    limparConteudo();
    if (!tenantId) { status('Nenhum espaço autorizado para esta aplicação.'); return; }
    status('Carregando espaço…');
    try {
        const context = await api('/api/v1/context');
        if (version !== selectionVersion) return;
        state.context = context;
        status('');
        if (routerIniciado) await renderizar();
        else { routerIniciado = true; await iniciarRouter(el('content')); }
    } catch (error) {
        if (version !== selectionVersion) return;
        status(error.message);
    }
}

el('tenant').addEventListener('change', event => selectTenant(event.target.value));
el('logout').addEventListener('click', async () => {
    try { await api('/auth/logout', {method: 'POST'}); location.replace('/'); }
    catch (error) { status(error.message); }
});
el('menu').addEventListener('click', () => {
    const aberta = el('sidebar').classList.toggle('aberta');
    el('menu').setAttribute('aria-expanded', String(aberta));
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
    el('nav').hidden = false;
    await selectTenant(tenants[0]?.id ?? null);
} catch (error) {
    el('login').hidden = error.status !== 401;
    status(error.status === 401 ? 'Entre para selecionar seu espaço.' : error.message);
}
