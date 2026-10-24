import {h, icone} from '../ui.js';
import {opcao} from './finops-comum.js';

export const PRIORIDADES = [['ALTA', 'Alta'], ['MEDIA', 'Média'], ['BAIXA', 'Baixa']];
export const STATUS_DEMANDA = {ABERTA: 'Aberta', CONCLUIDA: 'Concluída', CANCELADA: 'Cancelada'};
export const rotuloPrioridade = valor => PRIORIDADES.find(([v]) => v === valor)?.[1] ?? valor;

export const selecionarPrioridade = (valor = 'MEDIA') => {
    const select = h('select', {}, PRIORIDADES.map(([v, t]) => opcao(v, t)));
    select.value = valor;
    return select;
};

export const badgePrioridade = valor => h('span', {class: `badge badge-prio-${String(valor).toLowerCase()}`, text: rotuloPrioridade(valor)});
export const badgeStatus = valor => h('span', {class: `badge badge-dem-${String(valor).toLowerCase()}`, text: STATUS_DEMANDA[valor] ?? valor});

// Idade relativa curta ("há 3 h"); o título completo fica no atributo title do elemento que a exibe.
export function idade(iso) {
    const t = iso ? new Date(iso).getTime() : NaN;
    if (Number.isNaN(t)) return '—';
    const min = Math.max(0, Math.floor((Date.now() - t) / 60000));
    if (min < 1) return 'agora';
    if (min < 60) return `há ${min} min`;
    const horas = Math.floor(min / 60);
    if (horas < 24) return `há ${horas} h`;
    const dias = Math.floor(horas / 24);
    return dias < 30 ? `há ${dias} ${dias === 1 ? 'dia' : 'dias'}` : dataHora(iso).split(' ')[0].replace(',', '');
}

// Classe do estado de prioridade usada no filete lateral de linhas e cartões.
export const classePrioridade = valor => `dem-prio-${String(valor).toLowerCase()}`;

// Ícone + texto discreto para metadados.
export const meta = (nome, texto, titulo) => h('span', {class: 'dem-meta-item', title: titulo}, icone(nome, {classe: 'icone-sm'}), h('span', {text: texto}));

export function dataHora(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
}

export const semPermissao = () => h('div', {class: 'estado-vazio'},
    h('div', {class: 'icone-vazio'}, icone('triangle-alert')),
    h('h3', {text: 'Acesso restrito'}),
    h('p', {text: 'Esta página exige permissão de edição.'}));
