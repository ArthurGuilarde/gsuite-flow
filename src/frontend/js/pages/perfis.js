import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, icone, moeda, toast, tratarErro} from '../ui.js';
import {badgeSituacaoAtivo, botaoEditar, botaoExcluir, botaoNovo, cabecalhoTabela} from './capacidade-comum.js';
import {CUSTO_HORA_SUGERIDO} from './finops-comum.js';

export const perfis = {
    titulo: 'Perfis de custo/hora',
    subtitulo: 'Presets usados no cálculo de horas do time',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            if (!lista.firstChild) lista.replaceChildren(carregando(2));
            const itens = await get('/api/v1/finops/perfis', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Nenhum perfil cadastrado', icone: 'badge-dollar-sign'},
                    `Sem perfis, o formulário de iniciativa sugere ${moeda(CUSTO_HORA_SUGERIDO)}/h. Cadastre perfis como Analista ou Executivo para padronizar o cálculo.`,
                    escrita ? botaoNovo('Novo perfil', () => editar()) : null));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                cabecalhoTabela(['Perfil', 'Custo/hora', 'Situação'], escrita, ['Custo/hora']),
                h('tbody', {}, itens.map(p => h('tr', {class: p.ativo ? '' : 'inativa'},
                    h('td', {}, h('strong', {text: p.nome})),
                    h('td', {class: 'num', text: moeda(p.custo_hora)}),
                    h('td', {}, badgeSituacaoAtivo(p.ativo)),
                    escrita ? h('td', {class: 'acoes'},
                        botaoEditar(`Editar perfil ${p.nome}`, () => editar(p)),
                        botaoExcluir(`Excluir perfil ${p.nome}`, () => excluir(p))) : null))))));
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
            const form = h('form', {class: 'formulario form-cap', on: {submit: async evento => {
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
                h('h2', {}, icone(p ? 'pencil' : 'plus'), p ? 'Editar perfil' : 'Novo perfil'),
                campo('Nome (ex.: Analista)', nome), campo('Custo por hora (R$)', custo),
                p ? h('label', {class: 'campo-check'}, ativo, ' Ativo (inativos não aparecem como opção)') : null,
                h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar'),
                    h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Salvar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            nome.focus();
        }

        container.replaceChildren(
            h('div', {class: 'barra-acoes'},
                h('p', {class: 'ajuda-pagina'}, icone('info', {classe: 'icone-sm'}), 'Mudar o custo/hora de um perfil não reescreve iniciativas existentes.'),
                h('div', {class: 'acoes'}, escrita ? botaoNovo('Novo perfil', () => editar()) : null)),
            formulario, lista);
        await carregar();
    }
};
