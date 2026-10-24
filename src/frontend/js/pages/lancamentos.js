import {get, post, patch, put, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, icone, numero, toast, tratarErro} from '../ui.js';
import {botaoEditar, botaoExcluir, botaoNovo, cabecalhoTabela, tileGrupo} from './capacidade-comum.js';

export const lancamentos = {
    titulo: 'Lançamentos',
    subtitulo: 'Quantidade de itens abertos e resolvidos por grupo e semana',
    async render(container, signal) {
        const escrita = podeEscrever();
        const [listaGrupos, listaSemanas] = await Promise.all([
            get('/api/v1/grupos', undefined, signal), get('/api/v1/semanas', undefined, signal)]);
        if (!listaGrupos.length || !listaSemanas.length) {
            container.replaceChildren(estadoVazio('Cadastre grupos e semanas primeiro',
                'Os lançamentos combinam um grupo com uma semana.',
                h('a', {class: 'botao', href: '#/config/grupos', text: 'Grupos'}),
                h('a', {class: 'botao secundario', href: '#/config/semanas', text: 'Semanas'})));
            return;
        }
        const opcoes = (itens, rotulo) => itens.map(i => h('option', {value: i.id, text: rotulo(i)}));
        const filtroGrupo = h('select', {}, h('option', {value: '', text: 'Todos os grupos'}), opcoes(listaGrupos, g => `${g.icone} ${g.nome}`));
        const filtroSemana = h('select', {}, h('option', {value: '', text: 'Todas as semanas'}), opcoes(listaSemanas, s => s.identificacao));
        filtroSemana.value = listaSemanas[0].id;
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            if (!lista.firstChild) lista.replaceChildren(carregando(2));
            const itens = await get('/api/v1/lancamentos', {grupo_id: filtroGrupo.value, semana_id: filtroSemana.value}, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Nenhum lançamento', icone: 'list-checks'},
                    escrita ? 'Use "Inicializar semana" para criar os lançamentos zerados de todos os grupos.' : 'Não há lançamentos para este filtro.',
                    escrita ? h('button', {type: 'button', on: {click: inicializar}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Inicializar semana') : null));
                return;
            }
            const soma = status => itens.filter(l => l.status === status).reduce((t, l) => t + l.quantidade, 0);
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                cabecalhoTabela(['Semana', 'Grupo', 'Status', 'Qtd.', 'Observação'], escrita, ['Qtd.']),
                h('tbody', {}, itens.map(l => h('tr', {},
                    h('td', {text: l.semana_identificacao}),
                    h('td', {}, h('span', {class: 'celula-grupo'}, tileGrupo(l.grupo_icone, l.grupo_cor), l.grupo_nome)),
                    h('td', {}, h('span', {class: `badge badge-ponto badge-${l.status.toLowerCase()}`, text: l.status === 'ABERTO' ? 'Aberto' : 'Resolvido'})),
                    h('td', {class: 'num', text: numero(l.quantidade)}),
                    h('td', {class: 'col-obs', text: l.observacao ?? '—'}),
                    escrita ? h('td', {class: 'acoes'},
                        botaoEditar(`Editar lançamento de ${l.grupo_nome}`, () => editar(l)),
                        botaoExcluir(`Excluir lançamento de ${l.grupo_nome}`, () => excluir(l))) : null)))),
                h('div', {class: 'rodape-tabela'},
                    h('span', {}, `${numero(itens.length)} lançamentos`),
                    h('span', {}, 'Abertos: ', h('strong', {text: numero(soma('ABERTO'))})),
                    h('span', {}, 'Resolvidos: ', h('strong', {text: numero(soma('RESOLVIDO'))})))));
        }

        async function recarregar() {
            try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); }
        }

        async function excluir(l) {
            if (!await confirmar(`Excluir o lançamento ${l.status === 'ABERTO' ? 'aberto' : 'resolvido'} de "${l.grupo_nome}" em ${l.semana_identificacao}?`, 'Excluir')) return;
            try { await del(`/api/v1/lancamentos/${l.id}`); toast('Lançamento excluído.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function mostrar(titulo, form) {
            formulario.replaceChildren(h('section', {class: 'cartao'}, h('div', {class: 'cartao-topo'}, h('h2', {}, icone('pencil'), titulo)), form));
            form.querySelector('select, input')?.focus();
        }
        const cancelar = () => h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar');
        const salvar = texto => h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), texto);
        const inteiro = (valor = 0) => h('input', {type: 'number', min: 0, step: 1, required: true, value: String(valor)});

        function editar(l = null) {
            const grupo = h('select', {required: true}, opcoes(listaGrupos, g => `${g.icone} ${g.nome}`));
            const semana = h('select', {required: true}, opcoes(listaSemanas, s => s.identificacao));
            grupo.value = (l?.grupo_id ?? filtroGrupo.value) || listaGrupos[0].id;
            semana.value = (l?.semana_id ?? filtroSemana.value) || listaSemanas[0].id;
            const status = h('select', {}, h('option', {value: 'ABERTO', text: 'Aberto'}), h('option', {value: 'RESOLVIDO', text: 'Resolvido'}));
            status.value = l?.status ?? 'ABERTO';
            const quantidade = inteiro(l?.quantidade ?? 0);
            const obs = h('textarea', {rows: 2, maxLength: 1000}, l?.observacao ?? '');
            mostrar(l ? 'Editar lançamento' : 'Novo lançamento', h('form', {class: 'formulario form-cap', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {grupo_id: grupo.value, semana_id: semana.value, status: status.value, quantidade: Number(quantidade.value), observacao: obs.value.trim() || null};
                try {
                    if (l) await patch(`/api/v1/lancamentos/${l.id}`, corpo); else await post('/api/v1/lancamentos', corpo);
                    formulario.replaceChildren();
                    toast('Lançamento salvo.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                campo('Grupo', grupo), campo('Semana', semana), campo('Status', status), campo('Quantidade', quantidade), campo('Observação', obs),
                h('div', {class: 'acoes'}, cancelar(), salvar('Salvar'))));
        }

        function par() {
            const grupo = h('select', {required: true}, opcoes(listaGrupos, g => `${g.icone} ${g.nome}`));
            const semana = h('select', {required: true}, opcoes(listaSemanas, s => s.identificacao));
            grupo.value = filtroGrupo.value || listaGrupos[0].id;
            semana.value = filtroSemana.value || listaSemanas[0].id;
            const aberto = inteiro(), resolvido = inteiro();
            const obsA = h('input', {type: 'text', maxLength: 1000}), obsR = h('input', {type: 'text', maxLength: 1000});
            mostrar('Lançamento rápido em par', h('form', {class: 'formulario form-cap', on: {submit: async evento => {
                evento.preventDefault();
                try {
                    await put('/api/v1/lancamentos/par', {grupo_id: grupo.value, semana_id: semana.value,
                        qtd_aberto: Number(aberto.value), qtd_resolvido: Number(resolvido.value),
                        obs_aberto: obsA.value.trim(), obs_resolvido: obsR.value.trim()});
                    formulario.replaceChildren();
                    toast('Par de lançamentos salvo.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                campo('Grupo', grupo), campo('Semana', semana),
                campo('Abertos', aberto), campo('Observação (abertos)', obsA),
                campo('Resolvidos', resolvido), campo('Observação (resolvidos)', obsR),
                h('div', {class: 'acoes'}, cancelar(), salvar('Salvar par'))));
        }

        async function inicializar() {
            if (!filtroSemana.value) { toast('Selecione uma semana para inicializar.', 'error'); return; }
            const semana = listaSemanas.find(s => s.id === filtroSemana.value);
            if (!await confirmar(`Criar lançamentos zerados (aberto e resolvido) de todos os grupos na semana "${semana.identificacao}"? Os que já existem são mantidos.`, 'Inicializar')) return;
            try {
                const r = await post('/api/v1/lancamentos/inicializar', {semana_id: filtroSemana.value});
                toast(`Semana inicializada: ${r.created} criados, ${r.skipped} já existiam.`, 'success');
                await recarregar();
            } catch (erro) { tratarErro(erro); }
        }

        filtroGrupo.addEventListener('change', recarregar);
        filtroSemana.addEventListener('change', recarregar);
        container.replaceChildren(
            h('div', {class: 'barra-acoes'},
                h('div', {class: 'filtros'}, campo('Grupo', filtroGrupo), campo('Semana', filtroSemana)),
                escrita ? h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: inicializar}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Inicializar semana'),
                    h('button', {type: 'button', class: 'secundario', on: {click: par}}, icone('list-checks', {classe: 'icone-sm'}), 'Lançamento em par'),
                    botaoNovo('Novo lançamento', () => editar())) : null),
            formulario, lista);
        await carregar();
    }
};
