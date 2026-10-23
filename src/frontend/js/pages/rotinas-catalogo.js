import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, data, minutos, toast, tratarErro} from '../ui.js';
import {DIAS, TIPOS, badgeAgendamento, badgeCategoria, tituloComLink} from './rotinas.js';

const PERIODOS = ['Manhã', 'Tarde', 'Integral'];
const opcao = (valor, texto = valor) => h('option', {value: valor, text: texto});

export const rotinasCatalogo = {
    titulo: 'Catálogo de rotinas',
    subtitulo: 'Rotinas recorrentes, agendamento e esforço estimado por ocorrência',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});

        async function carregar() {
            const itens = await get('/api/v1/rotinas', undefined, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio('Nenhuma rotina cadastrada',
                    escrita ? 'Crie uma rotina ou use as rotinas padrão para começar.' : 'Peça a quem tem permissão de edição para cadastrar as rotinas.'));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Rotina', 'Categoria', 'Agendamento', 'Esforço', 'Vigência', 'Situação', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(r => h('tr', {class: r.ativo ? '' : 'inativa'},
                    h('td', {}, tituloComLink(r.titulo, r.link_recurso), r.responsavel ? h('div', {class: 'texto-suave', text: r.responsavel}) : null),
                    h('td', {}, badgeCategoria(r.categoria)),
                    h('td', {}, badgeAgendamento(r)),
                    h('td', {text: minutos(r.esforco_estimado_min)}),
                    h('td', {text: `desde ${data(r.inicio_vigencia)}`}),
                    h('td', {}, h('span', {class: `badge ${r.ativo ? 'badge-resolvido' : ''}`, text: r.ativo ? 'Ativa' : 'Inativa'})),
                    escrita ? h('td', {class: 'acoes'},
                        h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editar(r)}}, 'Editar'),
                        h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => excluir(r)}}, 'Excluir')) : null))))));
        }

        async function recarregar() {
            try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); }
        }

        async function excluir(r) {
            if (!await confirmar(`Excluir a rotina "${r.titulo}"? O histórico de execuções dela também será removido.`, 'Excluir')) return;
            try { await del(`/api/v1/rotinas/${r.id}`); toast('Rotina excluída.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function editar(r = null) {
            const titulo = h('input', {type: 'text', required: true, maxLength: 200, value: r?.titulo ?? ''});
            const descricao = h('textarea', {rows: 2});
            descricao.value = r?.descricao ?? '';
            const categoria = h('select', {}, opcao('BUILD'), opcao('RUN'));
            categoria.value = r?.categoria ?? 'RUN';
            const responsavel = h('input', {type: 'text', maxLength: 120, value: r?.responsavel ?? ''});
            const link = h('input', {type: 'text', maxLength: 500, placeholder: 'https://…', value: r?.link_recurso ?? ''});
            const tipo = h('select', {}, TIPOS.map(([v, t]) => opcao(v, t)));
            tipo.value = r?.tipo_agendamento ?? 'SEMANAL';
            const diaSemana = h('select', {}, DIAS.map(d => opcao(d)));
            diaSemana.value = r?.dia_semana ?? 'Segunda';
            const periodo = h('select', {}, PERIODOS.map(p => opcao(p)));
            periodo.value = r?.periodo ?? 'Manhã';
            const diaMes = h('input', {type: 'number', min: 1, max: 31, step: 1, value: r?.dia_mes ?? ''});
            const esforco = h('input', {type: 'number', min: 0, max: 1440, step: 1, required: true, value: r?.esforco_estimado_min ?? 0});
            const vigencia = h('input', {type: 'date', value: r?.inicio_vigencia ?? ''});
            const ativo = h('input', {type: 'checkbox', checked: r ? r.ativo : true});

            const campoDiaSemana = campo('Dia da semana', diaSemana);
            const campoDiaMes = campo('Dia do mês', diaMes);
            function alternar() {
                const semanal = tipo.value === 'SEMANAL', fixo = tipo.value === 'MENSAL_DIA_FIXO';
                campoDiaSemana.hidden = !semanal;
                campoDiaMes.hidden = !fixo;
                diaSemana.required = semanal;
                diaMes.required = fixo;
            }
            tipo.addEventListener('change', alternar);
            alternar();

            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const url = link.value.trim();
                if (url && !/^https?:\/\//i.test(url)) { toast('O link do recurso deve começar com http:// ou https://.', 'error'); link.focus(); return; }
                const corpo = {
                    titulo: titulo.value.trim(), descricao: descricao.value.trim() || null, categoria: categoria.value,
                    responsavel: responsavel.value.trim() || null, link_recurso: url || null, tipo_agendamento: tipo.value,
                    dia_semana: tipo.value === 'SEMANAL' ? diaSemana.value : null,
                    periodo: periodo.value,
                    dia_mes: tipo.value === 'MENSAL_DIA_FIXO' ? Number(diaMes.value) : null,
                    esforco_estimado_min: Number(esforco.value || 0), ativo: ativo.checked
                };
                if (vigencia.value) corpo.inicio_vigencia = vigencia.value;
                try {
                    if (r) await patch(`/api/v1/rotinas/${r.id}`, corpo); else await post('/api/v1/rotinas', corpo);
                    formulario.replaceChildren();
                    toast(r ? 'Rotina atualizada.' : 'Rotina criada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {text: r ? 'Editar rotina' : 'Nova rotina'}),
                campo('Título', titulo), campo('Categoria', categoria), campo('Responsável', responsavel),
                campo('Tipo de agendamento', tipo), campoDiaSemana, campoDiaMes, campo('Período', periodo),
                campo('Esforço estimado por ocorrência (min)', esforco),
                campo('Início da vigência (padrão: hoje)', vigencia),
                campo('Link do recurso', link), campo('Descrição', descricao),
                h('label', {class: 'campo-check'}, ativo, ' Ativa (inativas só aparecem em semanas com execução registrada)'),
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            titulo.focus();
        }

        async function criarPadrao() {
            try {
                const r = await post('/api/v1/rotinas/padrao');
                toast(`Rotinas padrão: ${r.created} criadas, ${r.skipped} já existiam.`, 'success');
                await recarregar();
            } catch (erro) { tratarErro(erro); }
        }

        container.replaceChildren(
            h('div', {class: 'barra-acoes'},
                h('div', {class: 'acoes'},
                    escrita ? h('button', {type: 'button', on: {click: () => editar()}}, 'Nova rotina') : null,
                    escrita ? h('button', {type: 'button', class: 'secundario', on: {click: criarPadrao}}, 'Criar rotinas padrão') : null,
                    h('a', {class: 'botao secundario', href: '#/rotinas', text: 'Ir para o checklist'}))),
            formulario, lista);
        await carregar();
    }
};
