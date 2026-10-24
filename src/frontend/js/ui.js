const PROPRIEDADES = new Set(['value', 'checked', 'disabled', 'hidden', 'selected', 'type', 'required', 'min', 'max', 'step', 'maxLength', 'placeholder', 'name', 'id', 'htmlFor', 'colSpan', 'open', 'rows']);

export function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [chave, valor] of Object.entries(attrs ?? {})) {
        if (valor === undefined || valor === null || valor === false) continue;
        if (chave === 'on') {
            for (const [evento, fn] of Object.entries(valor)) el.addEventListener(evento, fn);
        } else if (chave === 'class') el.className = valor;
        else if (chave === 'text') el.textContent = valor;
        else if (chave === 'dataset') Object.assign(el.dataset, valor);
        else if (chave === 'style' || /^on/i.test(chave)) throw new Error(`Atributo não permitido: ${chave}`);
        else if (PROPRIEDADES.has(chave)) el[chave] = valor;
        else el.setAttribute(chave, valor === true ? '' : valor);
    }
    anexar(el, children);
    return el;
}

function anexar(el, children) {
    for (const filho of children) {
        if (filho === undefined || filho === null || filho === false) continue;
        if (Array.isArray(filho)) anexar(el, filho);
        else el.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
    }
}

const SVG = 'http://www.w3.org/2000/svg';

// Ícone do sprite local (img/icones.svg). Decorativo por padrão; com `rotulo`, vira imagem acessível.
export function icone(nome, {classe = '', rotulo} = {}) {
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('class', `icone ${classe}`.trim());
    if (rotulo) { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', rotulo); }
    else svg.setAttribute('aria-hidden', 'true');
    const uso = document.createElementNS(SVG, 'use');
    uso.setAttribute('href', `/img/icones.svg#${nome}`);
    svg.append(uso);
    return svg;
}

// Placeholder de carregamento com `linhas` blocos.
export function carregando(linhas = 3) {
    return h('div', {class: 'carregando', 'aria-busy': 'true', 'aria-label': 'Carregando'},
        Array.from({length: linhas}, () => h('div', {class: 'esqueleto esqueleto-cartao'})));
}

const ICONE_TOAST = {success: 'circle-check', error: 'triangle-alert', info: 'info'};

export function toast(mensagem, tipo = 'info') {
    const regiao = document.getElementById('toasts');
    if (!regiao) return;
    const item = h('div', {class: `toast toast-${tipo}`, role: tipo === 'error' ? 'alert' : 'status'}, icone(ICONE_TOAST[tipo] ?? 'info'), h('span', {}, mensagem));
    regiao.append(item);
    setTimeout(() => item.remove(), tipo === 'error' ? 7000 : 4000);
}

export function confirmar(mensagem, rotulo = 'Confirmar') {
    const dialogo = document.getElementById('confirmacao');
    if (!dialogo || typeof dialogo.showModal !== 'function') return Promise.resolve(false);
    document.getElementById('confirmacao-texto').textContent = mensagem;
    document.getElementById('confirmacao-ok').textContent = rotulo;
    return new Promise(resolve => {
        dialogo.addEventListener('close', () => resolve(dialogo.returnValue === 'ok'), {once: true});
        dialogo.returnValue = 'cancel';
        dialogo.showModal();
    });
}

const fmtNumero = new Intl.NumberFormat('pt-BR');
const fmtPct = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
export const numero = valor => fmtNumero.format(valor ?? 0);
// Percentual já em escala 0-100.
export const pct = valor => `${fmtPct.format(valor ?? 0)}%`;
// Fração 0-1 convertida para percentual.
export const pctFracao = valor => pct((valor ?? 0) * 100);
export const pp = valor => `${valor > 0 ? '+' : valor < 0 ? '−' : ''}${fmtPct.format(Math.abs(valor ?? 0))} p.p.`;
const fmtMoeda = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'});
const fmtMoedaCurta = new Intl.NumberFormat('pt-BR', {notation: 'compact', maximumFractionDigits: 1});
const fmtDecimal = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 0, maximumFractionDigits: 2});
// Valores monetários em R$ (negativos aparecem com sinal).
export const moeda = valor => fmtMoeda.format(valor ?? 0);
export const moedaCurta = valor => fmtMoedaCurta.format(valor ?? 0);
export const decimal = valor => fmtDecimal.format(valor ?? 0);
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
// "2026-03" -> "mar/26"; com longo=true, "mar/2026".
export function competencia(valor, longo = false) {
    const [a, m] = String(valor ?? '').split('-');
    const nome = MESES[Number(m) - 1];
    return a && nome ? `${nome}/${longo ? a : a.slice(2)}` : '—';
}
// Mês atual do navegador em YYYY-MM.
export const mesAtual = () => hojeLocal().slice(0, 7);
export function data(iso) {
    if (!iso) return '—';
    const [a, m, d] = String(iso).slice(0, 10).split('-');
    return a && m && d ? `${d}/${m}/${a}` : '—';
}
// Data local do navegador em YYYY-MM-DD (nunca toISOString, que converte para UTC).
export function hojeLocal() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
// Minutos como "1 h 30 min", "2 h" ou "45 min".
export function minutos(total) {
    const m = Math.max(0, Math.round(total ?? 0));
    const horas = Math.floor(m / 60), resto = m % 60;
    if (!horas) return `${resto} min`;
    return resto ? `${horas} h ${resto} min` : `${horas} h`;
}
export function periodo(semana) {
    if (!semana.data_inicio && !semana.data_fim) return 'Sem período definido';
    return `${data(semana.data_inicio)} a ${data(semana.data_fim)}`;
}

export function campo(rotulo, controle) {
    return h('label', {class: 'campo'}, h('span', {text: rotulo}), controle);
}

// `titulo` pode ser string ou {titulo, icone}; o ícone padrão é "inbox".
export function estadoVazio(titulo, texto, ...acoes) {
    const {titulo: t, icone: nome = 'inbox'} = typeof titulo === 'object' && titulo !== null ? titulo : {titulo};
    return h('div', {class: 'estado-vazio'}, h('div', {class: 'icone-vazio'}, icone(nome)), h('h3', {text: t}), h('p', {text: texto}), acoes.length ? h('div', {class: 'acoes'}, acoes) : null);
}

export function salvarArquivo(nome, conteudo, tipo) {
    const url = URL.createObjectURL(new Blob([conteudo], {type: tipo}));
    const link = h('a', {href: url, download: nome});
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function tratarErro(erro) {
    if (erro?.status === 401) { location.replace('/'); return; }
    toast(erro?.message ?? 'Erro inesperado.', 'error');
}
