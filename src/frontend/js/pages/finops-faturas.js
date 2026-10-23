import {get, post, patch, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, competencia, decimal, mesAtual, moeda, toast, tratarErro} from '../ui.js';
import {opcao, variacao} from './finops-comum.js';

const numeroOuNulo = texto => (texto === '' ? null : Number(texto));

export const finopsFaturas = {
    titulo: 'Faturas',
    subtitulo: 'Fontes de custo e acompanhamento do orçado × realizado',
    async render(container, signal) {
        const escrita = podeEscrever();
        const listaFontes = h('div', {});
        const listaFaturas = h('div', {});
        const formFonte = h('div', {});
        const formFatura = h('div', {});
        let fontes = [];
        const filtroFonte = h('select', {id: 'fat-fonte'}, opcao('', 'Todas as fontes'));
        const filtroDe = h('input', {type: 'month', id: 'fat-de'});
        const filtroAte = h('input', {type: 'month', id: 'fat-ate'});

        async function carregarFontes() {
            fontes = await get('/api/v1/finops/fontes', undefined, signal);
            if (signal.aborted) return;
            const atual = filtroFonte.value;
            filtroFonte.replaceChildren(opcao('', 'Todas as fontes'), ...fontes.map(f => opcao(f.id, f.nome)));
            filtroFonte.value = fontes.some(f => f.id === atual) ? atual : '';
            if (!fontes.length) {
                listaFontes.replaceChildren(estadoVazio('Nenhuma fonte de custo', 'Uma fonte é onde o custo aparece (ex.: Microsoft Fabric, AWS, licenças). Cadastre uma para lançar faturas.'));
                return;
            }
            listaFontes.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Fonte', 'Métrica de volume', 'Situação', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, fontes.map(f => h('tr', {class: f.ativo ? '' : 'inativa'},
                    h('td', {}, h('strong', {text: f.nome}), f.descricao ? h('div', {class: 'texto-suave pequeno-texto', text: f.descricao}) : null),
                    h('td', {text: f.metrica_nome ?? '—'}),
                    h('td', {}, h('span', {class: `badge ${f.ativo ? 'badge-resolvido' : ''}`, text: f.ativo ? 'Ativa' : 'Inativa'})),
                    escrita ? h('td', {class: 'acoes'},
                        h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editarFonte(f)}}, 'Editar'),
                        h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => excluirFonte(f)}}, 'Excluir')) : null))))));
        }

        async function carregarFaturas() {
            const itens = await get('/api/v1/finops/faturas', {fonte_id: filtroFonte.value, de: filtroDe.value, ate: filtroAte.value}, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                listaFaturas.replaceChildren(estadoVazio('Nenhuma fatura lançada', fontes.length ? 'Lance a fatura de um mês para comparar orçado e realizado.' : 'Cadastre uma fonte de custo primeiro.'));
                return;
            }
            listaFaturas.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Mês', 'Fonte', 'Orçado', 'Realizado', 'Variação', 'Métrica', 'Custo unitário', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(f => h('tr', {},
                    h('td', {text: competencia(f.competencia, true)}),
                    h('td', {}, f.fonte_nome, f.observacao ? h('div', {class: 'texto-suave pequeno-texto', text: f.observacao}) : null),
                    h('td', {class: 'num', text: f.valor_orcado === null ? '—' : moeda(f.valor_orcado)}),
                    h('td', {class: 'num', text: moeda(f.valor_realizado)}),
                    h('td', {}, variacao(f.variacao)),
                    h('td', {class: 'num', text: f.metrica_valor === null ? '—' : decimal(f.metrica_valor)}),
                    h('td', {class: 'num', text: f.custo_unitario === null ? '—' : moeda(f.custo_unitario)}),
                    escrita ? h('td', {class: 'acoes'},
                        h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editarFatura(f)}}, 'Editar'),
                        h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => excluirFatura(f)}}, 'Excluir')) : null))))));
        }

        async function recarregar() {
            try { await carregarFontes(); await carregarFaturas(); } catch (erro) { if (!signal.aborted) tratarErro(erro); }
        }

        async function excluirFonte(f) {
            if (!await confirmar(`Excluir a fonte "${f.nome}"? As faturas dela também serão removidas. Fontes ligadas a iniciativas não podem ser excluídas.`, 'Excluir')) return;
            try { await del(`/api/v1/finops/fontes/${f.id}`); toast('Fonte excluída.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }
        async function excluirFatura(f) {
            if (!await confirmar(`Excluir a fatura de ${competencia(f.competencia, true)} de "${f.fonte_nome}"?`, 'Excluir')) return;
            try { await del(`/api/v1/finops/faturas/${f.id}`); toast('Fatura excluída.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function editarFonte(f = null) {
            const nome = h('input', {type: 'text', required: true, maxLength: 120, value: f?.nome ?? ''});
            const descricao = h('input', {type: 'text', value: f?.descricao ?? ''});
            const metrica = h('input', {type: 'text', maxLength: 80, placeholder: 'ex.: Usuários ativos', value: f?.metrica_nome ?? ''});
            const ativo = h('input', {type: 'checkbox', checked: f ? f.ativo : true});
            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {nome: nome.value.trim(), descricao: descricao.value.trim() || null, metrica_nome: metrica.value.trim() || null};
                try {
                    if (f) await patch(`/api/v1/finops/fontes/${f.id}`, {...corpo, ativo: ativo.checked}); else await post('/api/v1/finops/fontes', corpo);
                    formFonte.replaceChildren();
                    toast(f ? 'Fonte atualizada.' : 'Fonte criada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {text: f ? 'Editar fonte de custo' : 'Nova fonte de custo'}),
                campo('Nome', nome), campo('Métrica de volume (opcional)', metrica), campo('Descrição (opcional)', descricao),
                f ? h('label', {class: 'campo-check'}, ativo, ' Ativa') : null,
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formFonte.replaceChildren()}}, 'Cancelar')));
            formFonte.replaceChildren(h('section', {class: 'cartao'}, form));
            nome.focus();
        }

        function editarFatura(f = null) {
            const ativas = fontes.filter(x => x.ativo || x.id === f?.fonte_id);
            if (!ativas.length) { toast('Cadastre uma fonte de custo antes de lançar faturas.', 'error'); return; }
            const fonte = h('select', {required: true, disabled: Boolean(f)}, ativas.map(x => opcao(x.id, x.nome)));
            fonte.value = f?.fonte_id ?? filtroFonte.value ?? ativas[0].id;
            if (!fonte.value) fonte.value = ativas[0].id;
            const comp = h('input', {type: 'month', required: true, value: f?.competencia ?? mesAtual()});
            const orcado = h('input', {type: 'number', min: 0, step: 0.01, value: f?.valor_orcado ?? ''});
            const realizado = h('input', {type: 'number', min: 0, step: 0.01, required: true, value: f?.valor_realizado ?? ''});
            const metricaValor = h('input', {type: 'number', min: 0, step: 0.01, value: f?.metrica_valor ?? ''});
            const obs = h('input', {type: 'text', value: f?.observacao ?? ''});
            const rotuloMetrica = h('span', {});
            const campoMetrica = h('label', {class: 'campo'}, rotuloMetrica, metricaValor);
            const atualizarMetrica = () => {
                const nome = fontes.find(x => x.id === fonte.value)?.metrica_nome;
                rotuloMetrica.textContent = nome ? `${nome} (para custo unitário)` : 'Volume da métrica (opcional)';
            };
            fonte.addEventListener('change', atualizarMetrica);
            atualizarMetrica();
            const form = h('form', {class: 'formulario', on: {submit: async evento => {
                evento.preventDefault();
                const corpo = {competencia: comp.value, valor_orcado: numeroOuNulo(orcado.value), valor_realizado: Number(realizado.value),
                    metrica_valor: numeroOuNulo(metricaValor.value), observacao: obs.value.trim() || null};
                try {
                    if (f) await patch(`/api/v1/finops/faturas/${f.id}`, corpo); else await post('/api/v1/finops/faturas', {...corpo, fonte_id: fonte.value});
                    formFatura.replaceChildren();
                    toast(f ? 'Fatura atualizada.' : 'Fatura lançada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
                h('h2', {text: f ? 'Editar fatura' : 'Nova fatura'}),
                campo('Fonte de custo', fonte), campo('Competência', comp), campo('Orçado (R$, opcional)', orcado),
                campo('Realizado (R$)', realizado), campoMetrica, campo('Observação (opcional)', obs),
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => formFatura.replaceChildren()}}, 'Cancelar')));
            formFatura.replaceChildren(h('section', {class: 'cartao'}, form));
            realizado.focus();
        }

        for (const c of [filtroFonte, filtroDe, filtroAte]) c.addEventListener('change', () => carregarFaturas().catch(erro => { if (!signal.aborted) tratarErro(erro); }));

        container.replaceChildren(
            h('p', {class: 'regra-janela', role: 'note'}, h('strong', {text: 'Faturas só acompanham o custo. '}),
                'Elas não somam saving. Para registrar uma economia (ex.: renegociação, desligar recurso), crie uma iniciativa de otimização de custo e aponte para a fonte. ',
                h('a', {href: '#/finops/iniciativas', text: 'Ir para Iniciativas'})),
            h('section', {class: 'cartao'},
                h('div', {class: 'cartao-topo'}, h('h2', {text: 'Fontes de custo'}),
                    escrita ? h('button', {type: 'button', class: 'pequeno', on: {click: () => editarFonte()}}, 'Nova fonte') : null),
                formFonte, listaFontes),
            h('section', {class: 'cartao'},
                h('div', {class: 'cartao-topo'}, h('h2', {text: 'Lançamentos de fatura'}),
                    escrita ? h('button', {type: 'button', class: 'pequeno', on: {click: () => editarFatura()}}, 'Nova fatura') : null),
                h('div', {class: 'filtros filtros-linha'}, campo('Fonte', filtroFonte), campo('De', filtroDe), campo('Até', filtroAte)),
                formFatura, listaFaturas));
        await recarregar();
    }
};
