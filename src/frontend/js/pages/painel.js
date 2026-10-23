import {get} from '../api.js';
import {h, campo, estadoVazio, hojeLocal, minutos, numero, pct, pctFracao, pp, salvarArquivo, tratarErro} from '../ui.js';

const TODAS = '';

// Status BUILD: piso (>=). Status RUN: teto (<=). Calculado a partir dos percentuais (0-1).
function statusBuild(perc, meta) {
    const gap = (perc - meta) * 100;
    return perc >= meta
        ? {ok: true, texto: `Meta ≥ ${Math.round(meta * 100)}% atingida`}
        : {ok: false, texto: `Abaixo do piso (${pp(gap)})`};
}
function statusRun(perc, meta) {
    const gap = (perc - meta) * 100;
    return perc <= meta
        ? {ok: true, texto: `Dentro do teto (≤ ${Math.round(meta * 100)}%)`}
        : {ok: false, texto: `Acima do teto (${pp(gap)})`};
}

function kpi(rotulo, valor, classe = '') {
    return h('div', {class: `kpi ${classe}`}, h('span', {class: 'kpi-rotulo', text: rotulo}), h('strong', {class: 'kpi-valor', text: valor}));
}

function linhaCategoria(nome, quantidade, perc, status) {
    return h('div', {class: `categoria ${status.ok ? 'ok' : 'alerta'}`},
        h('div', {class: 'categoria-topo'},
            h('span', {class: 'categoria-nome', text: nome}),
            h('span', {class: 'categoria-qtd', text: `${numero(quantidade)} itens`})),
        h('strong', {class: 'categoria-pct', text: pctFracao(perc)}),
        h('span', {class: 'selo', text: status.texto}));
}

function cartao(titulo, build, run) {
    return h('section', {class: 'cartao'}, h('h2', {text: titulo}), h('div', {class: 'categorias'}, build, run));
}

function barras(grupos, filtro) {
    const visiveis = grupos.filter(g => filtro === 'TODOS' || (filtro === 'ABERTO' ? g.abertos > 0 : g.resolvidos > 0));
    if (!visiveis.length) return [h('p', {class: 'texto-suave', text: 'Nenhum grupo para este filtro.'})];
    return visiveis.map(g => {
        const segAberto = h('div', {class: 'seg seg-aberto', title: `${g.abertos} abertos`});
        const segResolvido = h('div', {class: 'seg seg-resolvido', title: `${g.resolvidos} resolvidos`});
        segAberto.style.width = `${g.pct_aberto}%`;
        segResolvido.style.width = `${g.pct_resolvido}%`;
        return h('div', {class: 'barra-grupo'},
            h('div', {class: 'barra-topo'},
                h('span', {class: 'barra-nome', text: `${g.icone} ${g.nome}`}),
                h('span', {class: 'badge', text: g.categoria}),
                h('span', {class: 'texto-suave', text: `${numero(g.total)} itens`})),
            h('div', {class: 'barra-empilhada'}, segAberto, segResolvido),
            h('div', {class: 'barra-legenda'},
                h('span', {class: 'leg-aberto', text: `${numero(g.abertos)} abertos (${pct(g.pct_aberto)})`}),
                h('span', {class: 'leg-resolvido', text: `${numero(g.resolvidos)} resolvidos (${pct(g.taxa_resolucao)})`})),
            g.demandas_abertas > 0 || g.demandas_resolvidas > 0 ? h('div', {class: 'texto-suave',
                text: `Inclui demandas: ${numero(g.demandas_abertas)} abertas, ${numero(g.demandas_resolvidas)} resolvidas`}) : null);
    });
}

function barrasRotinas(rotinas, filtro) {
    return rotinas.filter(r => filtro === 'TODOS' || (filtro === 'ABERTO' ? r.abertos > 0 : r.resolvidos > 0)).map(r => {
        const pctAberto = r.total ? (r.abertos / r.total) * 100 : 0;
        const pctResolvido = r.total ? (r.resolvidos / r.total) * 100 : 0;
        const segAberto = h('div', {class: 'seg seg-aberto', title: `${r.abertos} abertos`});
        const segResolvido = h('div', {class: 'seg seg-resolvido', title: `${r.resolvidos} resolvidos`});
        segAberto.style.width = `${pctAberto}%`;
        segResolvido.style.width = `${pctResolvido}%`;
        return h('div', {class: 'barra-grupo barra-rotina'},
            h('div', {class: 'barra-topo'},
                h('span', {class: 'barra-nome', text: '🔁 Rotinas'}),
                h('span', {class: `badge badge-${r.categoria.toLowerCase()}`, text: r.categoria}),
                h('span', {class: 'texto-suave', text: `${numero(r.total)} ocorrências`})),
            h('div', {class: 'barra-empilhada'}, segAberto, segResolvido),
            h('div', {class: 'barra-legenda'},
                h('span', {class: 'leg-aberto', text: `${numero(r.abertos)} abertos (${pct(pctAberto)})`}),
                h('span', {class: 'leg-resolvido', text: `${numero(r.resolvidos)} resolvidos (${pct(pctResolvido)})`}),
                h('span', {class: 'texto-suave', text: `Previsto ${minutos(r.minutos_previstos)} × executado ${minutos(r.minutos_executados)}`})));
    });
}

function cartaoPendencias(p) {
    const hoje = p.vence_hoje.length, atrasadas = p.atrasadas.length;
    return h('section', {class: `cartao cartao-pendencias${hoje + atrasadas ? ' com-pendencia' : ''}`},
        h('div', {class: 'cartao-topo'},
            h('h2', {text: 'Rotinas: não deixe nada para trás'}),
            h('a', {class: 'botao secundario pequeno', href: '#/rotinas', text: 'Abrir rotinas'})),
        h('p', {},
            h('span', {class: 'badge situacao situacao-hoje', text: `${numero(hoje)} vencem hoje`}), ' ',
            h('span', {class: 'badge situacao situacao-atrasada', text: `${numero(atrasadas)} atrasadas`}),
            hoje + atrasadas === 0 ? h('span', {class: 'texto-suave', text: ' Tudo em dia.'}) : null));
}

function montarDashboard(d, pendencias) {
    const rotinas = d.rotinas ?? [];
    const previstos = rotinas.reduce((t, r) => t + r.minutos_previstos, 0);
    const executados = rotinas.reduce((t, r) => t + r.minutos_executados, 0);
    const metaB = d.meta_build_min, metaR = d.meta_run_max;
    const resolvidos = cartao('Resolvidos no ciclo',
        linhaCategoria('BUILD', d.resolvidos_build, d.perc_build_resolvidos, statusBuild(d.perc_build_resolvidos, metaB)),
        linhaCategoria('RUN', d.resolvidos_run, d.perc_run_resolvidos, statusRun(d.perc_run_resolvidos, metaR)));
    const backlog = cartao('Backlog',
        linhaCategoria('BUILD', d.abertos_build, d.perc_build_abertos, statusBuild(d.perc_build_abertos, metaB)),
        linhaCategoria('RUN', d.abertos_run, d.perc_run_abertos, statusRun(d.perc_run_abertos, metaR)));

    const lista = h('div', {class: 'barras'});
    const chips = ['TODOS', 'ABERTO', 'RESOLVIDO'].map(valor => h('button', {
        type: 'button', class: `chip${valor === 'TODOS' ? ' ativo' : ''}`,
        'aria-pressed': String(valor === 'TODOS'),
        on: {click: () => {
            for (const c of chips) {
                const ativo = c === chips[['TODOS', 'ABERTO', 'RESOLVIDO'].indexOf(valor)];
                c.classList.toggle('ativo', ativo);
                c.setAttribute('aria-pressed', String(ativo));
            }
            lista.replaceChildren(...barras(d.groups, valor), ...barrasRotinas(rotinas, valor));
        }}
    }, {TODOS: 'Todos', ABERTO: 'Abertos', RESOLVIDO: 'Resolvidos'}[valor]));
    lista.replaceChildren(...barras(d.groups, 'TODOS'), ...barrasRotinas(rotinas, 'TODOS'));

    return h('div', {},
        h('div', {class: 'kpis'},
            kpi('Total de itens', numero(d.total)),
            kpi('Abertos (backlog)', numero(d.total_abertos), 'kpi-aberto'),
            kpi('Resolvidos', numero(d.total_resolvidos), 'kpi-resolvido'),
            kpi('Taxa de resolução', pct(d.taxa_resolucao)),
            kpi('Horas de rotina (exec. × prev.)', `${minutos(executados)} × ${minutos(previstos)}`)),
        pendencias ? cartaoPendencias(pendencias) : null,
        h('div', {class: 'grade-2'}, resolvidos, backlog),
        h('section', {class: 'cartao'},
            h('div', {class: 'cartao-topo'}, h('h2', {text: 'Itens por grupo'}), h('div', {class: 'chips', role: 'group', 'aria-label': 'Filtrar por status'}, chips)),
            lista));
}

export const painel = {
    titulo: 'Painel',
    subtitulo: 'Capacidade BUILD × RUN e vazão por semana',
    async render(container, signal) {
        container.replaceChildren(h('p', {class: 'texto-suave', text: 'Carregando painel…'}));
        const semanas = await get('/api/v1/semanas', undefined, signal);
        const grupos = await get('/api/v1/grupos', undefined, signal);
        if (!semanas.length || !grupos.length) {
            container.replaceChildren(estadoVazio('Nada para mostrar ainda',
                'Crie ao menos um grupo e uma semana, depois registre lançamentos para ver os indicadores.',
                h('a', {class: 'botao', href: '#/config/grupos', text: 'Configurar grupos'}),
                h('a', {class: 'botao secundario', href: '#/config/semanas', text: 'Configurar semanas'})));
            return;
        }
        let dados = null;
        const hoje = hojeLocal();
        const rotuloImpressao = h('p', {class: 'so-impressao'});
        const area = h('div', {});
        const seletor = h('select', {id: 'painel-semana'},
            h('option', {value: TODAS, text: 'Todas as semanas'}),
            semanas.map(s => h('option', {value: s.id, text: s.identificacao})));
        seletor.value = semanas[0].id;

        async function carregar() {
            area.replaceChildren(h('p', {class: 'texto-suave', text: 'Carregando…'}));
            try {
                const [resultado, pendencias] = await Promise.all([
                    get('/api/v1/dashboard', {semana_id: seletor.value}, signal),
                    get('/api/v1/rotinas/pendencias', {hoje}, signal).catch(() => null)]);
                if (signal.aborted) return;
                dados = resultado;
                rotuloImpressao.textContent = `Período: ${dados.periodo}`;
                area.replaceChildren(dados.total === 0
                    ? estadoVazio('Sem lançamentos neste período', 'Inicialize a semana em Lançamentos para começar a registrar.',
                        h('a', {class: 'botao', href: '#/lancamentos', text: 'Ir para Lançamentos'}))
                    : montarDashboard(dados, pendencias));
            } catch (erro) {
                if (signal.aborted) return;
                dados = null;
                area.replaceChildren(h('p', {class: 'erro', text: erro.message}));
                tratarErro(erro);
            }
        }
        seletor.addEventListener('change', carregar);

        container.replaceChildren(
            h('div', {class: 'barra-acoes nao-imprimir'},
                campo('Período', seletor),
                h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: () => window.print()}}, 'Exportar PDF'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => {
                        if (!dados) return;
                        const nome = (dados.periodo || 'todas').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'painel';
                        salvarArquivo(`painel-${nome}.json`, JSON.stringify(dados, null, 2), 'application/json');
                    }}}, 'Exportar JSON'))),
            rotuloImpressao,
            area);
        await carregar();
    }
};
