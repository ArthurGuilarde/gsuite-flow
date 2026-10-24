import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, data, hojeLocal, icone, toast, tratarErro} from '../ui.js';
import {botaoEditar, botaoExcluir, botaoNovo, cabecalhoTabela} from './capacidade-comum.js';

// Situação relativa a hoje, só para leitura: sem as duas datas não há classificação.
function situacaoSemana(s, hoje) {
    if (!s.data_inicio || !s.data_fim) return null;
    if (hoje < s.data_inicio) return ['Futura', 'badge-futura'];
    if (hoje > s.data_fim) return ['Encerrada', 'badge-passada'];
    return ['Em andamento', 'badge-andamento'];
}

export const semanas = {
    titulo: 'Semanas',
    subtitulo: 'Ciclos semanais usados nos lançamentos e no painel',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            if (!lista.firstChild) lista.replaceChildren(carregando(2));
            const itens = await get('/api/v1/semanas', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Nenhuma semana cadastrada', icone: 'calendar'},
                    escrita ? 'Crie a primeira semana para começar a lançar.' : 'Peça a quem tem permissão de edição para criar as semanas.',
                    escrita ? botaoNovo('Nova semana', () => editar()) : null));
                return;
            }
            const hoje = hojeLocal();
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                cabecalhoTabela(['Identificação', 'Início', 'Fim', 'Situação'], escrita),
                h('tbody', {}, itens.map(s => {
                    const situacao = situacaoSemana(s, hoje);
                    return h('tr', {},
                        h('td', {}, h('strong', {text: s.identificacao})), h('td', {text: data(s.data_inicio)}), h('td', {text: data(s.data_fim)}),
                        h('td', {}, situacao ? h('span', {class: `badge badge-ponto ${situacao[1]}`, text: situacao[0]}) : h('span', {class: 'texto-suave', text: 'Sem período'})),
                        escrita ? h('td', {class: 'acoes'},
                            botaoEditar(`Editar ${s.identificacao}`, () => editar(s)),
                            botaoExcluir(`Excluir ${s.identificacao}`, () => excluir(s))) : null);
                })))));
        }

        async function recarregar() {
            try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); }
        }

        async function excluir(s) {
            if (!await confirmar(`Excluir a semana "${s.identificacao}"? Os lançamentos dela também serão removidos.`, 'Excluir')) return;
            try { await del(`/api/v1/semanas/${s.id}`); toast('Semana excluída.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function editar(s = null) {
            const identificacao = h('input', {type: 'text', required: true, maxLength: 60, value: s?.identificacao ?? ''});
            const inicio = h('input', {type: 'date', value: s?.data_inicio ?? ''});
            const fim = h('input', {type: 'date', value: s?.data_fim ?? ''});
            const form = h('form', {class: 'formulario form-cap', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {identificacao: identificacao.value.trim(), data_inicio: inicio.value || null, data_fim: fim.value || null};
                try {
                    if (s) await patch(`/api/v1/semanas/${s.id}`, corpo); else await post('/api/v1/semanas', corpo);
                    formulario.replaceChildren();
                    toast(s ? 'Semana atualizada.' : 'Semana criada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {}, icone(s ? 'pencil' : 'plus'), s ? 'Editar semana' : 'Nova semana'),
                campo('Identificação', identificacao), campo('Início', inicio), campo('Fim', fim),
                h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar'),
                    h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Salvar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            identificacao.focus();
        }

        container.replaceChildren(
            escrita ? h('div', {class: 'barra-acoes'}, h('div', {class: 'acoes'}, botaoNovo('Nova semana', () => editar()))) : null,
            formulario, lista);
        await carregar();
    }
};
