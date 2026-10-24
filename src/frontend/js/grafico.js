// Gráficos em SVG puro (createElementNS). Cores e tipografia vêm de classes CSS (CSP sem style inline).
import {competencia, moeda, moedaCurta} from './ui.js';

const NS = 'http://www.w3.org/2000/svg';

export function svg(tag, attrs, ...filhos) {
    const el = document.createElementNS(NS, tag);
    for (const [chave, valor] of Object.entries(attrs ?? {})) {
        if (valor === undefined || valor === null || valor === false) continue;
        el.setAttribute(chave === 'class' ? 'class' : chave, String(valor));
    }
    for (const filho of filhos.flat()) {
        if (filho === undefined || filho === null || filho === false) continue;
        el.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
    }
    return el;
}
const texto = (conteudo, attrs) => svg('text', attrs, conteudo);
const dica = conteudo => svg('title', {}, conteudo);

// Escala "bonita": maior valor arredondado para 1, 2, 2.5 ou 5 × 10^n.
function tetoBonito(max) {
    if (!(max > 0)) return 1;
    const exp = 10 ** Math.floor(Math.log10(max));
    for (const f of [1, 2, 2.5, 5, 10]) if (f * exp >= max) return f * exp;
    return 10 * exp;
}

const L = 720, A = 280, MARGEM = {e: 56, d: 12, t: 12, b: 34};

function moldura(rotulo, teto, extras) {
    const w = L - MARGEM.e - MARGEM.d, h = A - MARGEM.t - MARGEM.b;
    const raiz = svg('svg', {class: 'grafico', viewBox: `0 0 ${L} ${A}`, role: 'img', 'aria-label': rotulo, preserveAspectRatio: 'xMidYMid meet'});
    const y = valor => MARGEM.t + h - (valor / teto) * h;
    for (let i = 0; i <= 4; i++) {
        const v = (teto / 4) * i;
        raiz.append(svg('line', {class: i === 0 ? 'g-grade g-base' : 'g-grade', x1: MARGEM.e, x2: L - MARGEM.d, y1: y(v), y2: y(v)}),
            texto(moedaCurta(v), {class: 'g-eixo', x: MARGEM.e - 6, y: y(v) + 4, 'text-anchor': 'end'}));
    }
    extras?.(raiz, {w, h, y});
    return {raiz, w, h, y};
}

const passo = n => (n > 18 ? Math.ceil(n / 12) : 1);

function rotulosX(raiz, serie, x0, larg) {
    const p = passo(serie.length);
    serie.forEach((s, i) => {
        if (i % p) return;
        raiz.append(texto(competencia(s.competencia), {class: 'g-eixo', x: x0 + larg * (i + 0.5), y: A - MARGEM.b + 16, 'text-anchor': 'middle'}));
    });
}

// Barras mensais empilhadas: economia direta × horas do time. Meses projetados usam classe mais clara.
export function graficoSaving(serie) {
    const teto = tetoBonito(Math.max(...serie.map(s => (s.saving_direto ?? 0) + (s.saving_horas ?? 0)), 0));
    const total = serie.length || 1;
    const {raiz, w, y} = moldura('Saving mensal em reais, empilhado entre economia direta e horas do time', teto);
    const larg = w / total, barra = Math.max(4, Math.min(44, larg * 0.7));
    serie.forEach((s, i) => {
        const cx = MARGEM.e + larg * (i + 0.5), proj = s.projetado ? ' g-proj' : '';
        const direto = Math.max(0, s.saving_direto ?? 0), horas = Math.max(0, s.saving_horas ?? 0);
        const topoDireto = y(direto), topoHoras = y(direto + horas);
        const grupo = svg('g', {class: 'g-coluna'}, dica(`${competencia(s.competencia, true)}${s.projetado ? ' (projetado)' : ''}\nEconomia direta: ${moeda(s.saving_direto)}\nHoras do time: ${moeda(s.saving_horas)}\nTotal: ${moeda(s.saving_total)}`));
        if (direto > 0) grupo.append(svg('rect', {class: `g-direto${proj}`, x: cx - barra / 2, y: topoDireto, width: barra, height: y(0) - topoDireto, rx: horas > 0 ? 0 : 2}));
        if (horas > 0) grupo.append(svg('rect', {class: `g-horas${proj}`, x: cx - barra / 2, y: topoHoras, width: barra, height: topoDireto - topoHoras, rx: 2}));
        // Total acima da barra quando há poucos meses (evita poluir séries longas).
        if (total <= 12 && direto + horas > 0) grupo.append(texto(moedaCurta(direto + horas), {class: 'g-valor', x: cx, y: topoHoras - 5, 'text-anchor': 'middle'}));
        // Área de toque transparente para o tooltip nativo mesmo em barras zeradas.
        grupo.append(svg('rect', {class: 'g-alvo', x: cx - larg / 2, y: MARGEM.t, width: larg, height: A - MARGEM.t - MARGEM.b}));
        raiz.append(grupo);
    });
    rotulosX(raiz, serie, MARGEM.e, larg);
    return raiz;
}

// Linhas orçado × realizado (valores nulos interrompem a linha).
export function graficoFaturas(serie) {
    const valores = serie.flatMap(s => [s.orcado, s.realizado]).filter(v => v !== null && v !== undefined);
    const teto = tetoBonito(Math.max(...valores, 0));
    const total = serie.length || 1;
    const {raiz, w, y} = moldura('Custo mensal das faturas: orçado e realizado em reais', teto);
    const larg = w / total;
    const caminho = campo => {
        let d = '', ativo = false;
        serie.forEach((s, i) => {
            const v = s[campo];
            if (v === null || v === undefined) { ativo = false; return; }
            d += `${ativo ? 'L' : 'M'}${MARGEM.e + larg * (i + 0.5)} ${y(v)} `;
            ativo = true;
        });
        return d.trim();
    };
    for (const [campo, classe] of [['orcado', 'g-orcado'], ['realizado', 'g-realizado']]) {
        const d = caminho(campo);
        if (d) raiz.append(svg('path', {class: `g-linha ${classe}`, d}));
        serie.forEach((s, i) => {
            if (s[campo] === null || s[campo] === undefined) return;
            raiz.append(svg('circle', {class: `g-ponto ${classe}`, cx: MARGEM.e + larg * (i + 0.5), cy: y(s[campo]), r: 3.5},
                dica(`${competencia(s.competencia, true)}: ${campo === 'orcado' ? 'orçado' : 'realizado'} ${moeda(s[campo])}`)));
        });
    }
    rotulosX(raiz, serie, MARGEM.e, larg);
    return raiz;
}

export function legenda(itens) {
    const ul = document.createElement('ul');
    ul.className = 'legenda';
    for (const [classe, rotulo] of itens) {
        const li = document.createElement('li');
        // Séries de linha ganham um traço; as demais, um quadrado.
        const linha = /g-(orcado|realizado)/.test(classe);
        const marca = svg('svg', {class: 'legenda-marca', viewBox: '0 0 14 14', 'aria-hidden': 'true'},
            linha ? svg('line', {class: `g-linha ${classe}`, x1: 0, x2: 14, y1: 7, y2: 7}) : svg('rect', {class: classe, x: 0, y: 0, width: 14, height: 14, rx: 3}));
        li.append(marca, document.createTextNode(rotulo));
        ul.append(li);
    }
    return ul;
}

// Despesas: barras mensais empilhadas (recorrente + pontual) sobre a linha do orçado (nulo interrompe a linha).
export function graficoDespesas(serie) {
    const valores = serie.flatMap(s => [(s.recorrente ?? 0) + (s.pontual ?? 0), s.orcado]).filter(v => v !== null && v !== undefined);
    const teto = tetoBonito(Math.max(...valores, 0));
    const total = serie.length || 1;
    const {raiz, w, y} = moldura('Despesas por mês em reais: recorrentes e pontuais empilhadas, com a linha do orçado', teto);
    const larg = w / total, barra = Math.max(4, Math.min(44, larg * 0.7));
    serie.forEach((s, i) => {
        const cx = MARGEM.e + larg * (i + 0.5);
        const rec = Math.max(0, s.recorrente ?? 0), pon = Math.max(0, s.pontual ?? 0);
        const grupo = svg('g', {class: 'g-coluna'}, dica(`${competencia(s.competencia, true)}\nRecorrente: ${moeda(s.recorrente)}\nPontual: ${moeda(s.pontual)}\nTotal: ${moeda(s.total)}\nOrçado: ${s.orcado === null || s.orcado === undefined ? 'não cadastrado' : moeda(s.orcado)}`));
        if (rec > 0) grupo.append(svg('rect', {class: 'g-recorrente', x: cx - barra / 2, y: y(rec), width: barra, height: y(0) - y(rec), rx: pon > 0 ? 0 : 2}));
        if (pon > 0) grupo.append(svg('rect', {class: 'g-pontual', x: cx - barra / 2, y: y(rec + pon), width: barra, height: y(rec) - y(rec + pon), rx: 2}));
        grupo.append(svg('rect', {class: 'g-alvo', x: cx - larg / 2, y: MARGEM.t, width: larg, height: A - MARGEM.t - MARGEM.b}));
        raiz.append(grupo);
    });
    let d = '', ativo = false;
    serie.forEach((s, i) => {
        if (s.orcado === null || s.orcado === undefined) { ativo = false; return; }
        d += `${ativo ? 'L' : 'M'}${MARGEM.e + larg * (i + 0.5)} ${y(s.orcado)} `;
        ativo = true;
    });
    if (d) raiz.append(svg('path', {class: 'g-linha g-orcado', d: d.trim()}));
    serie.forEach((s, i) => {
        if (s.orcado === null || s.orcado === undefined) return;
        raiz.append(svg('circle', {class: 'g-ponto g-orcado', cx: MARGEM.e + larg * (i + 0.5), cy: y(s.orcado), r: 3.5}, dica(`${competencia(s.competencia, true)}: orçado ${moeda(s.orcado)}`)));
    });
    rotulosX(raiz, serie, MARGEM.e, larg);
    return raiz;
}
