import {get, put, post, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, icone, competencia, hojeLocal, mesAtual, moeda, toast, tratarErro} from '../ui.js';
import {botaoExcluir, cabecalho, kpi, nota, variacao} from './finops-comum.js';
import {textoOuNulo} from './despesas-comum.js';

// Mesma regra do backend: 11 parcelas de round(v/12, 2) e dezembro com o resto (em centavos, sem erro de ponto flutuante).
function parcelasAnual(valor) {
    const centavos = Math.round(valor * 100);
    const parcela = Math.round(centavos / 12);
    return {parcela: parcela / 100, dezembro: (centavos - parcela * 11) / 100};
}

export const despesasOrcamento = {
    titulo: 'Orçamento de despesas',
    subtitulo: 'Meta mensal por competência, comparada ao run-rate e aos custos pontuais',
    async render(container, signal) {
        const escrita = podeEscrever();
        const ano = h('input', {type: 'number', id: 'orc-ano', min: 2000, max: 2100, step: 1, value: mesAtual().slice(0, 4), required: true});
        const grade = h('div', {});
        const anual = h('div', {});

        async function carregar() {
            const a = Math.round(Number(ano.value));
            if (!(a >= 2000 && a <= 2100)) return;
            grade.replaceChildren(carregando(3));
            const referencia = `${a}-12`;
            const [orcamentos, painel] = await Promise.all([
                get('/api/v1/despesas/orcamentos', {ano: a}, signal),
                get('/api/v1/despesas/dashboard', {referencia, hoje: hojeLocal()}, signal)]);
            if (signal.aborted) return;
            const porMes = new Map(orcamentos.map(o => [String(o.competencia).slice(0, 7), o]));
            const serie = new Map(painel.serie.map(s => [String(s.competencia).slice(0, 7), s]));
            const totalOrcado = orcamentos.reduce((s, o) => s + o.valor, 0);
            const totalGasto = painel.serie.reduce((s, x) => s + x.total, 0);
            grade.replaceChildren(
                h('div', {class: 'kpis kpis-fin'},
                    kpi('calculator', `Orçado em ${a}`, moeda(totalOrcado), '', `${orcamentos.length} de 12 meses cadastrados`),
                    kpi('wallet', `Run-rate + pontuais em ${a}`, moeda(totalGasto), 'kpi-neutro', 'Soma dos 12 meses'),
                    kpi('trending-up', 'Variação (orçado − previsto)', orcamentos.length ? variacao(totalOrcado - totalGasto) : 'Sem orçamento', 'kpi-resolvido')),
                h('div', {class: 'tabela-wrap'}, h('table', {class: 'tabela-orcamento tabela-fin'},
                    cabecalho(['Mês', ['Orçado (R$)', true], 'Observação', ['Run-rate (recorrente)', true], ['Pontual', true], ['Total', true], ['Variação', true], escrita ? ['Ações', true] : null]),
                    h('tbody', {}, Array.from({length: 12}, (_, i) => linhaMes(a, i + 1, porMes, serie))))));
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        function linhaMes(a, m, porMes, serie) {
            const chave = `${a}-${String(m).padStart(2, '0')}`;
            const o = porMes.get(chave), s = serie.get(chave);
            const valor = h('input', {type: 'number', min: 0, step: 0.01, value: o?.valor ?? '', disabled: !escrita, 'aria-label': `Orçado de ${competencia(chave, true)}`});
            const obs = h('input', {type: 'text', maxLength: 200, value: o?.observacao ?? '', disabled: !escrita, 'aria-label': `Observação de ${competencia(chave, true)}`});
            async function salvar() {
                if (valor.value === '') { toast('Informe o valor orçado.', 'error'); return; }
                try {
                    await put(`/api/v1/despesas/orcamentos/${chave}`, {valor: Number(valor.value), observacao: textoOuNulo(obs.value)});
                    toast(`Orçamento de ${competencia(chave, true)} salvo.`, 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }
            async function remover() {
                try { await del(`/api/v1/despesas/orcamentos/${chave}`); toast(`Orçamento de ${competencia(chave, true)} removido.`, 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
            }
            return h('tr', {class: chave === mesAtual() ? 'mes-atual' : ''},
                h('td', {}, h('strong', {text: competencia(chave, true)}), chave === mesAtual() ? [' ', h('span', {class: 'badge badge-build', text: 'atual'})] : null),
                h('td', {}, valor), h('td', {}, obs),
                h('td', {class: 'num', text: s ? moeda(s.recorrente) : '—'}),
                h('td', {class: 'num', text: s ? moeda(s.pontual) : '—'}),
                h('td', {class: 'num', text: s ? moeda(s.total) : '—'}),
                h('td', {class: 'num'}, o ? variacao(s?.variacao ?? null) : h('span', {class: 'texto-suave', text: 'Sem orçamento'})),
                escrita ? h('td', {class: 'acoes'}, h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'pequeno', on: {click: salvar}}, icone('check', {classe: 'icone-sm'}), 'Salvar'),
                    o ? botaoExcluir(`orçamento de ${competencia(chave, true)}`, remover) : null)) : null);
        }

        function formularioAnual() {
            const valorAnual = h('input', {type: 'number', id: 'orc-anual', min: 0, step: 0.01, required: true});
            const sobrescrever = h('input', {type: 'checkbox', id: 'orc-sobrescrever'});
            const previa = h('p', {class: 'texto-suave pequeno-texto', 'aria-live': 'polite'});
            const atualizar = () => {
                if (valorAnual.value === '') { previa.textContent = 'Informe o orçamento anual para ver a divisão.'; return; }
                const {parcela, dezembro} = parcelasAnual(Number(valorAnual.value));
                previa.textContent = `11 meses de ${moeda(parcela)} e dezembro com ${moeda(dezembro)} (soma exata de ${moeda(Number(valorAnual.value))}).`;
            };
            valorAnual.addEventListener('input', atualizar);
            atualizar();
            return h('form', {class: 'cartao', on: {submit: async evento => {
                evento.preventDefault();
                const a = Math.round(Number(ano.value));
                try {
                    const r = await post('/api/v1/despesas/orcamentos/anual', {ano: a, valor_anual: Number(valorAnual.value), sobrescrever: sobrescrever.checked});
                    toast(`Orçamento de ${a}: ${r.criados} criados, ${r.atualizados} atualizados, ${r.ignorados} mantidos.`, 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }}},
            h('h2', {class: 'titulo-secao'}, icone('calculator'), 'Distribuir orçamento anual ÷ 12'),
            h('div', {class: 'formulario'},
                campo('Valor anual (R$)', valorAnual),
                h('label', {class: 'campo-check'}, sobrescrever, h('span', {text: 'Sobrescrever meses já cadastrados'}))),
            previa,
            h('p', {class: 'texto-suave pequeno-texto', text: 'Sem sobrescrever, meses que já têm orçamento são mantidos. O ano é o selecionado acima.'}),
            h('div', {class: 'acoes'}, h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Distribuir pelos 12 meses')));
        }

        ano.addEventListener('change', recarregar);
        if (escrita) anual.append(formularioAnual());
        container.replaceChildren(
            nota(h('strong', {text: 'Orçamento é opcional: '}), 'o painel e o inventário funcionam sem ele. Variação = orçado − (run-rate + pontuais); positivo é abaixo do orçado.'),
            h('div', {class: 'barra-acoes'}, h('div', {class: 'filtros'}, campo('Ano', ano))),
            anual, grade);
        await carregar();
    }
};
