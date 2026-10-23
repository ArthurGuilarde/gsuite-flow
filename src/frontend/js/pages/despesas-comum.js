import {h, competencia, data, moeda, tratarErro} from '../ui.js';

export const CATEGORIAS_SUGERIDAS = ['SaaS & Ferramentas', 'Infraestrutura & Cloud', 'Consultoria & Terceiros', 'Licenças & Software', 'Pessoal & Treinamentos', 'Outros Serviços'];
export const TIPOS_CUSTO = [['RECORRENTE_MENSAL', 'Recorrente mensal'], ['PONTUAL', 'Pontual (valor total)']];
export const ROTULO_TIPO_CUSTO = Object.fromEntries(TIPOS_CUSTO);
export const STATUS_DESPESA = {
    EM_REVISAO: ['Em revisão', 'em-revisao'], VALIDADO: ['Validado', 'validado'], DESPERDICIO: ['Desperdício', 'desperdicio'],
    CANCELADO: ['Cancelado', 'cancelado'], RENEGOCIADO: ['Renegociado', 'renegociado']
};
// Status que o usuário pode escolher direto; cancelar/renegociar passam pelas ações.
export const STATUS_EDITAVEIS = ['EM_REVISAO', 'VALIDADO', 'DESPERDICIO'];
export const JANELA_PADRAO = 6;
export const URL_INICIATIVAS = '#/finops/iniciativas';

export function badgeDespesa(status) {
    const [texto, classe] = STATUS_DESPESA[status] ?? [status, 'em-revisao'];
    return h('span', {class: `badge dsp dsp-${classe}`, text: texto});
}

// Soma n meses a um "YYYY-MM".
export function somarMeses(ym, n) {
    const [a, m] = String(ym).split('-').map(Number);
    const total = a * 12 + (m - 1) + n;
    return `${Math.floor(total / 12)}-${String(total % 12 + 1).padStart(2, '0')}`;
}

export const textoOuNulo = texto => (texto.trim() === '' ? null : texto.trim());
export const numeroOuNulo = texto => (texto === '' || texto === null || texto === undefined ? null : Number(texto));

// Selo "fatura"/"contrato" da origem do custo considerado.
export function seloOrigem(despesa) {
    if (despesa.tipo_custo === 'PONTUAL') return null;
    const fatura = despesa.origem_custo === 'FATURA';
    const titulo = fatura ? `Realizado da fatura de ${competencia(despesa.competencia_fatura, true)}` : 'Valor contratado';
    return h('span', {class: `badge origem ${fatura ? 'origem-fatura' : 'origem-contrato'}`, title: titulo, text: fatura ? 'fatura' : 'contrato'});
}

// Situação da renovação: texto + classe. Cancelada não renova.
export function situacaoRenovacao(despesa) {
    if (!despesa.data_renovacao || despesa.status_auditoria === 'CANCELADO') return null;
    const dias = despesa.dias_para_renovacao;
    if (dias === null || dias === undefined) return {texto: data(despesa.data_renovacao), classe: ''};
    if (dias < 0) return {texto: `Vencida há ${-dias} ${dias === -1 ? 'dia' : 'dias'}`, classe: 'ren-vencida'};
    const texto = dias === 0 ? 'Renova hoje' : `Renova em ${dias} ${dias === 1 ? 'dia' : 'dias'}`;
    return {texto, classe: dias <= 30 ? 'ren-urgente' : dias <= 60 ? 'ren-atencao' : ''};
}

// Janela do saving: "nov/26 → abr/27".
export const intervaloJanela = (inicio, meses) => `${competencia(inicio)} → ${competencia(somarMeses(inicio, meses - 1))}`;

// Diálogo modal com formulário. `montar(fechar)` devolve {corpo, aoEnviar}; aoEnviar pode lançar erro (diálogo permanece aberto).
export function abrirDialogo(titulo, corpo, rotulo, aoEnviar, perigo = false) {
    const dialogo = h('dialog', {class: 'modal modal-largo', 'aria-label': titulo});
    const enviar = h('button', {type: 'submit', class: perigo ? 'perigo' : ''}, rotulo);
    const form = h('form', {class: 'formulario-modal', on: {submit: async evento => {
        evento.preventDefault();
        enviar.disabled = true;
        try { await aoEnviar(); dialogo.close('ok'); } catch (erro) { tratarErro(erro); } finally { enviar.disabled = false; }
    }}},
    h('h2', {text: titulo}), corpo,
    h('div', {class: 'acoes'}, h('button', {type: 'button', class: 'secundario', on: {click: () => dialogo.close('cancel')}}, 'Cancelar'), enviar));
    dialogo.append(form);
    dialogo.addEventListener('close', () => dialogo.remove(), {once: true});
    document.body.append(dialogo);
    dialogo.showModal();
    return {dialogo, enviar};
}

export const linhaValor = (rotulo, valor, classe = '') => h('div', {class: `linha-valor ${classe}`}, h('span', {text: rotulo}), h('strong', {text: valor}));

export const moedaMes = valor => `${moeda(valor)}/mês`;
