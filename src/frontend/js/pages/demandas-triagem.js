import {get, post} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, confirmar, estadoVazio, toast, tratarErro} from '../ui.js';
import {opcao} from './finops-comum.js';
import {badgePrioridade, dataHora, selecionarPrioridade, semPermissao} from './demandas-comum.js';

export const demandasTriagem = {
    titulo: 'Triagem',
    subtitulo: 'Classifique as demandas novas em um grupo de destino',
    async render(container, signal) {
        if (!podeEscrever()) { container.replaceChildren(semPermissao()); return; }
        const lista = h('div', {});

        async function carregar() {
            const grupos = await get('/api/v1/grupos', undefined, signal);
            if (signal.aborted) return;
            const triagem = grupos.find(g => g.sistema);
            const itens = triagem
                ? await get('/api/v1/demandas', {status: 'ABERTA', grupo_id: triagem.id}, signal) : [];
            if (signal.aborted) return;
            const destinos = grupos.filter(g => g.ativo && !g.sistema);
            if (!destinos.length) {
                lista.replaceChildren(estadoVazio('Nenhum grupo de destino',
                    'Crie ao menos um grupo ativo para classificar as demandas.',
                    h('a', {class: 'botao', href: '#/config/grupos', text: 'Ir para Grupos'})));
                return;
            }
            if (!itens.length) { lista.replaceChildren(estadoVazio('Triagem vazia', 'Nenhuma demanda aguardando classificação.')); return; }
            lista.replaceChildren(...itens.map(d => linha(d, destinos)));
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
                grupo, prioridade,
                h('button', {type: 'submit'}, 'Classificar'),
                h('button', {type: 'button', class: 'secundario', on: {click: () => acao(d, 'concluir', 'Demanda concluída.')}}, 'Concluir'),
                h('button', {type: 'button', class: 'perigo', on: {click: async () => {
                    if (!await confirmar(`Cancelar a demanda "${d.titulo}"?`, 'Cancelar demanda')) return;
                    await acao(d, 'cancelar', 'Demanda cancelada.');
                }}}, 'Cancelar'));
            return h('section', {class: 'cartao dem-triagem-item'},
                h('div', {class: 'cartao-topo'}, h('strong', {text: d.titulo}), badgePrioridade(d.prioridade)),
                d.descricao ? h('p', {class: 'dem-descricao', text: d.descricao}) : null,
                h('p', {class: 'texto-suave', text: `Aberta em ${dataHora(d.created_at)} por ${d.solicitante_sub}`}),
                form);
        }

        container.replaceChildren(lista);
        await carregar();
    }
};
