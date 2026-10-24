import {get, post} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, carregando, confirmar, estadoVazio, icone, toast, tratarErro} from '../ui.js';
import {opcao} from './finops-comum.js';
import {badgePrioridade, classePrioridade, dataHora, idade, meta, selecionarPrioridade, semPermissao} from './demandas-comum.js';

export const demandasTriagem = {
    titulo: 'Triagem',
    subtitulo: 'Classifique as demandas novas em um grupo de destino',
    async render(container, signal) {
        if (!podeEscrever()) { container.replaceChildren(semPermissao()); return; }
        const lista = h('div', {}, carregando(3));
        const contagem = h('span', {class: 'badge', text: '…'});

        async function carregar() {
            const grupos = await get('/api/v1/grupos', undefined, signal);
            if (signal.aborted) return;
            const triagem = grupos.find(g => g.sistema);
            const itens = triagem
                ? await get('/api/v1/demandas', {status: 'ABERTA', grupo_id: triagem.id}, signal) : [];
            if (signal.aborted) return;
            const destinos = grupos.filter(g => g.ativo && !g.sistema);
            if (!destinos.length) {
                contagem.textContent = String(itens.length);
                lista.replaceChildren(estadoVazio({titulo: 'Nenhum grupo de destino', icone: 'users'},
                    'Crie ao menos um grupo ativo para classificar as demandas.',
                    h('a', {class: 'botao', href: '#/config/grupos', text: 'Ir para Grupos'})));
                return;
            }
            contagem.textContent = String(itens.length);
            if (!itens.length) {
                lista.replaceChildren(estadoVazio({titulo: 'Triagem vazia', icone: 'circle-check'},
                    'Nenhuma demanda aguardando classificação. Novas demandas aparecem aqui.',
                    h('a', {class: 'botao secundario', href: '#/demandas', text: 'Ver todas as demandas'})));
                return;
            }
            lista.replaceChildren(h('div', {class: 'dem-fila'}, itens.map(d => linha(d, destinos))));
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        async function acao(d, caminho, mensagem) {
            try { await post(`/api/v1/demandas/${d.id}/${caminho}`); toast(mensagem, 'success'); await recarregar(); }
            catch (erro) { tratarErro(erro); }
        }

        function linha(d, destinos) {
            const grupo = h('select', {required: true, 'aria-label': 'Grupo de destino'},
                opcao('', 'Selecione o grupo…'), destinos.map(g => opcao(g.id, g.nome)));
            const prioridade = selecionarPrioridade(d.prioridade);
            prioridade.setAttribute('aria-label', 'Prioridade');
            const form = h('form', {class: 'dem-triagem-acoes', on: {submit: async evento => {
                evento.preventDefault();
                if (!grupo.value) return;
                try {
                    await post(`/api/v1/demandas/${d.id}/classificar`, {grupo_id: grupo.value, prioridade: prioridade.value});
                    toast('Demanda classificada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('div', {class: 'dem-triagem-destino'},
                    h('label', {class: 'campo dem-triagem-grupo'}, h('span', {text: 'Classificar para o grupo'}), grupo),
                    h('label', {class: 'campo'}, h('span', {text: 'Prioridade'}), prioridade),
                    h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Classificar')),
                h('div', {class: 'dem-triagem-extra'},
                    h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => acao(d, 'concluir', 'Demanda concluída.')}}, icone('circle-check', {classe: 'icone-sm'}), 'Concluir'),
                    h('button', {type: 'button', class: 'fantasma pequeno dem-cancelar', on: {click: async () => {
                        if (!await confirmar(`Cancelar a demanda "${d.titulo}"?`, 'Cancelar demanda')) return;
                        await acao(d, 'cancelar', 'Demanda cancelada.');
                    }}}, icone('x', {classe: 'icone-sm'}), 'Cancelar')));
            return h('article', {class: `cartao dem-triagem-item ${classePrioridade(d.prioridade)}`},
                h('div', {class: 'dem-triagem-topo'},
                    h('a', {href: `#/demandas/${d.id}`, class: 'dem-link'}, h('strong', {text: d.titulo})), badgePrioridade(d.prioridade)),
                h('div', {class: 'dem-meta'},
                    meta('users', d.solicitante_sub, 'Solicitante'),
                    meta('calendar', idade(d.created_at), dataHora(d.created_at))),
                d.descricao ? h('p', {class: 'dem-descricao dem-resumo', text: d.descricao}) : null,
                form);
        }

        container.replaceChildren(
            h('div', {class: 'barra-acoes dem-barra'}, h('div', {},
                h('h2', {class: 'dem-titulo-lista'}, icone('list-filter'), 'Fila de triagem', contagem),
                h('p', {class: 'texto-suave pequeno-texto', text: 'Escolha o grupo de destino e confirme. Ajuste a prioridade se precisar.'}))),
            lista);
        await carregar();
    }
};
