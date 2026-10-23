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

export function toast(mensagem, tipo = 'info') {
    const regiao = document.getElementById('toasts');
    if (!regiao) return;
    const item = h('div', {class: `toast toast-${tipo}`, role: tipo === 'error' ? 'alert' : 'status'}, mensagem);
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

export function estadoVazio(titulo, texto, ...acoes) {
    return h('div', {class: 'estado-vazio'}, h('h3', {text: titulo}), h('p', {text: texto}), acoes.length ? h('div', {class: 'acoes'}, acoes) : null);
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
