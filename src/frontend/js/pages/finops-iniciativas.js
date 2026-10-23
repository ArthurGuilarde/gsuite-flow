import {get, post, put, del} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, confirmar, estadoVazio, competencia, decimal, mesAtual, moeda, pct, toast, tratarErro} from '../ui.js';
import {CUSTO_HORA_SUGERIDO, FREQUENCIAS, MODOS, ROTULO_TIPO, STATUS, TIPOS, badgeModo, badgeStatus, janela, opcao, textoPayback, selo} from './finops-comum.js';

const MAX_PARTICIPANTES = 20;
const numeroOuNulo = texto => (texto === '' || texto === null || texto === undefined ? null : Number(texto));
const numeroOuZero = texto => (texto === '' ? 0 : Number(texto));

// Select de perfil que preenche nome e custo/hora. "Personalizado" mantém os valores digitados.
function seletorPerfil(perfis, nomeAtual, custoAtual) {
    const sel = h('select', {}, opcao('', 'Personalizado'), perfis.map(p => opcao(p.id, `${p.nome} (${moeda(p.custo_hora)}/h)`)));
    const igual = perfis.find(p => p.nome === nomeAtual && Number(p.custo_hora) === Number(custoAtual));
    sel.value = igual?.id ?? '';
    return sel;
}

function linhaParticipante(p, perfis, aoMudar, aoRemover) {
    const padrao = perfis[0] ?? {nome: 'Analista', custo_hora: CUSTO_HORA_SUGERIDO};
    const nomeIni = p?.perfil_nome ?? padrao.nome, custoIni = p?.custo_hora ?? padrao.custo_hora;
    const sel = seletorPerfil(perfis, nomeIni, custoIni);
    const nome = h('input', {type: 'text', required: true, maxLength: 80, value: nomeIni});
    const custo = h('input', {type: 'number', required: true, min: 0, step: 0.01, value: custoIni});
    const qtd = h('input', {type: 'number', required: true, min: 1, step: 1, value: p?.qtd_pessoas ?? 1});
    const antes = h('input', {type: 'number', required: true, min: 0, step: 0.25, value: p?.horas_antes ?? ''});
    const depois = h('input', {type: 'number', required: true, min: 0, step: 0.25, value: p?.horas_depois ?? ''});
    const total = h('output', {class: 'participante-total', text: p ? `${moeda(p.valor_mensal)}/mês` : '—'});
    sel.addEventListener('change', () => {
        const perfil = perfis.find(x => x.id === sel.value);
        if (perfil) { nome.value = perfil.nome; custo.value = perfil.custo_hora; }
        aoMudar();
    });
    const personalizar = () => { sel.value = ''; };
    nome.addEventListener('input', personalizar);
    custo.addEventListener('input', personalizar);
    const raiz = h('div', {class: 'participante', role: 'group', 'aria-label': 'Participante'},
        campo('Perfil', sel), campo('Nome', nome), campo('Custo/hora (R$)', custo), campo('Pessoas', qtd),
        campo('Horas antes (por execução)', antes), campo('Horas depois (por execução)', depois),
        h('div', {class: 'participante-fim'},
            h('span', {class: 'texto-suave pequeno-texto', text: 'Saving mensal'}), total,
            h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => aoRemover(linha)}}, 'Remover')));
    const linha = {
        raiz,
        corpo: () => ({perfil_nome: nome.value.trim(), custo_hora: numeroOuZero(custo.value), qtd_pessoas: Math.round(Number(qtd.value)),
            horas_antes: numeroOuZero(antes.value), horas_depois: numeroOuZero(depois.value)}),
        total: v => { total.textContent = v === null ? '—' : `${moeda(v)}/mês`; }
    };
    return linha;
}

function cartaoPrevia() {
    const corpo = h('div', {class: 'previa-corpo'});
    const raiz = h('aside', {class: 'cartao previa', 'aria-live': 'polite'}, h('h2', {text: 'Prévia do cálculo'}), corpo);
    const mensagem = texto => corpo.replaceChildren(h('p', {class: 'texto-suave', text: texto}));
    mensagem('Preencha o formulário para ver o valor financeiro.');
    return {
        raiz, mensagem,
        erro: texto => corpo.replaceChildren(h('p', {class: 'erro', text: texto})),
        mostrar(c, modo) {
            const meses = c.meses_janela;
            corpo.replaceChildren(...[
                h('div', {class: 'mini-grade'},
                    selo('Valor por mês', moeda(c.valor_mensal), 'mini-destaque'),
                    selo(`Saving na janela (${meses} ${meses === 1 ? 'mês' : 'meses'})`, moeda(c.saving_janela)),
                    modo === 'POR_TEMPO' ? selo('Horas liberadas/mês', `${decimal(c.horas_mes)} h`) : null,
                    modo === 'POR_TEMPO' ? selo('FTE (horas ÷ 168)', decimal(c.fte)) : null,
                    modo === 'POR_TEMPO' ? selo('Redução de tempo', c.perc_reducao === null ? '—' : pct(c.perc_reducao)) : null,
                    selo('Investimento', moeda(c.investimento_total)),
                    selo('ROI na janela', c.roi_janela_pct === null ? 'Sem investimento' : pct(c.roi_janela_pct)),
                    selo('Payback', textoPayback(c.payback_meses), c.investimento_total > 0 ? (c.se_paga_na_janela ? 'mini-bom' : 'mini-ruim') : '')),
                c.investimento_total > 0 && c.payback_meses !== null
                    ? h('p', {class: c.se_paga_na_janela ? 'var-boa' : 'var-ruim', text: c.se_paga_na_janela ? 'Se paga dentro da janela.' : 'Só se paga depois da janela.'}) : null,
                h('p', {class: 'texto-suave pequeno-texto', text: `O saving conta até ${competencia(c.fim_janela, true)}; depois vira novo normal.`}),
                modo === 'POR_TEMPO' && c.valor_mensal < 0 ? h('p', {class: 'var-ruim', text: 'Atenção: o total é negativo (o time passa a gastar mais tempo).'}) : null].filter(Boolean));
        }
    };
}

export const finopsIniciativas = {
    titulo: 'Iniciativas',
    subtitulo: 'Melhorias, automações e otimizações com valor em R$',
    async render(container, signal) {
        const escrita = podeEscrever();
        const lista = h('div', {});
        const formulario = h('div', {});
        let perfis = [], fontes = [], despesas = [];
        let temporizador = null, controleSim = null, versaoSim = 0;
        const fTipo = h('select', {id: 'ini-tipo'}, opcao('', 'Todos os tipos'), TIPOS.map(([v, t]) => opcao(v, t)));
        const fStatus = h('select', {id: 'ini-status'}, opcao('', 'Todos os status'), Object.entries(STATUS).map(([v, [t]]) => opcao(v, t)));

        async function carregar() {
            const itens = await get('/api/v1/finops/iniciativas', {tipo: fTipo.value, status: fStatus.value, referencia: mesAtual()}, signal);
            if (signal.aborted) return;
            if (!itens.length) {
                lista.replaceChildren(estadoVazio('Nenhuma iniciativa', escrita ? 'Registre uma melhoria, automação ou otimização para demonstrar o valor financeiro da decisão.' : 'Peça a quem tem permissão de edição para cadastrar as iniciativas.'));
                return;
            }
            lista.replaceChildren(h('div', {class: 'tabela-wrap'}, h('table', {},
                h('thead', {}, h('tr', {}, ['Iniciativa', 'Status', 'Janela', 'Valor/mês', 'Saving acumulado', 'ROI / payback', escrita ? 'Ações' : null].map(t => t && h('th', {text: t})))),
                h('tbody', {}, itens.map(i => {
                    const c = i.calculo;
                    return h('tr', {class: c.status === 'ENCERRADA' || c.status === 'PLANEJADA' ? 'inativa' : ''},
                        h('td', {}, h('span', {class: 'rotina-titulo', text: i.titulo}),
                            h('div', {class: 'texto-suave pequeno-texto'}, `${ROTULO_TIPO[i.tipo] ?? i.tipo} · `, badgeModo(i.modo_calculo), i.fonte_nome ? ` · ${i.fonte_nome}` : '',
                            i.despesa_nome ? [' · ', h('a', {class: i.conversao_despesa ? 'badge selo-despesa' : '', href: '#/despesas/inventario', text: i.conversao_despesa ? `da despesa ${i.despesa_nome}` : `despesa: ${i.despesa_nome}`})] : null)),
                        h('td', {}, badgeStatus(c.status)),
                        h('td', {text: janela(i.mes_inicio, c.fim_janela)}),
                        h('td', {class: 'num', text: moeda(c.valor_mensal)}),
                        h('td', {class: 'num', text: moeda(c.saving_acumulado)}),
                        h('td', {}, c.investimento_total > 0
                            ? [`${c.roi_janela_pct === null ? '—' : pct(c.roi_janela_pct)} · ${textoPayback(c.payback_meses)}`, h('div', {class: c.se_paga_na_janela ? 'var-boa pequeno-texto' : 'var-ruim pequeno-texto', text: c.se_paga_na_janela ? 'Se paga na janela' : 'Fora da janela'})]
                            : h('span', {class: 'texto-suave', text: 'Sem investimento'})),
                        escrita ? h('td', {class: 'acoes'},
                            h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => editar(i)}}, 'Editar'),
                            i.conversao_despesa
                                ? h('span', {class: 'texto-suave pequeno-texto'}, 'Para desfazer, reverta pela ', h('a', {href: '#/despesas/inventario', text: 'despesa'}), '.')
                                : h('button', {type: 'button', class: 'perigo pequeno', on: {click: () => excluir(i)}}, 'Excluir')) : null);
                })))));
        }
        async function recarregar() { try { await carregar(); } catch (erro) { if (!signal.aborted) tratarErro(erro); } }

        async function excluir(i) {
            if (!await confirmar(`Excluir a iniciativa "${i.titulo}"? O saving dela deixa de aparecer no painel.`, 'Excluir')) return;
            try { await del(`/api/v1/finops/iniciativas/${i.id}`); toast('Iniciativa excluída.', 'success'); await recarregar(); } catch (erro) { tratarErro(erro); }
        }

        function editar(ini = null) {
            let modo = ini?.modo_calculo ?? 'DIRETO_REAIS';
            const titulo = h('input', {type: 'text', required: true, maxLength: 160, value: ini?.titulo ?? ''});
            const tipo = h('select', {}, TIPOS.map(([v, t]) => opcao(v, t)));
            tipo.value = ini?.tipo ?? 'MELHORIA';
            const descricao = h('textarea', {rows: 2});
            descricao.value = ini?.descricao ?? '';
            const fonte = h('select', {}, opcao('', 'Nenhuma'), fontes.filter(f => f.ativo || f.id === ini?.fonte_id).map(f => opcao(f.id, f.nome)));
            fonte.value = ini?.fonte_id ?? '';
            const despesa = h('select', {disabled: Boolean(ini?.conversao_despesa)}, opcao('', 'Nenhuma'), despesas.map(x => opcao(x.id, x.nome)));
            despesa.value = ini?.despesa_id ?? '';
            const inicio = h('input', {type: 'month', required: true, value: ini?.mes_inicio ?? mesAtual()});
            const janelaMeses = h('input', {type: 'number', required: true, min: 1, max: 60, step: 1, value: ini?.janela_meses ?? 6});
            const encerramento = h('input', {type: 'month', value: ini?.mes_encerramento ?? ''});
            const valorMensal = h('input', {type: 'number', required: true, min: 0, step: 0.01, value: ini?.valor_mensal ?? ''});
            const frequencia = h('select', {}, FREQUENCIAS.map(([v, t]) => opcao(v, t)));
            frequencia.value = ini?.frequencia ?? 'MENSAL';
            const invReais = h('input', {type: 'number', min: 0, step: 0.01, value: ini?.investimento_reais ?? 0});
            const invHoras = h('input', {type: 'number', min: 0, step: 0.25, value: ini?.investimento_horas ?? 0});
            const padrao = perfis[0]?.custo_hora ?? CUSTO_HORA_SUGERIDO;
            const invCusto = h('input', {type: 'number', min: 0, step: 0.01, value: ini && ini.investimento_custo_hora > 0 ? ini.investimento_custo_hora : padrao});
            const invPerfil = seletorPerfil(perfis, null, null);
            invPerfil.addEventListener('change', () => {
                const p = perfis.find(x => x.id === invPerfil.value);
                if (p) invCusto.value = p.custo_hora;
                agendar();
            });
            invCusto.addEventListener('input', () => { invPerfil.value = ''; });

            const previa = cartaoPrevia();
            const linhas = [];
            const listaParticipantes = h('div', {class: 'participantes'});
            const botaoAdd = h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => { adicionar(null); agendar(); }}}, 'Adicionar participante');
            function adicionar(p) {
                if (linhas.length >= MAX_PARTICIPANTES) return;
                const linha = linhaParticipante(p, perfis, agendar, remover);
                linhas.push(linha);
                listaParticipantes.append(linha.raiz);
                botaoAdd.disabled = linhas.length >= MAX_PARTICIPANTES;
            }
            function remover(linha) {
                linhas.splice(linhas.indexOf(linha), 1);
                linha.raiz.remove();
                botaoAdd.disabled = false;
                agendar();
            }
            for (const p of ini?.participantes ?? []) adicionar(p);
            if (!ini) adicionar(null);

            const blocoDireto = h('fieldset', {class: 'bloco'},
                h('legend', {text: 'Economia direta'}),
                campo('Economia por mês (R$)', valorMensal),
                h('p', {class: 'texto-suave pequeno-texto', text: 'Dinheiro que deixa de sair (fatura, contrato, licença). Ex.: renegociar um plano ou desligar um recurso.'}));
            const dicaPerfis = perfis.length ? 'Escolha um perfil para preencher nome e custo/hora; os valores ficam copiados nesta iniciativa.'
                : `Nenhum perfil cadastrado: sugerimos ${moeda(CUSTO_HORA_SUGERIDO)}/h. Cadastre perfis em Configuração > Perfis de custo/hora.`;
            const blocoTempo = h('fieldset', {class: 'bloco'},
                h('legend', {text: 'Horas do time'}),
                campo('Frequência de execução', frequencia),
                h('p', {class: 'texto-suave pequeno-texto', text: `Informe, por execução, as horas antes e depois da melhoria. ${dicaPerfis}`}),
                listaParticipantes, h('div', {class: 'acoes'}, botaoAdd));

            const chipsModo = MODOS.map(([valor, rotulo]) => h('button', {
                type: 'button', class: 'chip', 'aria-pressed': 'false',
                on: {click: () => { modo = valor; alternar(); agendar(); }}
            }, rotulo));
            function alternar() {
                MODOS.forEach(([valor], i) => {
                    chipsModo[i].classList.toggle('ativo', valor === modo);
                    chipsModo[i].setAttribute('aria-pressed', String(valor === modo));
                });
                blocoDireto.disabled = modo !== 'DIRETO_REAIS';
                blocoTempo.disabled = modo !== 'POR_TEMPO';
                blocoDireto.hidden = modo !== 'DIRETO_REAIS';
                blocoTempo.hidden = modo !== 'POR_TEMPO';
            }

            function montarCorpo() {
                const direto = modo === 'DIRETO_REAIS';
                return {
                    titulo: titulo.value.trim(), descricao: descricao.value.trim() || null, tipo: tipo.value, modo_calculo: modo,
                    valor_mensal: direto ? numeroOuNulo(valorMensal.value) : null,
                    frequencia: direto ? null : frequencia.value,
                    participantes: direto ? [] : linhas.map(l => l.corpo()),
                    mes_inicio: inicio.value, janela_meses: Math.round(Number(janelaMeses.value)),
                    mes_encerramento: encerramento.value || null, fonte_id: fonte.value || null, despesa_id: despesa.value || null,
                    investimento_reais: numeroOuZero(invReais.value), investimento_horas: numeroOuZero(invHoras.value),
                    investimento_custo_hora: numeroOuZero(invCusto.value)
                };
            }

            function agendar() {
                clearTimeout(temporizador);
                temporizador = setTimeout(simular, 300);
            }
            async function simular() {
                const corpo = montarCorpo();
                if (!corpo.mes_inicio || !(corpo.janela_meses >= 1)) return previa.mensagem('Informe o mês de início e a janela.');
                if (modo === 'DIRETO_REAIS' && corpo.valor_mensal === null) return previa.mensagem('Informe a economia por mês para ver a prévia.');
                if (modo === 'POR_TEMPO' && !corpo.participantes.length) return previa.mensagem('Adicione ao menos um participante.');
                if (corpo.participantes.some(p => !p.perfil_nome || !(p.qtd_pessoas >= 1))) return previa.mensagem('Complete nome e quantidade de cada participante.');
                controleSim?.abort();
                const meu = new AbortController();
                controleSim = meu;
                const versao = ++versaoSim;
                const aoAbortarPagina = () => meu.abort();
                signal.addEventListener('abort', aoAbortarPagina, {once: true});
                try {
                    const res = await post(`/api/v1/finops/simular?referencia=${encodeURIComponent(mesAtual())}`, {...corpo, titulo: corpo.titulo || 'Prévia', fonte_id: null, despesa_id: null}, meu.signal);
                    if (versao !== versaoSim) return;
                    previa.mostrar(res.calculo, modo);
                    linhas.forEach((l, i) => l.total(res.participantes?.[i]?.valor_mensal ?? null));
                } catch (erro) {
                    if (meu.signal.aborted || versao !== versaoSim) return;
                    previa.erro(erro.message);
                } finally {
                    signal.removeEventListener('abort', aoAbortarPagina);
                }
            }

            const form = h('form', {class: 'formulario-iniciativa', on: {submit: async evento => {
                evento.preventDefault();
                clearTimeout(temporizador);
                const corpo = montarCorpo();
                try {
                    if (ini) await put(`/api/v1/finops/iniciativas/${ini.id}`, corpo); else await post('/api/v1/finops/iniciativas', corpo);
                    controleSim?.abort();
                    formulario.replaceChildren();
                    toast(ini ? 'Iniciativa atualizada.' : 'Iniciativa criada.', 'success');
                    await recarregar();
                } catch (erro) { tratarErro(erro); }
            }, input: agendar, change: agendar}},
                h('h2', {text: ini ? 'Editar iniciativa' : 'Nova iniciativa'}),
                h('div', {class: 'formulario'}, campo('Título', titulo), campo('Tipo', tipo), campo('Fonte de custo (opcional)', fonte), campo('Despesa vinculada (opcional)', despesa)),
                ini?.conversao_despesa ? h('p', {class: 'regra-janela', role: 'note'}, `Iniciativa gerada pela despesa "${ini.despesa_nome}": o vínculo é fixo e a exclusão é feita revertendo a ação na despesa.`) : null,
                h('div', {class: 'formulario'}, campo('Descrição (opcional)', descricao)),
                h('div', {class: 'campo'}, h('span', {text: 'Como medir o valor'}), h('div', {class: 'chips', role: 'group', 'aria-label': 'Modo de cálculo'}, chipsModo)),
                blocoDireto, blocoTempo,
                h('fieldset', {class: 'bloco'},
                    h('legend', {text: 'Janela de saving'}),
                    h('div', {class: 'formulario'}, campo('Mês de início', inicio), campo('Janela (meses, 1–60)', janelaMeses), campo('Encerramento (opcional)', encerramento)),
                    h('p', {class: 'texto-suave pequeno-texto', text: 'O saving soma durante a janela (padrão 6 meses); depois vira novo normal. O encerramento antecipado interrompe a soma.'})),
                h('fieldset', {class: 'bloco'},
                    h('legend', {text: 'Investimento (opcional)'}),
                    h('div', {class: 'formulario'},
                        campo('Investimento em R$', invReais), campo('Horas do time investidas', invHoras),
                        campo('Perfil do custo/hora', invPerfil), campo('Custo/hora das horas (R$)', invCusto))),
                h('div', {class: 'acoes'},
                    h('button', {type: 'submit'}, 'Salvar'),
                    h('button', {type: 'button', class: 'secundario', on: {click: () => { clearTimeout(temporizador); controleSim?.abort(); formulario.replaceChildren(); }}}, 'Cancelar')));
            alternar();
            formulario.replaceChildren(h('section', {class: 'cartao'}, h('div', {class: 'form-previa'}, form, previa.raiz)));
            titulo.focus();
            simular();
        }

        for (const c of [fTipo, fStatus]) c.addEventListener('change', recarregar);
        container.replaceChildren(
            h('p', {class: 'regra-janela', role: 'note'}, h('strong', {text: 'Como o saving é contado: '}), 'soma por N meses (padrão 6) a partir do início; depois vira novo normal e deixa de somar no período.'),
            h('div', {class: 'barra-acoes'},
                h('div', {class: 'acoes'}, escrita ? h('button', {type: 'button', on: {click: () => editar()}}, 'Nova iniciativa') : null),
                h('div', {class: 'filtros'}, campo('Tipo', fTipo), campo('Status', fStatus))),
            formulario, lista);
        [perfis, fontes, despesas] = await Promise.all([
            get('/api/v1/finops/perfis', undefined, signal).then(l => l.filter(p => p.ativo)),
            get('/api/v1/finops/fontes', undefined, signal),
            get('/api/v1/despesas', undefined, signal).catch(() => [])]);
        await carregar();
        return () => { clearTimeout(temporizador); controleSim?.abort(); };
    }
};
