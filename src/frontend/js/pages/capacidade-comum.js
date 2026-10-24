import {h, icone} from '../ui.js';

// Ícone do grupo (dado do usuário, normalmente emoji) em um quadro tingido com a cor do grupo.
export function tileGrupo(simbolo, cor) {
    const tile = h('span', {class: 'icone-tile', 'aria-hidden': 'true', text: simbolo || '•'});
    if (cor) { tile.dataset.cor = cor; tile.style.setProperty('--cor', cor); }
    return tile;
}

// Botões de linha só-ícone (editar/excluir), sempre com aria-label e title.
export function botaoEditar(rotulo, aoClicar) {
    return h('button', {type: 'button', class: 'secundario pequeno so-icone', title: rotulo, 'aria-label': rotulo, on: {click: aoClicar}}, icone('pencil', {classe: 'icone-sm'}));
}
export function botaoExcluir(rotulo, aoClicar, {desabilitado = false, dica = null} = {}) {
    return h('button', {type: 'button', class: 'secundario perigo pequeno so-icone', disabled: desabilitado, title: dica ?? rotulo, 'aria-label': rotulo, on: {click: aoClicar}}, icone('trash-2', {classe: 'icone-sm'}));
}

export const botaoNovo = (texto, aoClicar) =>
    h('button', {type: 'button', on: {click: aoClicar}}, icone('plus', {classe: 'icone-sm'}), texto);

export const cabecalhoTabela = (titulos, escrita, numericas = []) =>
    h('thead', {}, h('tr', {}, titulos.map(t => h('th', {class: numericas.includes(t) ? 'num' : null, text: t})),
        escrita ? h('th', {class: 'th-acoes', text: 'Ações'}) : null));

export const badgeSituacaoAtivo = (ativo, ligado = 'Ativo', desligado = 'Inativo') =>
    h('span', {class: `badge badge-ponto ${ativo ? 'badge-ativo' : ''}`, text: ativo ? ligado : desligado});
