import {h, icone, moeda, competencia} from '../ui.js';

export const TIPOS = [['MELHORIA', 'Melhoria'], ['AUTOMACAO', 'Automação'], ['OTIMIZACAO_CUSTO', 'Otimização de custo']];
export const ROTULO_TIPO = Object.fromEntries(TIPOS);
export const MODOS = [['DIRETO_REAIS', 'Economia direta em R$'], ['POR_TEMPO', 'Horas do time']];
export const ROTULO_MODO = {DIRETO_REAIS: 'Direto (R$)', POR_TEMPO: 'Horas do time'};
export const FREQUENCIAS = [
    ['DIARIA_UTIL', 'Diária (dias úteis, 22/mês)'], ['DIARIA_CORRIDA', 'Diária (30/mês)'],
    ['SEMANAL', 'Semanal (4,33/mês)'], ['QUINZENAL', 'Quinzenal (2/mês)'], ['MENSAL', 'Mensal (1/mês)']
];
export const STATUS = {
    PLANEJADA: ['Planejada', 'planejada'], EM_SAVING: ['Em saving', 'em-saving'],
    NOVO_NORMAL: ['Novo normal', 'novo-normal'], ENCERRADA: ['Encerrada', 'encerrada']
};
export const CUSTO_HORA_SUGERIDO = 80;
export const REGRA_JANELA = 'Cada iniciativa soma saving por N meses (padrão 6) a partir do início; depois vira novo normal e deixa de somar no período.';

export const opcao = (valor, texto = valor) => h('option', {value: valor, text: texto});

export function badgeStatus(status) {
    const [texto, classe] = STATUS[status] ?? [status, 'planejada'];
    return h('span', {class: `badge status status-${classe}`, text: texto});
}

export const badgeModo = modo => h('span', {class: `badge modo modo-${String(modo).toLowerCase().replace('_', '-')}`, text: ROTULO_MODO[modo] ?? modo});

// Variação = orçado − realizado: positivo é abaixo do orçado (bom).
export function variacao(valor) {
    if (valor === null || valor === undefined) return h('span', {class: 'texto-suave', text: '—'});
    const classe = valor > 0 ? 'var-boa' : valor < 0 ? 'var-ruim' : '';
    const texto = valor > 0 ? `${moeda(valor)} abaixo` : valor < 0 ? `${moeda(Math.abs(valor))} acima` : 'No orçado';
    return h('span', {class: classe, text: texto});
}

export function textoPayback(meses) {
    if (meses === null || meses === undefined) return 'Não se paga (sem saving)';
    if (meses === 0) return 'Imediato (sem investimento)';
    return meses === 1 ? '1 mês' : `${meses} meses`;
}

export const janela = (inicio, fim) => `${competencia(inicio)} → ${competencia(fim)}`;

export function selo(rotulo, valor, classe = '') {
    return h('div', {class: `mini ${classe}`}, h('span', {class: 'mini-rotulo', text: rotulo}), h('strong', {class: 'mini-valor', text: valor}));
}

// Nota informativa (regra de negócio) com ícone; `filhos` pode misturar texto, <strong> e links.
export const nota = (...filhos) => h('p', {class: 'regra-janela', role: 'note'}, icone('info'), h('span', {}, filhos));

// Cartão de indicador. `valor` pode ser texto ou Node; `nomeIcone` vem do sprite.
export function kpi(nomeIcone, rotulo, valor, classe = '', ...detalhes) {
    return h('div', {class: `kpi kpi-fin ${classe}`.trim()},
        h('span', {class: 'kpi-rotulo'}, icone(nomeIcone, {classe: 'icone-sm'}), rotulo),
        h('strong', {class: 'kpi-valor'}, valor),
        detalhes.filter(Boolean).map(d => h('span', {class: 'kpi-detalhe', text: d})));
}

// <thead>: cada coluna é "Texto", ["Texto", true] (numérica, à direita) ou falsa (omitida).
export const cabecalho = colunas => h('thead', {}, h('tr', {}, colunas.map(c => c && (Array.isArray(c)
    ? h('th', {class: c[1] ? 'num' : '', text: c[0]})
    : h('th', {text: c})))));

// Botões só-ícone para linhas de tabela (aria-label obrigatório).
export const botaoEditar = (alvo, aoClicar) => h('button', {type: 'button', class: 'secundario so-icone pequeno', 'aria-label': `Editar ${alvo}`, title: 'Editar', on: {click: aoClicar}}, icone('pencil', {classe: 'icone-sm'}));
export const botaoExcluir = (alvo, aoClicar) => h('button', {type: 'button', class: 'secundario perigo so-icone pequeno', 'aria-label': `Excluir ${alvo}`, title: 'Excluir', on: {click: aoClicar}}, icone('trash-2', {classe: 'icone-sm'}));
