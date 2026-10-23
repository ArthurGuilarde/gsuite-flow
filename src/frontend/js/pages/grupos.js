import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, toast, tratarErro} from '../ui.js';

export const grupos = {
    titulo: 'Grupos',
    subtitulo: 'Equipes e frentes de trabalho classificadas como BUILD ou RUN',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            const itens = await get('/api/v1/grupos', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio('Nenhum grupo cadastrado',
                    escrita ? 'Crie um grupo ou use os grupos padrão para começar.' : 'Peça a quem tem permissão de edição para criar os grupos.'));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Grupo', 'Categoria', 'Cor', 'Situação', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(g => {
                    const amostra = h('span', {class: 'amostra', 'aria-hidden': 'true'});
                    amostra.style.backgroundColor = g.cor;
                    return h('tr', {},
                        h('td', {}, `${g.icone} ${g.nome} `, g.sistema ? h('span', {class: 'badge', text: 'sistema'}) : null),
                        h('td', {}, h('span', {class: `badge badge-${g.categoria.toLowerCase()}`, text: g.categoria})),
                        h('td', {}, amostra, ` ${g.cor}`),
                        h('td', {text: g.ativo ? 'Ativo' : 'Inativo'}),
                        escrita ? h('td', {class: 'acoes'},
                            h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editar(g)}}, 'Editar'),
                            h('button', {type: 'button', class: 'perigo pequeno', disabled: g.sistema, title: g.sistema ? 'Grupo de sistema não pode ser excluído' : null, on: {click: () => excluir(g)}}, 'Excluir')) : null);
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
            const icone = h('input', {type: 'text', maxLength: 16, value: g?.icone ?? '📋'});
            const cor = h('input', {type: 'color', value: g?.cor ?? '#64748B'});
            const ativo = h('input', {type: 'checkbox', checked: g ? g.ativo : true});
            if (g?.sistema) { nome.disabled = true; categoria.disabled = true; ativo.disabled = true; }
            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {nome: nome.value.trim(), categoria: categoria.value, icone: icone.value.trim() || '📋', cor: cor.value};
                try {
                    if (g) await patch(`/api/v1/grupos/${g.id}`, {...corpo, ativo: ativo.checked});
                    else await post('/api/v1/grupos', corpo);
                    formulario.replaceChildren();
                    toast(g ? 'Grupo atualizado.' : 'Grupo criado.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {text: g ? 'Editar grupo' : 'Novo grupo'}),
                campo('Nome', nome), campo('Categoria', categoria), campo('Ícone', icone), campo('Cor', cor),
                g ? h('label', {class: 'campo-check'}, ativo, ' Ativo (inativos não entram no painel)') : null,
                g?.sistema ? h('p', {class: 'texto-suave', text: 'Grupo de sistema: nome, categoria e situação não podem ser alterados.'}) : null,
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar')));
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
                    h('button', {type: 'button', on: {click: () => editar()}}, 'Novo grupo'),
                    h('button', {type: 'button', class: 'secundario', on: {click: criarPadrao}}, 'Criar grupos padrão'))) : null,
            formulario, lista);
        await carregar();
    }
};
