import {get} from '../api.js';
import {h, campo, carregando, estadoVazio, icone, competencia, data, hojeLocal, mesAtual, moeda, numero, pct, tratarErro} from '../ui.js';
import {graficoDespesas, legenda} from '../grafico.js';
import {STATUS_DESPESA, badgeDespesa, moedaMes} from './despesas-comum.js';
import {kpi, nota} from './finops-comum.js';

function bannerAlertas(alertas) {
    if (!alertas.length) {
        return nota(h('strong', {text: 'Renovações: '}), 'nenhum contrato renova nos próximos 60 dias.');
    }
    const urgentes = alertas.filter(a => a.nivel === 'URGENTE').length;
    return h('section', {class: `cartao alertas ${urgentes ? 'alertas-urgente' : 'alertas-atencao'}`, 'aria-label': 'Alertas de renovação'},
        h('div', {class: 'cartao-topo'},
            h('h2', {}, icone('triangle-alert'), `Renovações nos próximos 60 dias (${alertas.length})`),
            h('span', {class: 'texto-suave pequeno-texto', text: urgentes ? `${urgentes} em até 30 dias` : 'Nenhuma em até 30 dias'})),
        h('ul', {class: 'lista-alertas'}, alertas.map(a => h('li', {class: `alerta-item alerta-${a.nivel.toLowerCase()}`},
            h('span', {class: `selo-nivel nivel-${a.nivel.toLowerCase()}`, text: a.nivel === 'URGENTE' ? 'Urgente' : 'Atenção'}),
            h('div', {class: 'alerta-corpo'},
                h('strong', {text: a.nome}),
                h('div', {class: 'texto-suave pequeno-texto', text: `${a.fornecedor ? `${a.fornecedor} · ` : ''}${data(a.data_renovacao)} · em ${a.dias} ${a.dias === 1 ? 'dia' : 'dias'}`})),
            h('div', {class: 'alerta-valor'}, h('strong', {text: moedaMes(a.custo_mensal)}), badgeDespesa(a.status_auditoria))))),
        h('div', {class: 'acoes'}, h('a', {class: 'botao secundario pequeno', href: '#/despesas/inventario'}, 'Abrir inventário', icone('chevron-right', {classe: 'icone-sm'}))));
}

// Barras horizontais proporcionais ao maior valor (largura via CSSOM, sem style inline).
function barras(itens, rotulo, classeBarra) {
    const max = Math.max(...itens.map(i => i.custo_mensal), 0);
    return h('ul', {class: 'barras-h'}, itens.map(i => {
        const preenchimento = h('div', {class: `barra-h-cheia ${classeBarra(i)}`});
        preenchimento.style.width = `${max > 0 ? (i.custo_mensal / max) * 100 : 0}%`;
        const nome = i.categoria ?? STATUS_DESPESA[i.status]?.[0] ?? i.status;
        return h('li', {class: 'barra-h'},
            h('div', {class: 'barra-h-topo'}, h('span', {class: 'barra-h-nome'}, rotulo(i)), h('strong', {text: moedaMes(i.custo_mensal)})),
            h('div', {class: 'barra-h-trilho', role: 'img', 'aria-label': `${nome}: ${moedaMes(i.custo_mensal)}, ${numero(i.quantidade)} ${i.quantidade === 1 ? 'despesa' : 'despesas'}`}, preenchimento));
    }));
}

function kpiOrcamento(k, d) {
    if (k.orcado_mes === null || k.orcado_mes === undefined) {
        return kpi('calculator', 'Orçado × previsto no mês', 'Sem orçamento', 'kpi-neutro', `Previsto ${moeda(k.run_rate_mensal)} em ${competencia(d.referencia, true)}`);
    }
    const folga = k.variacao_orcamento ?? 0;
    const previsto = k.orcado_mes - folga;
    return kpi('calculator', 'Orçado × previsto no mês', folga < 0 ? `${moeda(-folga)} acima` : folga > 0 ? `${moeda(folga)} abaixo` : 'No orçado',
        folga < 0 ? 'kpi-estouro' : 'kpi-resolvido',
        `Orçado ${moeda(k.orcado_mes)} · previsto ${moeda(previsto)}`, 'Previsto = run-rate + pontuais do mês');
}

function montar(d) {
    const k = d.kpis;
    const semOrcamento = !d.serie.some(s => s.orcado !== null && s.orcado !== undefined);
    return h('div', {},
        bannerAlertas(d.alertas_renovacao),
        h('div', {class: 'kpis kpis-fin kpis-6'},
            kpi('repeat', 'Run-rate mensal', moeda(k.run_rate_mensal), '', `Recorrentes ativas em ${competencia(d.referencia, true)}`),
            kpi('wallet', 'Run-rate anual', moeda(k.run_rate_anual), '', `Pontuais em ${d.ano}: ${moeda(k.pontuais_ano)}`),
            kpiOrcamento(k, d),
            kpi('triangle-alert', 'Desperdício mensal', moeda(k.desperdicio_mensal), k.desperdicio_mensal > 0 ? 'kpi-aberto' : '', 'Despesas marcadas como desperdício'),
            kpi('badge-dollar-sign', 'Saving capturado', moedaMes(k.saving_capturado_mensal), 'kpi-resolvido', `Novo normal: ${moedaMes(k.novo_normal_mensal)}`),
            kpi('list-checks', 'Auditoria', pct(k.auditoria_pct), 'kpi-neutro', `${numero(k.total_despesas - (k.por_status?.EM_REVISAO ?? 0))} de ${numero(k.total_despesas)} despesas já revisadas`)),
        h('section', {class: 'cartao'},
            h('div', {class: 'cartao-topo'}, h('h2', {}, icone('trending-up'), `Despesas por mês em ${d.ano}`),
                legenda([['g-recorrente', 'Recorrentes'], ['g-pontual', 'Pontuais'], ['g-orcado', 'Orçado']])),
            semOrcamento ? h('p', {class: 'texto-suave pequeno-texto'}, 'Sem orçamento cadastrado neste ano: ', h('a', {href: '#/despesas/orcamento', text: 'cadastrar orçamento'}), '.') : null,
            h('div', {class: 'grafico-wrap'}, graficoDespesas(d.serie))),
        h('div', {class: 'grade-2'},
            h('section', {class: 'cartao'}, h('h2', {class: 'titulo-secao'}, icone('package'), 'Custo mensal por categoria'),
                d.por_categoria.length ? barras(d.por_categoria, i => `${i.categoria} · ${numero(i.quantidade)}`, () => 'barra-categoria') : h('p', {class: 'texto-suave vazio-inline', text: 'Sem despesas ativas.'})),
            h('section', {class: 'cartao'}, h('h2', {class: 'titulo-secao'}, icone('list-checks'), 'Custo mensal por status de auditoria'),
                barras(d.por_status, i => [badgeDespesa(i.status), ` ${numero(i.quantidade)}`], i => `barra-${i.status.toLowerCase().replace('_', '-')}`))));
}

export const despesasPainel = {
    titulo: 'Painel de despesas',
    subtitulo: 'Run-rate, orçamento, renovações e saving dos contratos',
    async render(container, signal) {
        const ref = h('input', {type: 'month', id: 'dsp-ref', value: mesAtual(), required: true});
        const area = h('div', {});
        async function carregar() {
            if (!ref.value) return;
            area.replaceChildren(carregando(3));
            try {
                const dados = await get('/api/v1/despesas/dashboard', {referencia: ref.value, hoje: hojeLocal()}, signal);
                if (signal.aborted) return;
                area.replaceChildren(dados.kpis.total_despesas === 0
                    ? estadoVazio({titulo: 'Nenhuma despesa cadastrada', icone: 'wallet'}, 'Cadastre contratos e assinaturas no inventário para acompanhar run-rate, renovações e saving.',
                        h('a', {class: 'botao', href: '#/despesas/inventario'}, icone('package', {classe: 'icone-sm'}), 'Ir para o Inventário'),
                        h('a', {class: 'botao secundario', href: '#/despesas/orcamento'}, icone('calculator', {classe: 'icone-sm'}), 'Definir orçamento'))
                    : montar(dados));
            } catch (erro) {
                if (signal.aborted) return;
                area.replaceChildren(h('p', {class: 'erro', role: 'alert', text: erro.message}));
                tratarErro(erro);
            }
        }
        ref.addEventListener('change', carregar);
        container.replaceChildren(
            h('div', {class: 'barra-acoes nao-imprimir'},
                h('div', {class: 'filtros'}, campo('Mês de referência', ref)),
                h('button', {type: 'button', class: 'secundario', on: {click: () => window.print()}}, icone('printer', {classe: 'icone-sm'}), 'Exportar PDF')),
            area);
        await carregar();
    }
};
