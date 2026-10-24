import {get, post} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, icone, toast, tratarErro} from '../ui.js';
import {opcao} from './finops-comum.js';
import {STATUS_DEMANDA, badgePrioridade, badgeStatus, classePrioridade, dataHora, idade, selecionarPrioridade} from './demandas-comum.js';

export const demandas = {
    titulo: 'Demandas',
    subtitulo: 'Abra uma demanda e acompanhe o andamento',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {}, carregando(3));
        const contagem = h('span', {class: 'badge', text: '…'});
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
                botoes.push(h('button', {type: 'button', class: 'pequeno', on: {click: () => acao(d, 'concluir', 'Demanda concluída.')}}, icone('check', {classe: 'icone-sm'}), 'Concluir'));
                botoes.push(h('button', {type: 'button', class: 'secundario perigo pequeno so-icone', title: 'Cancelar demanda', 'aria-label': `Cancelar a demanda ${d.titulo}`, on: {click: async () => {
                    if (!await confirmar(`Cancelar a demanda "${d.titulo}"?`, 'Cancelar demanda')) return;
                    await acao(d, 'cancelar', 'Demanda cancelada.');
                }}}, icone('x', {classe: 'icone-sm'})));
            } else if (d.status === 'CONCLUIDA') {
                botoes.push(h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => acao(d, 'reabrir', 'Demanda reaberta.')}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Reabrir'));
            }
            return h('td', {class: 'acoes dem-col-acoes', 'data-rotulo': 'Ações'}, h('div', {class: 'acoes'}, botoes));
        }

        async function carregar() {
            const itens = await get('/api/v1/demandas', escrita
                ? {status: fStatus.value, grupo_id: fGrupo.value, minhas: fMinhas.checked ? 'true' : ''} : undefined, signal);
            if (signal.aborted) return;
            contagem.textContent = String(itens.length);
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Nenhuma demanda encontrada', icone: 'inbox'},
                    escrita ? 'Ajuste os filtros ou abra uma nova demanda.' : 'Você ainda não abriu nenhuma demanda.'));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {class: 'dem-tabela'},
                h('thead', {}, h('tr', {}, ['Demanda', 'Prioridade', 'Status', 'Grupo', 'Aberta', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(d => h('tr', {class: classePrioridade(d.prioridade)},
                    h('td', {class: 'dem-col-titulo'}, h('a', {href: `#/demandas/${d.id}`, class: 'dem-link'}, h('strong', {text: d.titulo})), d.descricao ? h('div', {class: 'texto-suave dem-descricao dem-resumo', text: d.descricao}) : null),
                    h('td', {'data-rotulo': 'Prioridade'}, badgePrioridade(d.prioridade)),
                    h('td', {'data-rotulo': 'Status'}, badgeStatus(d.status)),
                    h('td', {class: 'dem-col-grupo', 'data-rotulo': 'Grupo'}, d.grupo_nome ?? '—'),
                    h('td', {class: 'dem-col-data', 'data-rotulo': 'Aberta', title: dataHora(d.created_at)}, h('span', {text: idade(d.created_at)}), h('small', {class: 'texto-suave', text: dataHora(d.created_at)})),
                    escrita ? acoes(d) : null))))));
            contagem.textContent = String(itens.length);
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        const form = h('form', {class: 'formulario dem-form', on: {submit: async evento => {
            evento.preventDefault();
            try {
                await post('/api/v1/demandas', {titulo: titulo.value.trim(), descricao: descricao.value.trim() || null, prioridade: prioridade.value});
                titulo.value = ''; descricao.value = ''; prioridade.value = 'MEDIA';
                toast('Demanda aberta.', 'success');
                await recarregar();
            } catch (erro) { tratarErro(erro); }
        }}},
            h('div', {class: 'cartao-topo dem-largo'}, h('div', {},
                h('h2', {}, icone('plus'), 'Nova demanda'),
                h('p', {class: 'texto-suave pequeno-texto', text: 'Descreva o que precisa. A equipe classifica e define o grupo responsável.'}))),
            h('div', {class: 'dem-form-titulo'}, campo('Título', titulo)), campo('Prioridade', prioridade),
            h('div', {class: 'dem-largo'}, campo('Descrição', descricao)),
            h('div', {class: 'acoes dem-form-acoes'}, h('button', {type: 'submit'}, icone('plus', {classe: 'icone-sm'}), 'Abrir demanda')));

        const filtros = escrita ? h('div', {class: 'filtros dem-filtros'},
            campo('Status', fStatus), campo('Grupo', fGrupo),
            h('label', {class: 'campo-check dem-minhas'}, fMinhas, 'Minhas demandas')) : null;
        for (const controle of [fStatus, fGrupo, fMinhas]) controle.addEventListener('change', recarregar);

        container.replaceChildren(
            h('section', {class: 'cartao'}, form),
            h('div', {class: 'barra-acoes dem-barra'},
                h('h2', {class: 'dem-titulo-lista'}, icone('inbox'), escrita ? 'Demandas' : 'Minhas demandas', contagem),
                filtros),
            lista);
        if (escrita) await carregarGrupos();
        await carregar();
    }
};
