import {get} from '../api.js';
import {h, campo, carregando, estadoVazio, hojeLocal, icone, minutos, numero, pct, pctFracao, pp, salvarArquivo, tratarErro} from '../ui.js';
import {tileGrupo} from './capacidade-comum.js';

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

function kpi(rotulo, valor, classe = '', aux = null, progresso = null) {
    const barra = progresso === null ? null : h('div', {class: 'progresso kpi-barra', role: 'img', 'aria-label': `${Math.round(progresso)}%`}, h('div', {class: 'progresso-preenchido'}));
    if (barra) barra.firstChild.style.width = `${Math.min(100, Math.max(0, progresso))}%`;
    return h('div', {class: `kpi ${classe}`}, h('span', {class: 'kpi-rotulo', text: rotulo}), h('strong', {class: 'kpi-valor'}, valor), aux ? h('span', {class: 'kpi-aux', text: aux}) : null, barra);
}

// Meta BUILD é piso, meta RUN é teto: a marca vertical mostra onde está a meta no trilho 0-100%.
function linhaCategoria(nome, quantidade, perc, status, meta) {
    const preenchido = h('div', {class: 'meta-preenchido'});
    preenchido.style.width = `${Math.min(100, Math.max(0, perc * 100))}%`;
    const marca = h('span', {class: 'meta-marca', title: `Meta ${Math.round(meta * 100)}%`});
    marca.style.left = `${Math.min(100, Math.max(0, meta * 100))}%`;
    return h('div', {class: `categoria ${status.ok ? 'ok' : 'alerta'}`},
        h('div', {class: 'categoria-topo'},
            h('span', {class: 'categoria-nome', text: nome}),
            h('span', {class: 'categoria-qtd', text: `${numero(quantidade)} itens`})),
        h('strong', {class: 'categoria-pct', text: pctFracao(perc)}),
        h('div', {class: 'meta-trilho', role: 'img', 'aria-label': `${pctFracao(perc)} de ${nome}, meta ${Math.round(meta * 100)}%`}, preenchido, marca),
        h('span', {class: 'meta-legenda', text: `${nome === 'BUILD' ? 'Piso' : 'Teto'} de ${Math.round(meta * 100)}%`}),
        h('span', {class: 'selo'}, icone(status.ok ? 'circle-check' : 'triangle-alert'), status.texto));
}

function cartao(titulo, nomeIcone, build, run) {
    return h('section', {class: 'cartao'},
        h('div', {class: 'cartao-topo'}, h('h2', {}, icone(nomeIcone), titulo)),
        h('div', {class: 'categorias'}, build, run));
}

function segmentos(abertos, resolvidos, pctAbertos, pctResolvidos) {
    const segAberto = h('div', {class: 'seg seg-aberto', title: `${abertos} abertos`});
    const segResolvido = h('div', {class: 'seg seg-resolvido', title: `${resolvidos} resolvidos`});
    segAberto.style.width = `${pctAbertos}%`;
    segResolvido.style.width = `${pctResolvidos}%`;
    return h('div', {class: 'barra-empilhada', role: 'img', 'aria-label': `${abertos} abertos e ${resolvidos} resolvidos`}, segAberto, segResolvido);
}

function barras(grupos, filtro) {
    const visiveis = grupos.filter(g => filtro === 'TODOS' || (filtro === 'ABERTO' ? g.abertos > 0 : g.resolvidos > 0));
    if (!visiveis.length) return [h('p', {class: 'texto-suave', text: 'Nenhum grupo para este filtro.'})];
    return visiveis.map(g => h('div', {class: 'barra-grupo'},
        h('div', {class: 'barra-topo'},
            tileGrupo(g.icone, g.cor),
            h('span', {class: 'barra-nome', title: g.nome, text: g.nome}),
            h('span', {class: `badge badge-${g.categoria.toLowerCase()}`, text: g.categoria})),
        h('div', {class: 'barra-corpo'},
            segmentos(g.abertos, g.resolvidos, g.pct_aberto, g.pct_resolvido),
            h('div', {class: 'barra-legenda'},
                h('span', {class: 'leg-aberto', text: `${numero(g.abertos)} abertos (${pct(g.pct_aberto)})`}),
                h('span', {class: 'leg-resolvido', text: `${numero(g.resolvidos)} resolvidos`})),
            g.demandas_abertas > 0 || g.demandas_resolvidas > 0 ? h('div', {class: 'barra-extra',
                text: `Inclui demandas: ${numero(g.demandas_abertas)} abertas, ${numero(g.demandas_resolvidas)} resolvidas`}) : null),
        h('div', {class: 'barra-taxa'}, h('strong', {text: pct(g.taxa_resolucao)}), h('span', {text: `de ${numero(g.total)} itens`}))));
}

function barrasRotinas(rotinas, filtro) {
    return rotinas.filter(r => filtro === 'TODOS' || (filtro === 'ABERTO' ? r.abertos > 0 : r.resolvidos > 0)).map(r => {
        const pctAberto = r.total ? (r.abertos / r.total) * 100 : 0;
        const pctResolvido = r.total ? (r.resolvidos / r.total) * 100 : 0;
        return h('div', {class: 'barra-grupo barra-rotina'},
            h('div', {class: 'barra-topo'},
                h('span', {class: 'icone-tile', 'aria-hidden': 'true'}, icone('repeat', {classe: 'icone-sm'})),
                h('span', {class: 'barra-nome', text: 'Rotinas'}),
                h('span', {class: `badge badge-${r.categoria.toLowerCase()}`, text: r.categoria})),
            h('div', {class: 'barra-corpo'},
                segmentos(r.abertos, r.resolvidos, pctAberto, pctResolvido),
                h('div', {class: 'barra-legenda'},
                    h('span', {class: 'leg-aberto', text: `${numero(r.abertos)} abertos (${pct(pctAberto)})`}),
                    h('span', {class: 'leg-resolvido', text: `${numero(r.resolvidos)} resolvidos`})),
                h('div', {class: 'barra-extra', text: `Previsto ${minutos(r.minutos_previstos)} × executado ${minutos(r.minutos_executados)}`})),
            h('div', {class: 'barra-taxa'}, h('strong', {text: pct(pctResolvido)}), h('span', {text: `de ${numero(r.total)} ocorrências`})));
    });
}

function cartaoPendencias(p) {
    const hoje = p.vence_hoje.length, atrasadas = p.atrasadas.length;
    return h('section', {class: `cartao cartao-pendencias${hoje + atrasadas ? ' com-pendencia' : ''}`},
        h('div', {class: 'cartao-topo'},
            h('h2', {}, icone(hoje + atrasadas ? 'triangle-alert' : 'circle-check'), 'Rotinas: não deixe nada para trás'),
            h('a', {class: 'botao secundario pequeno', href: '#/rotinas'}, 'Abrir rotinas', icone('chevron-right', {classe: 'icone-sm'}))),
        h('div', {class: 'alerta-rotinas'},
            h('span', {class: 'badge situacao situacao-hoje', text: `${numero(hoje)} vencem hoje`}),
            h('span', {class: 'badge situacao situacao-atrasada', text: `${numero(atrasadas)} atrasadas`}),
            hoje + atrasadas === 0 ? h('span', {class: 'texto-suave', text: 'Tudo em dia.'}) : null));
}

function montarDashboard(d, pendencias) {
    const rotinas = d.rotinas ?? [];
    const previstos = rotinas.reduce((t, r) => t + r.minutos_previstos, 0);
    const executados = rotinas.reduce((t, r) => t + r.minutos_executados, 0);
    const metaB = d.meta_build_min, metaR = d.meta_run_max;
    const resolvidos = cartao('Resolvidos no ciclo', 'circle-check',
        linhaCategoria('BUILD', d.resolvidos_build, d.perc_build_resolvidos, statusBuild(d.perc_build_resolvidos, metaB), metaB),
        linhaCategoria('RUN', d.resolvidos_run, d.perc_run_resolvidos, statusRun(d.perc_run_resolvidos, metaR), metaR));
    const backlog = cartao('Backlog', 'list-todo',
        linhaCategoria('BUILD', d.abertos_build, d.perc_build_abertos, statusBuild(d.perc_build_abertos, metaB), metaB),
        linhaCategoria('RUN', d.abertos_run, d.perc_run_abertos, statusRun(d.perc_run_abertos, metaR), metaR));

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
            kpi('Total de itens', numero(d.total), '', `${numero(d.qtd_build)} BUILD · ${numero(d.qtd_run)} RUN`),
            kpi('Abertos (backlog)', numero(d.total_abertos), 'kpi-aberto', d.total ? `${pct((d.total_abertos / d.total) * 100)} do total` : null),
            kpi('Resolvidos', numero(d.total_resolvidos), 'kpi-resolvido', d.total ? `${pct((d.total_resolvidos / d.total) * 100)} do total` : null),
            kpi('Taxa de resolução', pct(d.taxa_resolucao), '', null, d.taxa_resolucao),
            kpi('Horas de rotina', minutos(executados), 'kpi-horas', `executadas de ${minutos(previstos)} previstas`, previstos ? (executados / previstos) * 100 : null)),
        pendencias ? cartaoPendencias(pendencias) : null,
        h('div', {class: 'grade-2'}, resolvidos, backlog),
        h('section', {class: 'cartao'},
            h('div', {class: 'cartao-topo'}, h('h2', {}, icone('users'), 'Itens por grupo'), h('div', {class: 'chips', role: 'group', 'aria-label': 'Filtrar por status'}, chips)),
            lista));
}

export const painel = {
    titulo: 'Painel',
    subtitulo: 'Capacidade BUILD × RUN e vazão por semana',
    async render(container, signal) {
        container.replaceChildren(carregando(3));
        const semanas = await get('/api/v1/semanas', undefined, signal);
        const grupos = await get('/api/v1/grupos', undefined, signal);
        if (!semanas.length || !grupos.length) {
            container.replaceChildren(estadoVazio({titulo: 'Nada para mostrar ainda', icone: 'layout-dashboard'},
                'Crie ao menos um grupo e uma semana, depois registre lançamentos para ver os indicadores.',
                h('a', {class: 'botao', href: '#/config/grupos'}, icone('users', {classe: 'icone-sm'}), 'Configurar grupos'),
                h('a', {class: 'botao secundario', href: '#/config/semanas'}, icone('calendar', {classe: 'icone-sm'}), 'Configurar semanas')));
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
            area.replaceChildren(carregando(3));
            try {
                const [resultado, pendencias] = await Promise.all([
                    get('/api/v1/dashboard', {semana_id: seletor.value}, signal),
                    get('/api/v1/rotinas/pendencias', {hoje}, signal).catch(() => null)]);
                if (signal.aborted) return;
                dados = resultado;
                rotuloImpressao.textContent = `Período: ${dados.periodo}`;
                area.replaceChildren(dados.total === 0
                    ? estadoVazio({titulo: 'Sem lançamentos neste período', icone: 'trending-up'}, 'Inicialize a semana em Lançamentos para começar a registrar.',
                        h('a', {class: 'botao', href: '#/lancamentos'}, 'Ir para Lançamentos', icone('chevron-right', {classe: 'icone-sm'})))
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
                    h('button', {type: 'button', class: 'secundario', on: {click: () => window.print()}}, icone('receipt', {classe: 'icone-sm'}), 'Exportar PDF'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => {
                        if (!dados) return;
                        const nome = (dados.periodo || 'todas').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'painel';
                        salvarArquivo(`painel-${nome}.json`, JSON.stringify(dados, null, 2), 'application/json');
                    }}}, icone('package', {classe: 'icone-sm'}), 'Exportar JSON'))),
            rotuloImpressao,
            area);
        await carregar();
    }
};
