import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, icone, toast, tratarErro} from '../ui.js';
import {badgeSituacaoAtivo, botaoEditar, botaoExcluir, botaoNovo, cabecalhoTabela, tileGrupo} from './capacidade-comum.js';

export const grupos = {
    titulo: 'Grupos',
    subtitulo: 'Equipes e frentes de trabalho classificadas como BUILD ou RUN',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            if (!lista.firstChild) lista.replaceChildren(carregando(2));
            const itens = await get('/api/v1/grupos', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Nenhum grupo cadastrado', icone: 'users'},
                    escrita ? 'Crie um grupo ou use os grupos padrão para começar.' : 'Peça a quem tem permissão de edição para criar os grupos.',
                    escrita ? h('button', {type: 'button', on: {click: criarPadrao}}, icone('plus', {classe: 'icone-sm'}), 'Criar grupos padrão') : null,
                    escrita ? h('button', {type: 'button', class: 'secundario', on: {click: () => editar()}}, 'Novo grupo') : null));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                cabecalhoTabela(['Grupo', 'Categoria', 'Cor', 'Situação'], escrita),
                h('tbody', {}, itens.map(g => {
                    const amostra = h('span', {class: 'amostra', 'aria-hidden': 'true'});
                    amostra.style.backgroundColor = g.cor;
                    return h('tr', {class: g.ativo ? '' : 'inativa'},
                        h('td', {}, h('span', {class: 'celula-grupo'}, tileGrupo(g.icone, g.cor), g.nome, g.sistema ? h('span', {class: 'badge', text: 'sistema'}) : null)),
                        h('td', {}, h('span', {class: `badge badge-${g.categoria.toLowerCase()}`, text: g.categoria})),
                        h('td', {}, h('span', {class: 'cor-valor'}, amostra, g.cor.toUpperCase())),
                        h('td', {}, badgeSituacaoAtivo(g.ativo)),
                        escrita ? h('td', {class: 'acoes'},
                            botaoEditar(`Editar grupo ${g.nome}`, () => editar(g)),
                            botaoExcluir(`Excluir grupo ${g.nome}`, () => excluir(g), {desabilitado: g.sistema, dica: g.sistema ? 'Grupo de sistema não pode ser excluído' : null})) : null);
                })))));
        }

        async function recarregar() {
            try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); }
        }

        async function excluir(g) {
            if (!await confirmar(`Excluir o grupo "${g.nome}"? Os lançamentos dele também serão removidos.`, 'Excluir')) return;
            try { await del(`/api/v1/grupos/${g.id}`); toast('Grupo excluído.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function editar(g = null) {
            const nome = h('input', {type: 'text', required: true, maxLength: 120, value: g?.nome ?? ''});
            const categoria = h('select', {}, h('option', {value: 'BUILD', text: 'BUILD'}), h('option', {value: 'RUN', text: 'RUN'}));
            categoria.value = g?.categoria ?? 'BUILD';
            const iconeCampo = h('input', {type: 'text', maxLength: 16, value: g?.icone ?? '📋'});
            const cor = h('input', {type: 'color', value: g?.cor ?? '#64748B'});
            const ativo = h('input', {type: 'checkbox', checked: g ? g.ativo : true});
            if (g?.sistema) { nome.disabled = true; categoria.disabled = true; ativo.disabled = true; }
            const form = h('form', {class: 'formulario form-cap', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {nome: nome.value.trim(), categoria: categoria.value, icone: iconeCampo.value.trim() || '📋', cor: cor.value};
                try {
                    if (g) await patch(`/api/v1/grupos/${g.id}`, {...corpo, ativo: ativo.checked});
                    else await post('/api/v1/grupos', corpo);
                    formulario.replaceChildren();
                    toast(g ? 'Grupo atualizado.' : 'Grupo criado.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {}, icone(g ? 'pencil' : 'plus'), g ? 'Editar grupo' : 'Novo grupo'),
                campo('Nome', nome), campo('Categoria', categoria), campo('Ícone (emoji ou símbolo)', iconeCampo), campo('Cor', cor),
                g ? h('label', {class: 'campo-check'}, ativo, ' Ativo (inativos não entram no painel)') : null,
                g?.sistema ? h('p', {class: 'texto-suave', text: 'Grupo de sistema: nome, categoria e situação não podem ser alterados.'}) : null,
                h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar'),
                    h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Salvar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            nome.focus();
        }

        async function criarPadrao() {
            try {
                const r = await post('/api/v1/grupos/padrao');
                toast(`Grupos padrão: ${r.created} criados, ${r.skipped} já existiam.`, 'success');
                await recarregar();
            } catch (erro) { tratarErro(erro); }
        }

        container.replaceChildren(
            escrita ? h('div', {class: 'barra-acoes'},
                h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: criarPadrao}}, icone('list-checks', {classe: 'icone-sm'}), 'Criar grupos padrão'),
                    botaoNovo('Novo grupo', () => editar()))) : null,
            formulario, lista);
        await carregar();
    }
};
