import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, moeda, toast, tratarErro} from '../ui.js';
import {CUSTO_HORA_SUGERIDO} from './finops-comum.js';

export const perfis = {
    titulo: 'Perfis de custo/hora',
    subtitulo: 'Presets usados no cálculo de horas do time',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            const itens = await get('/api/v1/finops/perfis', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio('Nenhum perfil cadastrado',
                    `Sem perfis, o formulário de iniciativa sugere ${moeda(CUSTO_HORA_SUGERIDO)}/h. Cadastre perfis como Analista ou Executivo para padronizar o cálculo.`));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Perfil', 'Custo/hora', 'Situação', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(p => h('tr', {class: p.ativo ? '' : 'inativa'},
                    h('td', {text: p.nome}),
                    h('td', {class: 'num', text: moeda(p.custo_hora)}),
                    h('td', {}, h('span', {class: `badge ${p.ativo ? 'badge-resolvido' : ''}`, text: p.ativo ? 'Ativo' : 'Inativo'})),
                    escrita ? h('td', {class: 'acoes'},
                        h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editar(p)}}, 'Editar'),
                        h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => excluir(p)}}, 'Excluir')) : null))))));
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        async function excluir(p) {
            if (!await confirmar(`Excluir o perfil "${p.nome}"? Iniciativas já salvas não mudam: elas guardam uma cópia do custo/hora.`, 'Excluir')) return;
            try { await del(`/api/v1/finops/perfis/${p.id}`); toast('Perfil excluído.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function editar(p = null) {
            const nome = h('input', {type: 'text', required: true, maxLength: 80, value: p?.nome ?? ''});
            const custo = h('input', {type: 'number', required: true, min: 0, step: 0.01, value: p?.custo_hora ?? ''});
            const ativo = h('input', {type: 'checkbox', checked: p ? p.ativo : true});
            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {nome: nome.value.trim(), custo_hora: Number(custo.value)};
                try {
                    if (p) await patch(`/api/v1/finops/perfis/${p.id}`, {...corpo, ativo: ativo.checked});
                    else await post('/api/v1/finops/perfis', corpo);
                    formulario.replaceChildren();
                    toast(p ? 'Perfil atualizado.' : 'Perfil criado.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {text: p ? 'Editar perfil' : 'Novo perfil'}),
                campo('Nome (ex.: Analista)', nome), campo('Custo por hora (R$)', custo),
                p ? h('label', {class: 'campo-check'}, ativo, ' Ativo (inativos não aparecem como opção)') : null,
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            nome.focus();
        }

        container.replaceChildren(
            h('div', {class: 'barra-acoes'},
                h('div', {class: 'acoes'}, escrita ? h('button', {type: 'button', on: {click: () => editar()}}, 'Novo perfil') : null),
                h('p', {class: 'texto-suave pequeno-texto', text: 'Mudar o custo/hora de um perfil não reescreve iniciativas existentes.'})),
            formulario, lista);
        await carregar();
    }
};
