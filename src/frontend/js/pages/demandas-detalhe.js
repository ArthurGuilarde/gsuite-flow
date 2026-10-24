import {get, post} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, carregando, confirmar, estadoVazio, icone, toast, tratarErro} from '../ui.js';
import {badgePrioridade, badgeStatus, dataHora, idade} from './demandas-comum.js';

const MAX_COMENTARIO = 5000;

const EVENTOS = {
    ABERTURA: ['plus', 'Aberta por'],
    CLASSIFICACAO: ['list-filter', 'Classificada por'],
    CONCLUSAO: ['circle-check', 'Concluída por'],
    REABERTURA: ['rotate-ccw', 'Reaberta por'],
    CANCELAMENTO: ['x', 'Cancelada por']
};

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

function iniciais(sub) {
    const partes = String(sub ?? '').split(/[^\p{L}\p{N}]+/u).filter(Boolean);
    const texto = partes.length > 1 ? partes[0][0] + partes[1][0] : (partes[0] ?? '?').slice(0, 2);
    return texto.toUpperCase();
}

// `solicitante` distingue o autor da demanda (balão neutro) da equipe (balão destacado).
function itemEvento(e, solicitante) {
    if (e.tipo === 'COMENTARIO') {
        const doSolicitante = e.autor_sub === solicitante;
        return h('li', {class: `dem-item dem-item-comentario ${doSolicitante ? 'dem-do-solicitante' : 'dem-da-equipe'}`},
            h('span', {class: 'dem-avatar', 'aria-hidden': 'true', text: iniciais(e.autor_sub)}),
            h('div', {class: 'dem-comentario'},
                h('div', {class: 'dem-comentario-topo'},
                    h('strong', {text: e.autor_sub}),
                    h('span', {class: 'dem-papel', text: doSolicitante ? 'Solicitante' : 'Equipe'}),
                    h('time', {class: 'texto-suave', datetime: e.created_at ?? '', title: dataHora(e.created_at), text: `${idade(e.created_at)} · ${dataHora(e.created_at)}`})),
                h('p', {class: 'dem-comentario-texto', text: e.texto ?? ''})));
    }
    const [nome] = EVENTOS[e.tipo] ?? ['info'];
    return h('li', {class: `dem-item dem-item-evento dem-evento-${String(e.tipo).toLowerCase()}`},
        h('span', {class: 'dem-marca'}, icone(nome, {classe: 'icone-sm'})),
        h('p', {class: 'dem-evento'}, rotuloEvento(e), h('span', {class: 'texto-suave', text: ` · ${dataHora(e.created_at)}`})));
}

export const demandaDetalhe = {
    titulo: 'Demanda',
    subtitulo: 'Detalhes, histórico e comentários',
    ativo: '/demandas',
    async render(container, signal, params = {}) {
        const id = encodeURIComponent(params.id ?? '');
        const base = `/api/v1/demandas/${id}`;
        const escrita = podeEscrever();
        const cabecalho = h('section', {class: 'cartao dem-cabecalho'});
        const acoesBox = h('div', {class: 'acoes dem-cabecalho-acoes'});
        const linha = h('ul', {class: 'dem-linha'});
        const formBox = h('div', {class: 'dem-compositor-box'});
        const contagem = h('span', {class: 'badge', title: 'Comentários', text: '…'});
        let atual = null;

        const voltar = h('p', {class: 'dem-voltar'}, h('a', {href: '#/demandas', class: 'dem-link'}, icone('arrow-left', {classe: 'icone-sm'}), 'Voltar para Demandas'));

        function naoEncontrada() {
            container.replaceChildren(voltar, estadoVazio({titulo: 'Demanda não encontrada', icone: 'search'},
                'Ela não existe ou você não tem acesso a ela.',
                h('a', {class: 'botao secundario', href: '#/demandas', text: 'Ver demandas'})));
        }

        async function acao(caminho, mensagem) {
            try { await post(`${base}/${caminho}`); toast(mensagem, 'success'); await carregarTudo(); }
            catch (erro) { tratarErro(erro); }
        }

        function desenharAcoes(d) {
            const botoes = [];
            if (escrita && d.status === 'ABERTA') {
                botoes.push(h('button', {type: 'button', on: {click: () => acao('concluir', 'Demanda concluída.')}}, icone('check', {classe: 'icone-sm'}), 'Concluir'));
                botoes.push(h('button', {type: 'button', class: 'secundario perigo', on: {click: async () => {
                    if (!await confirmar(`Cancelar a demanda "${d.titulo}"?`, 'Cancelar demanda')) return;
                    await acao('cancelar', 'Demanda cancelada.');
                }}}, icone('x', {classe: 'icone-sm'}), 'Cancelar'));
            } else if (escrita && d.status === 'CONCLUIDA') {
                botoes.push(h('button', {type: 'button', class: 'secundario', on: {click: () => acao('reabrir', 'Demanda reaberta.')}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Reabrir'));
            }
            acoesBox.replaceChildren(...botoes);
        }

        const dado = (rotulo, valor) => h('div', {class: 'dem-dado'}, h('dt', {text: rotulo}), h('dd', {text: valor}));

        function desenharCabecalho(d) {
            cabecalho.replaceChildren(
                h('div', {class: 'dem-cabecalho-topo'},
                    h('div', {class: 'dem-cabecalho-titulo'},
                        h('div', {class: 'dem-meta'}, badgeStatus(d.status), badgePrioridade(d.prioridade)),
                        h('h2', {text: d.titulo})),
                    acoesBox),
                h('dl', {class: 'dem-dados'},
                    dado('Grupo', d.grupo_nome ?? '—'),
                    dado('Solicitante', d.solicitante_sub),
                    dado('Aberta em', dataHora(d.created_at)),
                    d.concluido_em ? dado('Concluída em', dataHora(d.concluido_em)) : null,
                    d.cancelado_em ? dado('Cancelada em', dataHora(d.cancelado_em)) : null),
                d.descricao ? h('p', {class: 'dem-descricao dem-descricao-bloco', text: d.descricao}) : h('p', {class: 'texto-suave', text: 'Sem descrição.'}));
            desenharAcoes(d);
        }

        function desenharForm(d) {
            if (d.status === 'CANCELADA') {
                formBox.replaceChildren(h('p', {class: 'dem-encerrada'}, icone('info', {classe: 'icone-sm'}), 'Demanda cancelada: comentários encerrados.'));
                return;
            }
            const texto = h('textarea', {rows: 3, maxLength: MAX_COMENTARIO, required: true, 'aria-label': 'Novo comentário', placeholder: 'Escreva um comentário…'});
            const contador = h('span', {class: 'dem-contador', text: `0/${MAX_COMENTARIO}`});
            const enviar = h('button', {type: 'submit', disabled: true}, icone('message-square', {classe: 'icone-sm'}), 'Comentar');
            const atualizar = () => {
                contador.textContent = `${texto.value.length}/${MAX_COMENTARIO}`;
                contador.classList.toggle('dem-contador-limite', texto.value.length > MAX_COMENTARIO * 0.9);
                enviar.disabled = !texto.value.trim();
            };
            texto.addEventListener('input', atualizar);
            texto.addEventListener('keydown', evento => {
                if (evento.key === 'Enter' && (evento.ctrlKey || evento.metaKey) && !enviar.disabled) { evento.preventDefault(); form.requestSubmit(); }
            });
            const form = h('form', {class: 'dem-compositor', on: {submit: async evento => {
                evento.preventDefault();
                const valor = texto.value.trim();
                if (!valor || valor.length > MAX_COMENTARIO) return;
                enviar.disabled = true;
                try {
                    const novo = await post(`${base}/comentarios`, {texto: valor});
                    if (signal.aborted) return;
                    linha.append(itemEvento(novo, d.solicitante_sub));
                    contagem.textContent = String(linha.querySelectorAll('.dem-item-comentario').length);
                    texto.value = '';
                    toast('Comentário enviado.', 'success');
                } catch (erro) { tratarErro(erro); }
                atualizar();
            }}},
                texto,
                h('div', {class: 'dem-compositor-rodape'},
                    h('span', {class: 'dem-contador-grupo'}, contador, h('span', {class: 'texto-suave', text: 'Ctrl+Enter envia'})),
                    enviar));
            formBox.replaceChildren(form);
        }

        async function carregarTudo() {
            const [d, eventos] = await Promise.all([get(base, undefined, signal), get(`${base}/historico`, undefined, signal)]);
            if (signal.aborted) return;
            atual = d;
            desenharCabecalho(d);
            linha.replaceChildren(...eventos.map(e => itemEvento(e, d.solicitante_sub)));
            contagem.textContent = String(eventos.filter(e => e.tipo === 'COMENTARIO').length);
            desenharForm(d);
        }

        container.replaceChildren(voltar, cabecalho,
            h('section', {class: 'cartao dem-conversa'},
                h('div', {class: 'cartao-topo'}, h('h2', {}, icone('message-square'), 'Conversa e histórico', contagem)),
                linha, formBox));
        cabecalho.replaceChildren(carregando(1));
        try { await carregarTudo(); }
        catch (erro) {
            if (signal.aborted) return;
            if (erro.status === 404) { naoEncontrada(); return; }
            throw erro;
        }
        return () => { atual = null; };
    }
};
