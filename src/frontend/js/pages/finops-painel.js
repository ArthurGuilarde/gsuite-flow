import {get} from '../api.js';
import {h, campo, carregando, estadoVazio, icone, mesAtual, moeda, competencia, decimal, numero, pct, tratarErro} from '../ui.js';
import {graficoSaving, graficoFaturas, legenda} from '../grafico.js';
import {REGRA_JANELA, ROTULO_TIPO, badgeStatus, badgeModo, cabecalho, janela, kpi, nota, textoPayback, variacao} from './finops-comum.js';

// Barra de proporção direto × horas do saving mensal em curso.
function proporcao(direto, horas) {
    const total = direto + horas;
    const a = h('div', {class: 'seg seg-direto'}), b = h('div', {class: 'seg seg-horas'});
    a.style.width = `${total > 0 ? (direto / total) * 100 : 0}%`;
    b.style.width = `${total > 0 ? (horas / total) * 100 : 0}%`;
    return h('div', {class: 'barra-empilhada', role: 'img', 'aria-label': `Direto ${moeda(direto)}, horas do time ${moeda(horas)}`}, a, b);
}

function cartaoEmCurso(k) {
    return h('section', {class: 'cartao destaque'},
        h('div', {class: 'cartao-topo'}, h('h2', {}, icone('trending-up'), 'Saving em curso por mês'), h('strong', {class: 'destaque-valor', text: moeda(k.saving_mensal_em_curso)})),
        proporcao(k.saving_direto_em_curso, k.saving_horas_em_curso),
        h('div', {class: 'duas-colunas'},
            h('div', {},
                h('span', {class: 'marca-cor marca-direto'}), h('strong', {text: ` ${moeda(k.saving_direto_em_curso)}/mês `}), 'economia direta',
                h('p', {class: 'texto-suave pequeno-texto', text: 'Dinheiro que deixa de sair de faturas e contratos.'})),
            h('div', {},
                h('span', {class: 'marca-cor marca-horas'}), h('strong', {text: ` ${moeda(k.saving_horas_em_curso)}/mês `}), 'horas do time convertidas',
                h('p', {class: 'texto-suave pequeno-texto', text: 'Capacidade liberada valorizada pelo custo/hora; não reduz a fatura, volta ao time.'}))));
}

function tabelaIniciativas(lista) {
    if (!lista.length) return h('p', {class: 'texto-suave vazio-inline', text: 'Nenhuma iniciativa cadastrada.'});
    return h('div', {class: 'tabela-wrap'}, h('table', {class: 'tabela-fin'},
        cabecalho(['Iniciativa', 'Status', 'Janela', ['Valor/mês', true], ['Saving no período', true], ['Saving na janela', true], ['Investimento', true], ['ROI', true], 'Payback']),
        h('tbody', {}, lista.map(i => h('tr', {class: i.status === 'ENCERRADA' || i.status === 'PLANEJADA' ? 'inativa' : ''},
            h('td', {}, h('a', {class: 'item-titulo', href: '#/finops/iniciativas', text: i.titulo}),
                h('div', {class: 'texto-suave pequeno-texto', text: `${ROTULO_TIPO[i.tipo] ?? i.tipo} · `}, badgeModo(i.modo_calculo))),
            h('td', {}, badgeStatus(i.status)),
            h('td', {text: janela(i.mes_inicio, i.fim_janela)}),
            h('td', {class: 'num', text: moeda(i.valor_mensal)}),
            h('td', {class: 'num', text: moeda(i.saving_periodo)}),
            h('td', {class: 'num', text: moeda(i.saving_janela)}),
            h('td', {class: 'num', text: i.investimento_total ? moeda(i.investimento_total) : '—'}),
            h('td', {class: 'num', text: i.roi_janela_pct === null ? '—' : pct(i.roi_janela_pct)}),
            h('td', {}, i.investimento_total ? `${textoPayback(i.payback_meses)}` : '—',
                i.investimento_total && i.payback_meses !== null ? h('div', {class: i.se_paga_na_janela ? 'var-boa pequeno-texto' : 'var-ruim pequeno-texto', text: i.se_paga_na_janela ? 'Se paga na janela' : 'Fora da janela'}) : null))))));
}

function blocoFonte(f) {
    const tem = f.serie.some(s => s.realizado !== null || s.orcado !== null);
    return h('details', {class: 'cartao fonte', open: tem},
        h('summary', {},
            h('strong', {text: f.nome}),
            h('span', {class: 'texto-suave', text: f.metrica_nome ? ` · métrica: ${f.metrica_nome}` : ''})),
        h('div', {class: 'resumo-fonte'},
            h('div', {}, h('span', {class: 'mini-rotulo', text: 'Orçado'}), h('strong', {text: f.orcado_periodo === null ? '—' : moeda(f.orcado_periodo)})),
            h('div', {}, h('span', {class: 'mini-rotulo', text: 'Realizado'}), h('strong', {text: moeda(f.realizado_periodo)})),
            h('div', {}, h('span', {class: 'mini-rotulo', text: 'Variação (orçado − realizado)'}), h('strong', {}, variacao(f.variacao_periodo))),
            h('div', {}, h('span', {class: 'mini-rotulo', text: 'Saving de iniciativas ligadas'}), h('strong', {text: `${moeda(f.saving_iniciativas_mensal)}/mês`}))),
        tem ? h('div', {class: 'tabela-wrap'}, h('table', {class: 'tabela-fin'},
            cabecalho(['Mês', ['Orçado', true], ['Realizado', true], ['Variação', true], [f.metrica_nome ?? 'Métrica', true], ['Custo unitário', true]]),
            h('tbody', {}, f.serie.filter(s => s.realizado !== null || s.orcado !== null).map(s => h('tr', {},
                h('td', {text: competencia(s.competencia, true)}),
                h('td', {class: 'num', text: s.orcado === null ? '—' : moeda(s.orcado)}),
                h('td', {class: 'num', text: s.realizado === null ? '—' : moeda(s.realizado)}),
                h('td', {class: 'num'}, variacao(s.variacao)),
                h('td', {class: 'num', text: s.metrica_valor === null ? '—' : decimal(s.metrica_valor)}),
                h('td', {class: 'num', text: s.custo_unitario === null ? '—' : moeda(s.custo_unitario)})))))) : h('p', {class: 'texto-suave vazio-inline', text: 'Sem faturas neste período.'}));
}

function montar(d) {
    const k = d.kpis, st = k.iniciativas_por_status ?? {};
    const semFaturas = !d.serie.some(s => s.realizado !== null || s.orcado !== null);
    const resumoStatus = ['PLANEJADA', 'EM_SAVING', 'NOVO_NORMAL', 'ENCERRADA'].map(s => h('span', {}, badgeStatus(s), ` ${numero(st[s] ?? 0)}`));
    return h('div', {},
        nota(h('strong', {text: 'Regra da janela: '}), REGRA_JANELA.replace('N meses (padrão 6)', `N meses (padrão ${d.janela_padrao})`)),
        h('div', {class: 'kpis kpis-fin'},
            kpi('circle-check', 'Saving realizado no período', moeda(k.saving_realizado), 'kpi-resolvido', `até ${competencia(d.referencia, true)}`),
            kpi('trending-up', 'Saving projetado', moeda(k.saving_projetado), '', `meses após ${competencia(d.referencia, true)}`),
            kpi('calendar', 'Horas liberadas/mês', `${decimal(k.horas_mes_liberadas)} h`, '', `${decimal(k.fte_liberado)} FTE (horas ÷ ${d.horas_fte_mes})`),
            kpi('repeat', 'Novo normal incorporado', `${moeda(k.novo_normal_mensal)}/mês`, 'kpi-neutro', 'Janela concluída: já faz parte do baseline'),
            kpi('calculator', 'ROI na janela', k.roi_pct === null ? '—' : pct(k.roi_pct), '', `Investimento ${moeda(k.investimento_total)} · saving na janela ${moeda(k.saving_janela_total)}`)),
        cartaoEmCurso(k),
        h('section', {class: 'cartao'},
            h('div', {class: 'cartao-topo'}, h('h2', {}, icone('trending-up'), 'Saving mensal'),
                legenda([['g-direto', 'Economia direta'], ['g-horas', 'Horas do time'], ['g-direto g-proj', 'Projetado (mais claro)']])),
            h('div', {class: 'grafico-wrap'}, graficoSaving(d.serie))),
        h('section', {class: 'cartao'},
            h('div', {class: 'cartao-topo'}, h('h2', {}, icone('lightbulb'), 'Iniciativas'), h('div', {class: 'status-resumo'}, resumoStatus)),
            tabelaIniciativas(d.iniciativas)),
        h('section', {class: 'cartao'},
            h('div', {class: 'cartao-topo'}, h('h2', {}, icone('receipt'), 'Faturas: orçado × realizado'),
                legenda([['g-orcado', 'Orçado'], ['g-realizado', 'Realizado']])),
            h('p', {class: 'texto-suave pequeno-texto', text: 'Faturas apenas acompanham o custo; o saving vem das iniciativas (sem dupla contagem).'}),
            semFaturas ? h('p', {class: 'texto-suave vazio-inline', text: 'Nenhuma fatura lançada neste período.'}) : h('div', {class: 'grafico-wrap'}, graficoFaturas(d.serie))),
        h('section', {}, h('h2', {class: 'titulo-secao'}, icone('wallet'), 'Fontes de custo'),
            d.fontes.length ? d.fontes.map(blocoFonte) : h('p', {class: 'texto-suave vazio-inline', text: 'Nenhuma fonte de custo cadastrada.'})),
        h('section', {class: 'cartao'}, h('div', {class: 'cartao-topo'}, h('h2', {}, icone('list-filter'), 'Saving por tipo')),
            h('div', {class: 'tabela-wrap'}, h('table', {class: 'tabela-fin'},
                cabecalho(['Tipo', ['Iniciativas', true], ['Saving no período', true]]),
                h('tbody', {}, d.por_tipo.map(t => h('tr', {}, h('td', {text: ROTULO_TIPO[t.tipo] ?? t.tipo}), h('td', {class: 'num', text: numero(t.quantidade)}), h('td', {class: 'num', text: moeda(t.saving_periodo)}))))))));
}

export const finopsPainel = {
    titulo: 'Painel FinOps',
    subtitulo: 'Valor financeiro das decisões do time',
    async render(container, signal) {
        const atual = mesAtual(), ano = atual.slice(0, 4);
        const de = h('input', {type: 'month', id: 'fin-de', value: `${ano}-01`, required: true});
        const ate = h('input', {type: 'month', id: 'fin-ate', value: `${ano}-12`, required: true});
        const ref = h('input', {type: 'month', id: 'fin-ref', value: atual, required: true});
        const area = h('div', {});

        async function carregar() {
            if (!de.value || !ate.value || !ref.value) return;
            if (ate.value < de.value) { area.replaceChildren(h('p', {class: 'erro', role: 'alert', text: 'O mês final deve ser igual ou posterior ao inicial.'})); return; }
            area.replaceChildren(carregando(3));
            try {
                const dados = await get('/api/v1/finops/dashboard', {de: de.value, ate: ate.value, referencia: ref.value}, signal);
                if (signal.aborted) return;
                const vazio = !dados.iniciativas.length && !dados.fontes.length;
                area.replaceChildren(vazio
                    ? estadoVazio({titulo: 'Nada para mostrar ainda', icone: 'trending-up'}, 'Cadastre uma iniciativa (melhoria, automação ou otimização de custo) para ver o saving, ou lance faturas para acompanhar o orçado × realizado.',
                        h('a', {class: 'botao', href: '#/finops/iniciativas'}, icone('lightbulb', {classe: 'icone-sm'}), 'Ir para Iniciativas'),
                        h('a', {class: 'botao secundario', href: '#/finops/faturas'}, icone('receipt', {classe: 'icone-sm'}), 'Ir para Faturas'))
                    : montar(dados));
            } catch (erro) {
                if (signal.aborted) return;
                area.replaceChildren(h('p', {class: 'erro', role: 'alert', text: erro.message}));
                tratarErro(erro);
            }
        }
        for (const c of [de, ate, ref]) c.addEventListener('change', carregar);
        container.replaceChildren(
            h('div', {class: 'barra-acoes nao-imprimir'},
                h('div', {class: 'filtros'}, campo('De', de), campo('Até', ate), campo('Mês de referência (hoje)', ref)),
                h('button', {type: 'button', class: 'secundario', on: {click: () => window.print()}}, 'Exportar PDF')),
            area);
        await carregar();
    }
};
