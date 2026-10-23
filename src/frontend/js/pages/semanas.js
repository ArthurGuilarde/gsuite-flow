import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, data, toast, tratarErro} from '../ui.js';

export const semanas = {
    titulo: 'Semanas',
    subtitulo: 'Ciclos semanais usados nos lançamentos e no painel',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            const itens = await get('/api/v1/semanas', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio('Nenhuma semana cadastrada', escrita ? 'Crie a primeira semana para começar a lançar.' : 'Peça a quem tem permissão de edição para criar as semanas.'));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Identificação', 'Início', 'Fim', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(s => h('tr', {},
                    h('td', {text: s.identificacao}), h('td', {text: data(s.data_inicio)}), h('td', {text: data(s.data_fim)}),
                    escrita ? h('td', {class: 'acoes'},
                        h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editar(s)}}, 'Editar'),
                        h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => excluir(s)}}, 'Excluir')) : null))))));
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
            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {identificacao: identificacao.value.trim(), data_inicio: inicio.value || null, data_fim: fim.value || null};
                try {
                    if (s) await patch(`/api/v1/semanas/${s.id}`, corpo); else await post('/api/v1/semanas', corpo);
                    formulario.replaceChildren();
                    toast(s ? 'Semana atualizada.' : 'Semana criada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {text: s ? 'Editar semana' : 'Nova semana'}),
                campo('Identificação', identificacao), campo('Início', inicio), campo('Fim', fim),
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            identificacao.focus();
        }

        container.replaceChildren(
            escrita ? h('div', {class: 'barra-acoes'}, h('div', {class: 'acoes'}, h('button', {type: 'button', on: {click: () => editar()}}, 'Nova semana'))) : null,
            formulario, lista);
        await carregar();
    }
};
