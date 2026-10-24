import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, icone, competencia, data, hojeLocal, mesAtual, moeda, toast, tratarErro} from '../ui.js';
import {botaoEditar, botaoExcluir, cabecalho, nota, opcao} from './finops-comum.js';
import {
    CATEGORIAS_SUGERIDAS, JANELA_PADRAO, ROTULO_TIPO_CUSTO, STATUS_DESPESA, STATUS_EDITAVEIS, TIPOS_CUSTO, URL_INICIATIVAS,
    abrirDialogo, badgeDespesa, intervaloJanela, linhaValor, moedaMes, numeroOuNulo, seloOrigem, situacaoRenovacao, textoOuNulo
} from './despesas-comum.js';

const ROTULOS_STATUS_EDITAVEIS = STATUS_EDITAVEIS.map(s => [s, STATUS_DESPESA[s][0]]);

// Prévia de saving (por mês e na janela) para cancelar/renegociar. `saving` é o valor mensal eliminado.
function previaSaving(saving, mes, meses, extra) {
    const bloco = h('div', {class: 'previa-saving', 'aria-live': 'polite'});
    function atualizar(valor, mesAcao, janela) {
        const ok = valor > 0 && mesAcao && janela >= 1;
        bloco.replaceChildren(...[
            h('h3', {text: 'Impacto no FinOps'}),
            ok ? linhaValor('Saving por mês', moedaMes(valor), 'linha-destaque') : linhaValor('Saving por mês', moeda(0)),
            ok ? linhaValor(`Saving na janela de ${janela} ${janela === 1 ? 'mês' : 'meses'}`, moeda(valor * janela)) : null,
            ok ? linhaValor('Período', intervaloJanela(mesAcao, janela)) : null,
            ok ? linhaValor('Por ano (run-rate)', moeda(valor * 12)) : null,
            h('p', {class: 'texto-suave pequeno-texto', text: ok
                ? 'Será criada uma iniciativa de otimização de custo vinculada a esta despesa; depois da janela o valor vira novo normal.'
                : 'Sem saving mensal: nenhuma iniciativa será criada.'}),
            extra ? h('p', {class: 'texto-suave pequeno-texto', text: extra}) : null].filter(Boolean));
    }
    atualizar(saving, mes, meses);
    return {bloco, atualizar};
}

function notaFatura(d) {
    return d.origem_custo === 'FATURA'
        ? `O custo considerado hoje (${moedaMes(d.custo_mensal_considerado)}) vem da fatura; o saving usa o valor contratado de ${moedaMes(d.valor)}.`
        : null;
}

export const despesasInventario = {
    titulo: 'Inventário de despesas',
    subtitulo: 'Contratos, assinaturas e custos pontuais com status de auditoria',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});
        const avisoRenovacao = h('div', {});
        let fontes = [], itens = [];
        const fStatus = h('select', {id: 'dsp-status'}, opcao('', 'Todos os status'), Object.entries(STATUS_DESPESA).map(([v, [t]]) => opcao(v, t)));
        const fCategoria = h('select', {id: 'dsp-categoria'}, opcao('', 'Todas as categorias'));
        const fBusca = h('input', {type: 'search', id: 'dsp-busca', placeholder: 'Nome ou fornecedor'});

        function atualizarCategorias() {
            const atual = fCategoria.value;
            const nomes = [...new Set(itens.map(i => i.categoria))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
            fCategoria.replaceChildren(opcao('', 'Todas as categorias'), ...nomes.map(n => opcao(n)));
            fCategoria.value = nomes.includes(atual) ? atual : '';
        }

        async function carregar() {
            itens = await get('/api/v1/despesas', {referencia: mesAtual(), hoje: hojeLocal()}, signal);
            if (signal.aborted) return;
            atualizarCategorias();
            desenhar();
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        function filtrar() {
            const busca = fBusca.value.trim().toLocaleLowerCase('pt-BR');
            return itens.filter(i => (!fStatus.value || i.status_auditoria === fStatus.value)
                && (!fCategoria.value || i.categoria === fCategoria.value)
                && (!busca || `${i.nome} ${i.fornecedor ?? ''}`.toLocaleLowerCase('pt-BR').includes(busca)));
        }

        function desenhar() {
            const urgentes = itens.filter(i => situacaoRenovacao(i)?.classe === 'ren-urgente');
            avisoRenovacao.replaceChildren(...(urgentes.length ? [
                h('p', {class: 'aviso-renovacao', role: 'status'}, icone('triangle-alert'), h('span', {}, h('strong', {text: `${urgentes.length} ${urgentes.length === 1 ? 'contrato renova' : 'contratos renovam'} em até 30 dias: `}),
                    urgentes.map(u => u.nome).join(', '), '. ', h('a', {href: '#/despesas', text: 'Ver alertas no painel'})))] : []));
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Nenhuma despesa cadastrada', icone: 'package'}, escrita ? 'Cadastre os contratos e assinaturas para auditar, acompanhar renovações e capturar saving.' : 'Peça a quem tem permissão de edição para cadastrar as despesas.',
                    escrita ? h('button', {type: 'button', on: {click: () => editar()}}, icone('plus', {classe: 'icone-sm'}), 'Nova despesa') : null));
                return;
            }
            const visiveis = filtrar();
            if (!visiveis.length) { lista.replaceChildren(estadoVazio({titulo: 'Nada encontrado', icone: 'search'}, 'Nenhuma despesa corresponde aos filtros.')); return; }
            const total = visiveis.filter(i => i.tipo_custo === 'RECORRENTE_MENSAL' && i.status_auditoria !== 'CANCELADO').reduce((s, i) => s + i.custo_mensal_considerado, 0);
            lista.replaceChildren(
                h('p', {class: 'texto-suave pequeno-texto', text: `${visiveis.length} ${visiveis.length === 1 ? 'despesa' : 'despesas'} · recorrente mensal ativo na seleção: ${moedaMes(total)}`}),
                h('div', {class: 'tabela-wrap'}, h('table', {class: 'tabela-despesas tabela-fin'},
                    cabecalho(['Despesa', 'Status', ['Custo considerado', true], ['Custo anual', true], 'Renovação', escrita ? ['Ações', true] : null]),
                    h('tbody', {}, visiveis.map(linha)))));
        }

        function linha(d) {
            const ren = situacaoRenovacao(d);
            const pontual = d.tipo_custo === 'PONTUAL';
            const ativa = d.status_auditoria !== 'CANCELADO' && d.status_auditoria !== 'RENEGOCIADO';
            return h('tr', {class: d.status_auditoria === 'CANCELADO' ? 'inativa' : ''},
                h('td', {},
                    h('span', {class: 'item-titulo', text: d.nome}),
                    h('div', {class: 'texto-suave pequeno-texto', text: [d.fornecedor, d.categoria, ROTULO_TIPO_CUSTO[d.tipo_custo]].filter(Boolean).join(' · ')}),
                    d.fonte_nome ? h('div', {class: 'texto-suave pequeno-texto', text: `Fonte de custo: ${d.fonte_nome}`}) : null,
                    d.iniciativas?.length ? h('ul', {class: 'iniciativas-vinculadas'}, d.iniciativas.map(i => h('li', {},
                        h('a', {href: URL_INICIATIVAS, text: i.titulo}), ` · ${STATUS_DESPESA_INICIATIVA[i.status] ?? i.status} · ${moedaMes(i.valor_mensal)}`))) : null),
                h('td', {}, badgeDespesa(d.status_auditoria),
                    d.mes_acao ? h('div', {class: 'texto-suave pequeno-texto', text: `desde ${competencia(d.mes_acao)}`}) : null),
                h('td', {class: 'num'},
                    pontual ? [h('strong', {text: moeda(d.valor)}), h('div', {class: 'texto-suave pequeno-texto', text: 'pontual'})]
                        : [h('strong', {text: moedaMes(d.custo_mensal_considerado)}), h('div', {}, seloOrigem(d)),
                            d.valor_anterior !== null && d.valor_anterior !== undefined ? h('div', {class: 'texto-suave pequeno-texto', text: `antes ${moedaMes(d.valor_anterior)}`}) : null]),
                h('td', {class: 'num', text: moeda(d.custo_anual)}),
                h('td', {}, d.data_renovacao ? [data(d.data_renovacao), ren ? h('div', {}, h('span', {class: `badge ${ren.classe}`, text: ren.texto})) : null] : h('span', {class: 'texto-suave', text: '—'})),
                escrita ? h('td', {class: 'acoes'}, h('div', {class: 'acoes'},
                    ativa ? [
                        !pontual ? h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => renegociar(d)}}, icone('badge-dollar-sign', {classe: 'icone-sm'}), 'Renegociar') : null,
                        h('button', {type: 'button', class: 'secundario perigo pequeno', on: {click: () => cancelar(d)}}, icone('x', {classe: 'icone-sm'}), 'Cancelar')]
                        : h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => reverter(d)}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Reverter'),
                    botaoEditar(`despesa ${d.nome}`, () => editar(d)),
                    botaoExcluir(`despesa ${d.nome}`, () => excluir(d)))) : null);
        }

        async function excluir(d) {
            if (!await confirmar(`Excluir a despesa "${d.nome}"? Se houver iniciativa vinculada, a exclusão é recusada.`, 'Excluir')) return;
            try { await del(`/api/v1/despesas/${d.id}`); toast('Despesa excluída.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function cancelar(d) {
            const pontual = d.tipo_custo === 'PONTUAL';
            const mes = h('input', {type: 'month', required: true, value: mesAtual()});
            const janelaMeses = h('input', {type: 'number', required: true, min: 1, max: 60, step: 1, value: JANELA_PADRAO});
            const obs = h('textarea', {rows: 2});
            const saving = !pontual && d.valor > 0 ? d.valor : 0;
            const previa = previaSaving(saving, mes.value, Number(janelaMeses.value), notaFatura(d));
            const refrescar = () => previa.atualizar(saving, mes.value, Math.round(Number(janelaMeses.value)));
            mes.addEventListener('input', refrescar);
            janelaMeses.addEventListener('input', refrescar);
            const corpo = h('div', {class: 'formulario-modal'},
                h('p', {}, `Cancelar "${d.nome}"? O custo contratual cai para ${moeda(0)} a partir do mês informado.`),
                campo('Mês do cancelamento', mes),
                !pontual ? campo('Janela do saving (meses, 1–60)', janelaMeses) : null,
                campo('Observação (opcional)', obs),
                pontual ? h('p', {class: 'texto-suave pequeno-texto', text: 'Despesa pontual: apenas muda o status, sem saving mensal.'}) : previa.bloco);
            abrirDialogo('Cancelar despesa', corpo, 'Confirmar cancelamento', async () => {
                const res = await post(`/api/v1/despesas/${d.id}/cancelar`, {mes: mes.value, janela_meses: pontual ? JANELA_PADRAO : Math.round(Number(janelaMeses.value)), observacao: textoOuNulo(obs.value)});
                toast(res.iniciativa ? `Despesa cancelada. Saving de ${moedaMes(res.iniciativa.valor_mensal)} registrado no FinOps.` : 'Despesa cancelada.', 'success');
                await recarregar();
            }, true);
        }

        function renegociar(d) {
            const mes = h('input', {type: 'month', required: true, value: mesAtual()});
            const janelaMeses = h('input', {type: 'number', required: true, min: 1, max: 60, step: 1, value: JANELA_PADRAO});
            const novo = h('input', {type: 'number', required: true, min: 0, step: 0.01, max: Math.max(0, d.valor - 0.01), placeholder: `menor que ${d.valor}`});
            const obs = h('textarea', {rows: 2});
            const aviso = h('p', {class: 'erro pequeno-texto', role: 'alert'});
            const previa = previaSaving(0, mes.value, Number(janelaMeses.value), notaFatura(d));
            let botao = null;
            const refrescar = () => {
                const valorNovo = novo.value === '' ? null : Number(novo.value);
                const valido = valorNovo !== null && valorNovo >= 0 && valorNovo < d.valor;
                aviso.textContent = valorNovo !== null && !valido ? `O novo valor deve ser menor que o atual (${moedaMes(d.valor)}).` : '';
                previa.atualizar(valido ? d.valor - valorNovo : 0, mes.value, Math.round(Number(janelaMeses.value)));
                if (botao) botao.disabled = !valido;
            };
            for (const c of [novo, mes, janelaMeses]) c.addEventListener('input', refrescar);
            const corpo = h('div', {class: 'formulario-modal'},
                h('p', {}, `Valor atual de "${d.nome}": ${moedaMes(d.valor)}.`),
                campo('Novo valor mensal (R$)', novo), aviso,
                campo('Mês da renegociação', mes), campo('Janela do saving (meses, 1–60)', janelaMeses),
                campo('Observação (opcional)', obs), previa.bloco);
            const {enviar} = abrirDialogo('Renegociar despesa', corpo, 'Confirmar renegociação', async () => {
                const res = await post(`/api/v1/despesas/${d.id}/renegociar`, {novo_valor: Number(novo.value), mes: mes.value, janela_meses: Math.round(Number(janelaMeses.value)), observacao: textoOuNulo(obs.value)});
                toast(`Despesa renegociada. Saving de ${moedaMes(res.iniciativa.valor_mensal)} registrado no FinOps.`, 'success');
                await recarregar();
            });
            botao = enviar;
            botao.disabled = true;
            novo.focus();
        }

        function reverter(d) {
            const conversoes = (d.iniciativas ?? []).filter(i => i.conversao_despesa);
            const novoStatus = h('select', {}, ROTULOS_STATUS_EDITAVEIS.map(([v, t]) => opcao(v, t)));
            novoStatus.value = 'EM_REVISAO';
            const efeitos = [
                conversoes.length ? `Apaga ${conversoes.length === 1 ? 'a iniciativa' : 'as iniciativas'} do FinOps: ${conversoes.map(i => `"${i.titulo}" (${moedaMes(i.valor_mensal)})`).join(', ')}.` : 'Nenhuma iniciativa de conversão será apagada.',
                d.status_auditoria === 'RENEGOCIADO' && d.valor_anterior !== null ? `Restaura o valor de ${moedaMes(d.valor)} para ${moedaMes(d.valor_anterior)}.` : null,
                'Limpa o mês da ação e aplica o novo status.'].filter(Boolean);
            const corpo = h('div', {class: 'formulario-modal'},
                h('p', {}, `Reverter ${d.status_auditoria === 'CANCELADO' ? 'o cancelamento' : 'a renegociação'} de "${d.nome}"?`),
                h('ul', {class: 'efeitos'}, efeitos.map(t => h('li', {text: t}))),
                campo('Novo status', novoStatus));
            abrirDialogo('Reverter ação', corpo, 'Reverter', async () => {
                await post(`/api/v1/despesas/${d.id}/reverter`, {novo_status: novoStatus.value});
                toast('Ação revertida; o saving deixou de contar.', 'success');
                await recarregar();
            }, true);
        }

        function editar(d = null) {
            const travada = d && (d.status_auditoria === 'CANCELADO' || d.status_auditoria === 'RENEGOCIADO');
            const nome = h('input', {type: 'text', required: true, maxLength: 160, value: d?.nome ?? ''});
            const fornecedor = h('input', {type: 'text', maxLength: 120, value: d?.fornecedor ?? ''});
            const categoria = h('input', {type: 'text', required: true, maxLength: 60, value: d?.categoria ?? '', list: 'dsp-categorias', autocomplete: 'off'});
            const lista_ = h('datalist', {id: 'dsp-categorias'}, CATEGORIAS_SUGERIDAS.map(c => h('option', {value: c})));
            const tipo = h('select', {disabled: travada}, TIPOS_CUSTO.map(([v, t]) => opcao(v, t)));
            tipo.value = d?.tipo_custo ?? 'RECORRENTE_MENSAL';
            const valor = h('input', {type: 'number', required: true, min: 0, step: 0.01, value: d?.valor ?? '', disabled: travada});
            const rotuloValor = h('span', {});
            const status = h('select', {disabled: travada});
            status.append(...(travada ? [opcao(d.status_auditoria, STATUS_DESPESA[d.status_auditoria][0])] : ROTULOS_STATUS_EDITAVEIS.map(([v, t]) => opcao(v, t))));
            status.value = d?.status_auditoria ?? 'EM_REVISAO';
            const inicio = h('input', {type: 'date', value: d?.data_inicio ?? ''});
            const renovacao = h('input', {type: 'date', value: d?.data_renovacao ?? ''});
            const responsavel = h('input', {type: 'text', maxLength: 120, value: d?.responsavel ?? ''});
            const fonte = h('select', {}, opcao('', 'Nenhuma (usar valor contratado)'), fontes.filter(f => f.ativo || f.id === d?.fonte_id).map(f => opcao(f.id, f.nome)));
            fonte.value = d?.fonte_id ?? '';
            const observacoes = h('textarea', {rows: 2});
            observacoes.value = d?.observacoes ?? '';
            const dicaValor = h('p', {class: 'texto-suave pequeno-texto'});
            const ajustar = () => {
                const pontual = tipo.value === 'PONTUAL';
                rotuloValor.textContent = pontual ? 'Valor total (R$)' : 'Valor mensal (R$)';
                dicaValor.textContent = pontual ? 'Pontual: conta uma vez, no mês da data de início.' : 'Recorrente: com fonte de custo ligada, o custo considerado vem do realizado das faturas.';
            };
            tipo.addEventListener('change', ajustar);
            ajustar();
            const form = h('form', {class: 'formulario-despesa', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {
                    nome: nome.value.trim(), fornecedor: textoOuNulo(fornecedor.value), categoria: categoria.value.trim(),
                    data_inicio: inicio.value || null, data_renovacao: renovacao.value || null,
                    responsavel: textoOuNulo(responsavel.value), observacoes: textoOuNulo(observacoes.value), fonte_id: fonte.value || null
                };
                if (!travada) Object.assign(corpo, {tipo_custo: tipo.value, valor: numeroOuNulo(valor.value), status_auditoria: status.value});
                try {
                    if (d) await patch(`/api/v1/despesas/${d.id}`, corpo); else await post('/api/v1/despesas', corpo);
                    formulario.replaceChildren();
                    toast(d ? 'Despesa atualizada.' : 'Despesa criada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
            h('h2', {text: d ? 'Editar despesa' : 'Nova despesa'}),
            travada ? nota(`Despesa ${STATUS_DESPESA[d.status_auditoria][0].toLowerCase()}: valor, tipo e status só mudam depois de reverter a ação.`) : null,
            h('div', {class: 'formulario'},
                campo('Nome', nome), campo('Fornecedor', fornecedor), h('label', {class: 'campo'}, h('span', {text: 'Categoria'}), categoria, lista_),
                campo('Tipo de custo', tipo), h('label', {class: 'campo'}, rotuloValor, valor), campo('Status de auditoria', status),
                campo('Data de início', inicio), campo('Data de renovação', renovacao), campo('Responsável', responsavel),
                campo('Fonte de custo (opcional)', fonte)),
            dicaValor,
            h('div', {class: 'formulario'}, campo('Observações', observacoes)),
            h('div', {class: 'acoes'},
                h('button', {type: 'button', class: 'secundario', on: {click: () => formulario.replaceChildren()}}, 'Cancelar'),
                h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Salvar')));
            formulario.replaceChildren(h('section', {class: 'cartao'}, form));
            nome.focus();
            formulario.scrollIntoView({block: 'nearest'});
        }

        for (const c of [fStatus, fCategoria]) c.addEventListener('change', desenhar);
        fBusca.addEventListener('input', desenhar);
        container.replaceChildren(
            avisoRenovacao,
            h('div', {class: 'barra-acoes'},
                h('div', {class: 'acoes'}, escrita ? h('button', {type: 'button', on: {click: () => editar()}}, icone('plus', {classe: 'icone-sm'}), 'Nova despesa') : null),
                h('div', {class: 'filtros'}, campo('Status', fStatus), campo('Categoria', fCategoria), campo('Busca', fBusca))),
            formulario, lista);
        lista.replaceChildren(carregando(2));
        fontes = await get('/api/v1/finops/fontes', undefined, signal).catch(() => []);
        await carregar();
    }
};

const STATUS_DESPESA_INICIATIVA = {PLANEJADA: 'planejada', EM_SAVING: 'em saving', NOVO_NORMAL: 'novo normal', ENCERRADA: 'encerrada'};
