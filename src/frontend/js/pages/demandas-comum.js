import {h} from '../ui.js';
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

export function dataHora(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
}

export const semPermissao = () => h('p', {class: 'texto-suave', text: 'Esta página exige permissão de edição.'});
