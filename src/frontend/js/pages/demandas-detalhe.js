import {get, post} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, toast, tratarErro} from '../ui.js';
import {badgePrioridade, badgeStatus, dataHora} from './demandas-comum.js';

const MAX_COMENTARIO = 5000;

function rotuloEvento(e) {
    switch (e.tipo) {
        case 'ABERTURA': return `Aberta por ${e.autor_sub}`;
        case 'CLASSIFICACAO': return e.grupo_nome
            ? `Classificada para ${e.grupo_nome} por ${e.autor_sub}` : `Classificada por ${e.autor_sub}`;
        case 'CONCLUSAO': return `Concluída por ${e.autor_sub}`;
        case 'REABERTURA': return `Reaberta por ${e.autor_sub}`;
        case 'CANCELAMENTO': return `Cancelada por ${e.autor_sub}`;
        default: return `${e.tipo} por ${e.autor_sub}`;
    }
}

function itemEvento(e) {
    if (e.tipo === 'COMENTARIO') {
        return h('li', {class: 'dem-comentario'},
            h('div', {class: 'dem-comentario-topo'}, h('strong', {text: e.autor_sub}), h('span', {text: dataHora(e.created_at)})),
            h('p', {class: 'dem-comentario-texto', text: e.texto ?? ''}));
    }
    return h('li', {class: 'dem-evento', text: `${rotuloEvento(e)} · ${dataHora(e.created_at)}`});
}

export const demandaDetalhe = {
    titulo: 'Demanda',
    subtitulo: 'Detalhes, histórico e comentários',
    ativo: '/demandas',
    async render(container, signal, params = {}) {
        const id = encodeURIComponent(params.id ?? '');
        const base = `/api/v1/demandas/${id}`;
        const escrita = podeEscrever();
        const cabecalho = h('section', {class: 'cartao'});
        const acoesBox = h('div', {class: 'acoes'});
        const linha = h('ul', {class: 'dem-linha'});
        const formBox = h('div', {});
        let atual = null;

        const voltar = h('p', {}, h('a', {href: '#/demandas', text: '← Voltar para Demandas'}));

        function naoEncontrada() {
            container.replaceChildren(voltar, estadoVazio('Demanda não encontrada',
                'Ela não existe ou você não tem acesso a ela.'));
        }

        async function acao(caminho, mensagem) {
            try { await post(`${base}/${caminho}`); toast(mensagem, 'success'); await carregarTudo(); }
            catch (erro) { tratarErro(erro); }
        }

        function desenharAcoes(d) {
            const botoes = [];
            if (escrita && d.status === 'ABERTA') {
                botoes.push(h('button', {type: 'button', on: {click: () => acao('concluir', 'Demanda concluída.')}}, 'Concluir'));
                botoes.push(h('button', {type: 'button', class: 'perigo', on: {click: async () => {
                    if (!await confirmar(`Cancelar a demanda "${d.titulo}"?`, 'Cancelar demanda')) return;
                    await acao('cancelar', 'Demanda cancelada.');
                }}}, 'Cancelar'));
            } else if (escrita && d.status === 'CONCLUIDA') {
                botoes.push(h('button', {type: 'button', class: 'secundario', on: {click: () => acao('reabrir', 'Demanda reaberta.')}}, 'Reabrir'));
            }
            acoesBox.replaceChildren(...botoes);
        }

        function desenharCabecalho(d) {
            cabecalho.replaceChildren(
                h('div', {class: 'cartao-topo'}, h('h2', {text: d.titulo}), acoesBox),
                h('div', {class: 'dem-meta'}, badgeStatus(d.status), badgePrioridade(d.prioridade),
                    h('span', {class: 'texto-suave', text: `Grupo: ${d.grupo_nome ?? '—'}`}),
                    h('span', {class: 'texto-suave', text: `Solicitante: ${d.solicitante_sub}`}),
                    h('span', {class: 'texto-suave', text: `Aberta em ${dataHora(d.created_at)}`}),
                    d.concluido_em ? h('span', {class: 'texto-suave', text: `Concluída em ${dataHora(d.concluido_em)}`}) : null,
                    d.cancelado_em ? h('span', {class: 'texto-suave', text: `Cancelada em ${dataHora(d.cancelado_em)}`}) : null),
                d.descricao ? h('p', {class: 'dem-descricao', text: d.descricao}) : h('p', {class: 'texto-suave', text: 'Sem descrição.'}));
            desenharAcoes(d);
        }

        function desenharForm(d) {
            if (d.status === 'CANCELADA') {
                formBox.replaceChildren(h('p', {class: 'texto-suave', text: 'Demanda cancelada: comentários encerrados.'}));
                return;
            }
            const texto = h('textarea', {rows: 3, maxLength: MAX_COMENTARIO, required: true, 'aria-label': 'Comentário'});
            const contador = h('span', {class: 'dem-contador', text: `0/${MAX_COMENTARIO}`});
            const enviar = h('button', {type: 'submit', disabled: true}, 'Comentar');
            const atualizar = () => {
                contador.textContent = `${texto.value.length}/${MAX_COMENTARIO}`;
                enviar.disabled = !texto.value.trim();
            };
            texto.addEventListener('input', atualizar);
            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const valor = texto.value.trim();
                if (!valor || valor.length > MAX_COMENTARIO) return;
                enviar.disabled = true;
                try {
                    const novo = await post(`${base}/comentarios`, {texto: valor});
                    if (signal.aborted) return;
                    linha.append(itemEvento(novo));
                    texto.value = '';
                    toast('Comentário enviado.', 'success');
                } catch (erro) { tratarErro(erro); }
                atualizar();
            }}},
                h('div', {class: 'dem-largo'}, campo('Novo comentário', texto)), contador,
                h('div', {class: 'acoes'}, enviar));
            formBox.replaceChildren(form);
        }

        async function carregarTudo() {
            const [d, eventos] = await Promise.all([get(base, undefined, signal), get(`${base}/historico`, undefined, signal)]);
            if (signal.aborted) return;
            atual = d;
            desenharCabecalho(d);
            linha.replaceChildren(...eventos.map(itemEvento));
            desenharForm(d);
        }

        container.replaceChildren(voltar, cabecalho,
            h('section', {class: 'cartao'}, h('h2', {text: 'Histórico'}), linha, formBox));
        try { await carregarTudo(); }
        catch (erro) {
            if (signal.aborted) return;
            if (erro.status === 404) { naoEncontrada(); return; }
            throw erro;
        }
        return () => { atual = null; };
    }
};
