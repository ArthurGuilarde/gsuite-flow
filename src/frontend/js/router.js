const rotas = new Map();
let limpeza = null;
let controle = null;
let alvo = null;

export function registrarRotas(definicoes) {
    for (const [caminho, rota] of Object.entries(definicoes)) rotas.set(caminho, rota);
}

export const caminhoAtual = () => location.hash.replace(/^#/, '') || '/';

function marcarAtivo(caminho) {
    for (const link of document.querySelectorAll('[data-rota]')) {
        const ativo = link.dataset.rota === caminho;
        link.classList.toggle('ativo', ativo);
        if (ativo) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    }
}

function encerrar() {
    controle?.abort();
    controle = null;
    try { limpeza?.(); } catch { /* cleanup não deve quebrar a navegação */ }
    limpeza = null;
}

export function limparConteudo() {
    encerrar();
    alvo?.replaceChildren();
}

export async function renderizar() {
    encerrar();
    if (!alvo) return;
    const caminho = caminhoAtual();
    const rota = rotas.get(caminho);
    marcarAtivo(caminho);
    alvo.replaceChildren();
    document.getElementById('pagina-titulo').textContent = rota?.titulo ?? 'Página não encontrada';
    document.getElementById('pagina-subtitulo').textContent = rota?.subtitulo ?? '';
    document.title = `${rota?.titulo ?? 'GFlow'} · GFlow`;
    document.getElementById('sidebar')?.classList.remove('aberta');
    if (!rota) {
        const pagina = document.createElement('p');
        pagina.className = 'texto-suave';
        pagina.textContent = 'Página não encontrada.';
        alvo.append(pagina);
        return;
    }
    const meu = new AbortController();
    controle = meu;
    try {
        const resultado = await rota.render(alvo, meu.signal);
        if (meu.signal.aborted) { try { resultado?.(); } catch { /* ignora */ } return; }
        if (typeof resultado === 'function') limpeza = resultado;
    } catch (erro) {
        if (meu.signal.aborted) return;
        if (erro.status === 401) { location.replace('/'); return; }
        const msg = document.createElement('p');
        msg.className = 'erro';
        msg.textContent = erro.message;
        alvo.replaceChildren(msg);
    }
}

export function iniciarRouter(elementoConteudo) {
    alvo = elementoConteudo;
    window.addEventListener('hashchange', renderizar);
    return renderizar();
}
