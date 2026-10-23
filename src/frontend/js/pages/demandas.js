import {get, post} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, toast, tratarErro} from '../ui.js';
import {opcao} from './finops-comum.js';
import {STATUS_DEMANDA, badgePrioridade, badgeStatus, dataHora, selecionarPrioridade} from './demandas-comum.js';

export const demandas = {
    titulo: 'Demandas',
    subtitulo: 'Abra uma demanda e acompanhe o andamento',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const titulo = h('input', {type: 'text', required: true, maxLength: 200});
        const descricao = h('textarea', {rows: 4, maxLength: 10000});
        const prioridade = selecionarPrioridade('MEDIA');
        const fStatus = h('select', {}, opcao('', 'Todos os status'), Object.entries(STATUS_DEMANDA).map(([v, t]) => opcao(v, t)));
        const fGrupo = h('select', {}, opcao('', 'Todos os grupos'));
        const fMinhas = h('input', {type: 'checkbox'});

        async function carregarGrupos() {
            const grupos = await get('/api/v1/grupos', undefined, signal);
            if (signal.aborted) return;
            fGrupo.replaceChildren(opcao('', 'Todos os grupos'), ...grupos.map(g => opcao(g.id, g.nome)));
        }

        async function acao(d, caminho, mensagem) {
            try { await post(`/api/v1/demandas/${d.id}/${caminho}`); toast(mensagem, 'success'); await recarregar(); }
            catch (erro) { tratarErro(erro); }
        }

        function acoes(d) {
            const botoes = [];
            if (d.status === 'ABERTA') {
                botoes.push(h('button', {type: 'button', class: 'pequeno', on: {click: () => acao(d, 'concluir', 'Demanda concluída.')}}, 'Concluir'));
                botoes.push(h('button', {type: 'button', class: 'perigo pequeno', on: {click: async () => {
                    if (!await confirmar(`Cancelar a demanda "${d.titulo}"?`, 'Cancelar demanda')) return;
                    await acao(d, 'cancelar', 'Demanda cancelada.');
                }}}, 'Cancelar'));
            } else if (d.status === 'CONCLUIDA') {
                botoes.push(h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => acao(d, 'reabrir', 'Demanda reaberta.')}}, 'Reabrir'));
            }
            return h('td', {class: 'acoes'}, botoes);
        }

        async function carregar() {
            const itens = await get('/api/v1/demandas', escrita
                ? {status: fStatus.value, grupo_id: fGrupo.value, minhas: fMinhas.checked ? 'true' : ''} : undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio('Nenhuma demanda encontrada',
                    escrita ? 'Ajuste os filtros ou abra uma nova demanda.' : 'Você ainda não abriu nenhuma demanda.'));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Título', 'Prioridade', 'Status', 'Grupo', 'Aberta em', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(d => h('tr', {},
                    h('td', {}, h('strong', {text: d.titulo}), d.descricao ? h('div', {class: 'texto-suave dem-descricao', text: d.descricao}) : null),
                    h('td', {}, badgePrioridade(d.prioridade)),
                    h('td', {}, badgeStatus(d.status)),
                    h('td', {text: d.grupo_nome ?? '—'}),
                    h('td', {text: dataHora(d.created_at)}),
                    escrita ? acoes(d) : null))))));
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        const form = h('form', {class: 'formulario', on: {submit: async evento => {
            evento.preventDefault();
            try {
                await post('/api/v1/demandas', {titulo: titulo.value.trim(), descricao: descricao.value.trim() || null, prioridade: prioridade.value});
                titulo.value = ''; descricao.value = ''; prioridade.value = 'MEDIA';
                toast('Demanda aberta.', 'success');
                await recarregar();
            } catch (erro) { tratarErro(erro); }
        }}},
            h('h2', {text: 'Nova demanda'}),
            campo('Título', titulo), campo('Prioridade', prioridade),
            h('div', {class: 'dem-largo'}, campo('Descrição', descricao)),
            h('div', {class: 'acoes'}, h('button', {type: 'submit'}, 'Abrir demanda')));

        const filtros = escrita ? h('div', {class: 'barra-acoes'}, h('div', {class: 'acoes'},
            campo('Status', fStatus), campo('Grupo', fGrupo),
            h('label', {class: 'campo-check'}, fMinhas, ' Minhas demandas'))) : null;
        for (const controle of [fStatus, fGrupo, fMinhas]) controle.addEventListener('change', recarregar);

        container.replaceChildren(
            h('section', {class: 'cartao'}, form),
            h('h2', {text: escrita ? 'Demandas' : 'Minhas demandas'}),
            filtros, lista);
        if (escrita) await carregarGrupos();
        await carregar();
    }
};
