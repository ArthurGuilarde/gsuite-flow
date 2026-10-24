import {del, get, patch, post, put} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, carregando, confirmar, data as formatarData, hojeLocal, icone, minutos, moeda, numero, toast, tratarErro} from '../ui.js';
import {badgeCategoria, dialogoConclusao, tituloComLink} from './rotinas.js';

const API = '/api/v1/planner';
const LIMITE_PRIORIDADES = 3;
const ATRASO_SALVAR_MS = 800;
const DIAS_HISTORICO = 30;

// Aritmética de datas sempre local (nunca toISOString, que converte para UTC).
function somarDias(iso, n) {
    const [a, m, d] = iso.split('-').map(Number);
    const dt = new Date(a, m - 1, d + n);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
}
const dataLocal = iso => { const [a, m, d] = iso.split('-').map(Number); return new Date(a, m - 1, d); };
const maiuscula = texto => `${texto.charAt(0).toUpperCase()}${texto.slice(1)}`;
const diaSemana = (iso, estilo = 'long') => maiuscula(dataLocal(iso).toLocaleDateString('pt-BR', {weekday: estilo}).replace('.', ''));
const diaMes = iso => iso.slice(8, 10) + '/' + iso.slice(5, 7);
const textoDias = n => (n === 0 ? 'hoje' : n === 1 ? 'amanhã' : `em ${n} dias`);

export const meuDia = {
    titulo: 'Meu Dia',
    subtitulo: 'Foco, prioridades e lembretes do que não pode ficar para trás',
    async render(container, signal) {
        const escrita = podeEscrever();
        const hoje = hojeLocal();
        let dataAtual = hoje;
        let view = null;
        let historico = [];
        let filtro = 'TODAS';
        let todasRotinas = false;
        let refocar = null;
        let sequencia = 0;
        let timer = null;
        let fila = Promise.resolve();
        const sujo = new Set();
        const selecionados = new Set();
        const indicadores = [];

        // ---------- Salvamento de foco e notas (debounce + versão otimista) ----------
        const indicador = () => {
            const el = h('span', {class: 'md-salvo texto-suave', 'aria-live': 'polite'});
            indicadores.push(el);
            return el;
        };
        const avisar = texto => { for (const el of indicadores) el.textContent = texto; };

        const focoInput = h('input', {
            type: 'text', class: 'md-foco-input', id: 'md-foco', maxLength: 500, readOnly: !escrita,
            placeholder: 'Qual é o foco de hoje?', 'aria-label': 'Foco do dia',
            on: {
                input: () => agendar('foco'),
                blur: () => flush(),
                keydown: evento => { if (evento.key === 'Enter') evento.target.blur(); }
            }
        });
        const notasArea = h('textarea', {
            class: 'md-notas', id: 'md-notas', rows: 7, maxLength: 20000, readOnly: !escrita,
            placeholder: 'Anotações livres, recados, ideias…', 'aria-label': 'Notas do dia',
            on: {input: () => agendar('notas'), blur: () => flush()}
        });

        function agendar(campoAlterado) {
            sujo.add(campoAlterado);
            avisar('Alterações pendentes…');
            clearTimeout(timer);
            timer = setTimeout(flush, ATRASO_SALVAR_MS);
        }
        function flush() {
            clearTimeout(timer);
            timer = null;
            fila = fila.then(gravar, gravar);
            return fila;
        }
        async function gravar() {
            if (!sujo.size || !view || signal.aborted) return;
            const campos = [...sujo];
            sujo.clear();
            const alvo = dataAtual;
            const corpo = {versao: view.dia.versao};
            if (campos.includes('foco')) corpo.foco = focoInput.value.trim() || null;
            if (campos.includes('notas')) corpo.notas = notasArea.value.trim() ? notasArea.value : null;
            avisar('Salvando…');
            try {
                const dia = await put(`${API}/dias/${alvo}`, corpo);
                if (signal.aborted || alvo !== dataAtual) return;
                view.dia = dia;
                avisar(sujo.size ? 'Alterações pendentes…' : 'Salvo');
                if (!historico.some(d => d.data === alvo)) await carregar();
            } catch (erro) {
                if (signal.aborted) return;
                if (erro.status === 409) {
                    toast('Este dia foi alterado em outra aba ou dispositivo. Recarregando a versão mais recente.', 'error');
                    sujo.clear();
                    await carregar(true);
                    avisar('');
                    return;
                }
                for (const c of campos) sujo.add(c);
                avisar('Não salvo');
                tratarErro(erro);
            }
        }

        // ---------- Operações ----------
        async function executar(acao, aposSucesso) {
            try {
                const resultado = await acao();
                if (signal.aborted) return null;
                aposSucesso?.(resultado);
                await carregar();
                return resultado ?? true;
            } catch (erro) {
                if (signal.aborted) return null;
                tratarErro(erro);
                await carregar();
                return null;
            }
        }
        const alterarItem = (item, corpo) => executar(() => patch(`${API}/itens/${item.id}`, corpo));
        const removerItem = item => executar(() => del(`${API}/itens/${item.id}`));
        async function adicionar(tipo, input) {
            const texto = input.value.trim();
            if (!texto) return;
            await flush();
            const ok = await executar(() => post(`${API}/dias/${dataAtual}/itens`, {tipo, texto}), () => { input.value = ''; });
            if (ok) refocar = tipo;
            aplicarFoco();
        }
        function aplicarFoco() {
            const alvo = refocar === 'PRIORIDADE' ? prioInput : refocar === 'TAREFA' ? tarInput : null;
            refocar = null;
            if (alvo && !alvo.closest('[hidden]')) alvo.focus();
        }
        async function irPara(iso) {
            if (!/^\d{4}-\d{2}-\d{2}$/.test(iso) || iso === dataAtual) return;
            await flush();
            if (signal.aborted) return;
            dataAtual = iso;
            selecionados.clear();
            filtro = 'TODAS';
            await carregar(true);
        }
        async function limparDia() {
            if (!await confirmar(`Apagar foco, notas e todos os itens de ${formatarData(dataAtual)}?`, 'Apagar dia')) return;
            sujo.clear();
            await executar(() => del(`${API}/dias/${dataAtual}`), () => toast('Dia apagado.', 'success'));
        }
        async function concluirRotina(o) {
            const extra = await dialogoConclusao(o);
            if (!extra || signal.aborted) return;
            await executar(() => put(`/api/v1/rotinas/${o.rotina_id}/execucao`, {
                semana_id: o.semana_id, ocorrencia: o.ocorrencia, status: 'CONCLUIDA',
                esforco_real_min: extra.esforco_real_min ?? null, observacao: extra.observacao ?? null
            }), () => toast('Rotina concluída.', 'success'));
        }
        async function trazer(ids) {
            await executar(() => post(`${API}/dias/${dataAtual}/trazer-pendentes`, ids ? {item_ids: ids} : {}), r => {
                selecionados.clear();
                const extra = r.como_tarefa ? ` (${numero(r.como_tarefa)} como tarefa: o dia já tinha ${LIMITE_PRIORIDADES} prioridades)` : '';
                toast(`${numero(r.trazidos)} ${r.trazidos === 1 ? 'item trazido' : 'itens trazidos'} para ${formatarData(dataAtual)}${extra}.`, 'success');
            });
        }
        async function descartar() {
            const ids = [...selecionados];
            if (!ids.length) return;
            if (!await confirmar(`Descartar ${ids.length} ${ids.length === 1 ? 'item pendente' : 'itens pendentes'}? Eles deixam de aparecer como pendentes.`, 'Descartar')) return;
            await executar(() => post(`${API}/dias/${dataAtual}/descartar-pendentes`, {item_ids: ids}), r => {
                selecionados.clear();
                toast(`${numero(r.descartados)} ${r.descartados === 1 ? 'item descartado' : 'itens descartados'}.`, 'success');
            });
        }

        // ---------- Esqueleto persistente (campos digitados não se perdem ao recarregar) ----------
        const cabecalho = h('section', {class: 'cartao md-hero', 'aria-label': 'Resumo do dia'});
        const prioLista = h('ul', {class: 'lista-limpa md-itens'});
        const prioInput = h('input', {type: 'text', maxLength: 500, placeholder: 'Adicionar prioridade e pressionar Enter', 'aria-label': 'Nova prioridade'});
        const prioForm = h('form', {class: 'md-add nao-imprimir', on: {submit: evento => { evento.preventDefault(); adicionar('PRIORIDADE', prioInput); }}},
            prioInput, h('button', {type: 'submit'}, icone('plus', {classe: 'icone-sm'}), 'Adicionar'));
        const prioNota = h('p', {class: 'texto-suave md-nota'});
        const prioContagem = h('span', {class: 'badge md-contagem'});
        const prioridades = h('section', {class: 'cartao md-prioridades', 'aria-labelledby': 'md-t-prio'},
            h('div', {class: 'cartao-topo'}, h('h2', {id: 'md-t-prio'}, icone('list-checks'), 'Prioridades'), prioContagem),
            prioLista, prioNota, escrita ? prioForm : null);

        const tarLista = h('ul', {class: 'lista-limpa md-itens'});
        const tarInput = h('input', {type: 'text', maxLength: 500, placeholder: 'Nova tarefa e pressionar Enter', 'aria-label': 'Nova tarefa'});
        const tarForm = h('form', {class: 'md-add nao-imprimir', on: {submit: evento => { evento.preventDefault(); adicionar('TAREFA', tarInput); }}},
            tarInput, h('button', {type: 'submit'}, icone('plus', {classe: 'icone-sm'}), 'Adicionar'));
        const tarContagem = h('span', {class: 'badge md-contagem'});
        const tarFiltros = h('div', {class: 'chips nao-imprimir', role: 'group', 'aria-label': 'Filtrar tarefas'});
        const tarefas = h('section', {class: 'cartao md-tarefas', 'aria-labelledby': 'md-t-tar'},
            h('div', {class: 'cartao-topo'}, h('h2', {id: 'md-t-tar'}, icone('list-todo'), 'Tarefas'), tarContagem), tarFiltros,
            escrita ? tarForm : null, tarLista);

        const notas = h('section', {class: 'cartao md-notas-cartao', 'aria-labelledby': 'md-t-notas'},
            h('div', {class: 'cartao-topo'}, h('h2', {id: 'md-t-notas'}, icone('message-square'), 'Notas'), indicador()), notasArea);

        const pendentes = h('section', {class: 'cartao md-pendentes', 'aria-labelledby': 'md-t-pend', hidden: true});
        const lembretes = h('section', {class: 'cartao md-lembretes', 'aria-labelledby': 'md-t-lemb'});
        const hist = h('section', {class: 'cartao md-historico nao-imprimir', 'aria-labelledby': 'md-t-hist'});

        // ---------- Desenho ----------
        function desenharCabecalho() {
            const r = view.resumo;
            const total = r.itens_total + r.rotinas_pendentes;
            const perc = total ? Math.round((r.itens_concluidos / total) * 100) : 0;
            const barra = h('div', {class: 'progresso-preenchido'});
            barra.style.width = `${perc}%`;
            const dataInput = h('input', {type: 'date', value: dataAtual, 'aria-label': 'Escolher data', class: 'md-data-input',
                on: {change: evento => irPara(evento.target.value)}});
            const marca = dataAtual === hoje ? h('span', {class: 'badge situacao situacao-hoje', text: 'Hoje'})
                : dataAtual < hoje ? h('span', {class: 'badge', text: 'Dia anterior'}) : h('span', {class: 'badge badge-run', text: 'Planejamento'});
            const chip = (texto, classe) => h('span', {class: `badge ${classe}`, text: texto});
            const renov = view.renovacoes.length;
            cabecalho.replaceChildren(
                h('div', {class: 'md-nav nao-imprimir'},
                    h('div', {class: 'md-nav-botoes'},
                        h('button', {type: 'button', class: 'secundario so-icone', title: 'Dia anterior', 'aria-label': 'Dia anterior', on: {click: () => irPara(somarDias(dataAtual, -1))}}, icone('chevron-left')),
                        h('button', {type: 'button', class: 'secundario', disabled: dataAtual === hoje, on: {click: () => irPara(hoje)}}, 'Hoje'),
                        h('button', {type: 'button', class: 'secundario so-icone', title: 'Próximo dia', 'aria-label': 'Próximo dia', on: {click: () => irPara(somarDias(dataAtual, 1))}}, icone('chevron-right'))),
                    dataInput,
                    h('div', {class: 'acoes md-nav-extra'},
                        h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => window.print()}}, icone('printer', {classe: 'icone-sm'}), 'Imprimir'),
                        escrita && view.dia.id ? h('button', {type: 'button', class: 'secundario perigo pequeno', on: {click: limparDia}}, icone('trash-2', {classe: 'icone-sm'}), 'Limpar dia') : null)),
                h('div', {class: 'md-titulo-dia'},
                    h('h2', {class: 'md-data', text: `${diaSemana(dataAtual)}, ${formatarData(dataAtual)}`}), marca),
                h('div', {class: 'md-progresso'},
                    h('div', {class: 'progresso', role: 'img', 'aria-label': `${perc}% do dia concluído`}, barra),
                    h('div', {class: 'md-progresso-texto'},
                        h('strong', {text: total ? `${numero(r.itens_concluidos)} de ${numero(total)}` : 'Dia livre'}),
                        h('span', {class: 'texto-suave', text: total ? ' itens concluídos' : ' — defina o foco e as prioridades'}),
                        r.rotinas_pendentes ? chip(`${numero(r.rotinas_pendentes)} ${r.rotinas_pendentes === 1 ? 'rotina' : 'rotinas'} por fazer`, 'situacao-hoje') : null,
                        renov ? chip(`${numero(renov)} ${renov === 1 ? 'renovação' : 'renovações'}`, 'situacao-atrasada') : null)),
                h('div', {class: 'md-foco'},
                    h('label', {class: 'md-foco-rotulo', htmlFor: 'md-foco'}, icone('lightbulb', {classe: 'icone-sm'}), 'Foco do dia'),
                    focoInput, indicador()),
                ...(escrita ? [] : [h('p', {class: 'texto-suave md-nota', text: 'Somente leitura: seu perfil não tem permissão de escrita neste espaço.'})]));
        }

        function linhaItem(item, indice) {
            const caixa = h('input', {type: 'checkbox', checked: item.concluido, disabled: !escrita, 'aria-label': `Concluir: ${item.texto}`,
                on: {change: () => alterarItem(item, {concluido: caixa.checked})}});
            const texto = h('input', {type: 'text', class: 'md-item-texto', value: item.texto, maxLength: 500, readOnly: !escrita, 'aria-label': 'Texto do item',
                on: {
                    change: () => {
                        const novo = texto.value.trim();
                        if (!novo) { texto.value = item.texto; return; }
                        if (novo !== item.texto) alterarItem(item, {texto: novo});
                    },
                    keydown: evento => {
                        if (evento.key === 'Enter') texto.blur();
                        if (evento.key === 'Escape') { texto.value = item.texto; texto.blur(); }
                    }
                }});
            const prioridade = item.tipo === 'PRIORIDADE';
            const cheio = view.prioridades.length >= LIMITE_PRIORIDADES;
            const acoes = !escrita ? null : h('div', {class: 'md-item-acoes nao-imprimir'},
                prioridade
                    ? h('button', {type: 'button', class: 'fantasma pequeno so-icone md-icone', title: 'Mover para tarefas', 'aria-label': `Mover para tarefas: ${item.texto}`,
                        on: {click: () => alterarItem(item, {tipo: 'TAREFA'})}}, icone('list-todo', {classe: 'icone-sm'}))
                    : h('button', {type: 'button', class: 'fantasma pequeno so-icone md-icone', disabled: cheio, title: cheio ? 'Já há 3 prioridades' : 'Promover a prioridade',
                        'aria-label': `Promover a prioridade: ${item.texto}`, on: {click: () => alterarItem(item, {tipo: 'PRIORIDADE'})}}, icone('trending-up', {classe: 'icone-sm'})),
                h('button', {type: 'button', class: 'fantasma pequeno so-icone md-icone', title: 'Remover', 'aria-label': `Remover: ${item.texto}`,
                    on: {click: () => removerItem(item)}}, icone('x', {classe: 'icone-sm'})));
            return h('li', {class: `md-item${item.concluido ? ' concluido' : ''}${prioridade ? ' md-item-prioridade' : ''}`},
                prioridade ? h('span', {class: 'md-numero', 'aria-hidden': 'true', text: indice + 1}) : null,
                caixa, texto, acoes);
        }

        function desenharPrioridades() {
            const n = view.prioridades.length;
            const feitas = view.prioridades.filter(i => i.concluido).length;
            prioContagem.textContent = n ? `${feitas}/${n} concluídas` : `0/${LIMITE_PRIORIDADES}`;
            prioLista.replaceChildren(...view.prioridades.map(linhaItem));
            const cheio = n >= LIMITE_PRIORIDADES;
            prioForm.hidden = cheio;
            prioNota.textContent = cheio ? `Limite de ${LIMITE_PRIORIDADES} prioridades atingido. O restante vai em Tarefas.`
                : n === 0 ? `Escolha até ${LIMITE_PRIORIDADES} coisas que fariam deste um dia bem-sucedido.` : '';
            prioNota.hidden = !prioNota.textContent;
        }

        function desenharTarefas() {
            const todas = view.tarefas;
            const abertas = todas.filter(i => !i.concluido).length;
            tarContagem.textContent = todas.length ? `${abertas} em aberto` : 'vazio';
            const FILTROS = [['TODAS', 'Todas'], ['PENDENTES', 'Pendentes'], ['CONCLUIDAS', 'Concluídas']];
            tarFiltros.replaceChildren(...FILTROS.map(([valor, rotulo]) => h('button', {
                type: 'button', class: `chip${filtro === valor ? ' ativo' : ''}`, 'aria-pressed': String(filtro === valor),
                on: {click: () => { filtro = valor; desenharTarefas(); }}
            }, rotulo)));
            const visiveis = todas.filter(i => filtro === 'TODAS' || (filtro === 'PENDENTES' ? !i.concluido : i.concluido));
            if (!visiveis.length) {
                tarLista.replaceChildren(h('li', {class: 'texto-suave md-vazio', text: todas.length ? 'Nenhuma tarefa neste filtro.'
                    : escrita ? 'Nenhuma tarefa. Anote algo acima e pressione Enter.' : 'Nenhuma tarefa neste dia.'}));
                return;
            }
            tarLista.replaceChildren(...visiveis.map(linhaItem));
        }

        function desenharPendentes() {
            const lista = view.pendentes_anteriores;
            for (const id of [...selecionados]) if (!lista.some(p => p.id === id)) selecionados.delete(id);
            pendentes.hidden = !lista.length;
            if (!lista.length) { pendentes.replaceChildren(); return; }
            const contador = h('span', {class: 'texto-suave pequeno-texto'});
            const botaoTrazer = h('button', {type: 'button', class: 'pequeno', on: {click: () => trazer([...selecionados])}});
            const rotuloTrazer = h('span');
            botaoTrazer.append(icone('plus', {classe: 'icone-sm'}), rotuloTrazer);
            const botaoDescartar = h('button', {type: 'button', class: 'secundario pequeno', on: {click: descartar}}, icone('trash-2', {classe: 'icone-sm'}), 'Descartar selecionados');
            const atualizar = () => {
                const n = selecionados.size;
                contador.textContent = n ? `${n} selecionado${n === 1 ? '' : 's'}` : 'Marque os itens que deseja trazer';
                rotuloTrazer.textContent = n ? `Trazer selecionados (${n})` : 'Trazer selecionados';
                botaoTrazer.disabled = !n;
                botaoDescartar.disabled = !n;
            };
            const linhas = lista.map(p => {
                const caixa = h('input', {type: 'checkbox', checked: selecionados.has(p.id), disabled: !escrita, 'aria-label': `Selecionar: ${p.texto}`,
                    on: {change: () => { if (caixa.checked) selecionados.add(p.id); else selecionados.delete(p.id); atualizar(); }}});
                return h('li', {class: 'md-pendente'},
                    h('label', {class: 'md-pendente-corpo'}, caixa,
                        h('span', {class: 'md-pendente-texto', text: p.texto}),
                        h('span', {class: 'badge', text: p.tipo === 'PRIORIDADE' ? 'Prioridade' : 'Tarefa'}),
                        h('span', {class: 'texto-suave pequeno-texto', text: `de ${diaMes(p.data_origem)}`})));
            });
            atualizar();
            pendentes.replaceChildren(
                h('div', {class: 'cartao-topo'}, h('h2', {id: 'md-t-pend'}, icone('inbox'), 'Pendentes de dias anteriores'),
                    h('span', {class: 'badge situacao situacao-hoje', text: numero(lista.length)})),
                h('ul', {class: 'lista-limpa md-itens'}, linhas),
                h('div', {class: 'acoes md-pendentes-acoes nao-imprimir'}, escrita ? [botaoTrazer,
                    h('button', {type: 'button', class: 'secundario pequeno', on: {click: () => trazer(null)}}, `Trazer todos (${lista.length})`),
                    botaoDescartar, contador] : null));
        }

        function linhaRotina(o, atrasada) {
            return h('li', {class: `md-lembrete${atrasada ? ' atrasada' : ''}`},
                h('div', {class: 'md-lembrete-corpo'},
                    h('div', {class: 'md-lembrete-titulo'}, tituloComLink(o.titulo, o.link_recurso), badgeCategoria(o.categoria)),
                    h('div', {class: 'texto-suave pequeno-texto', text: [
                        atrasada ? `Atrasada desde ${diaMes(o.data_prevista)}` : 'Vence hoje',
                        o.semana_identificacao, o.esforco_estimado_min ? `previsto ${minutos(o.esforco_estimado_min)}` : null
                    ].filter(Boolean).join(' · ')})),
                escrita ? h('button', {type: 'button', class: 'pequeno nao-imprimir', 'aria-label': `Concluir rotina: ${o.titulo}`, on: {click: () => concluirRotina(o)}}, icone('check', {classe: 'icone-sm'}), 'Concluir') : null);
        }

        function desenharLembretes() {
            const {vence_hoje: venceHoje, atrasadas} = view.rotinas;
            const rotinas = [...atrasadas.map(o => linhaRotina(o, true)), ...venceHoje.map(o => linhaRotina(o, false))];
            const nRotinas = rotinas.length;
            const LIMITE_ROTINAS = 6;
            const visiveis = todasRotinas ? rotinas : rotinas.slice(0, LIMITE_ROTINAS);
            const renov = view.renovacoes;
            lembretes.classList.toggle('md-ok', !nRotinas && !renov.length);
            lembretes.classList.toggle('md-alerta', atrasadas.length > 0 || renov.length > 0);
            lembretes.replaceChildren(
                h('div', {class: 'cartao-topo'}, h('h2', {id: 'md-t-lemb'}, icone('lightbulb'), 'Lembretes')),
                h('div', {class: 'md-bloco'},
                    h('h3', {}, icone('repeat', {classe: 'icone-sm'}), 'Rotinas', h('span', {class: `badge situacao ${atrasadas.length ? 'situacao-atrasada' : nRotinas ? 'situacao-hoje' : 'situacao-concluida'}`, text: numero(nRotinas)})),
                    nRotinas ? h('ul', {class: 'lista-limpa'}, visiveis) : h('p', {class: 'texto-suave', text: 'Nenhuma rotina vence hoje nem está atrasada.'}),
                    nRotinas > LIMITE_ROTINAS ? h('button', {type: 'button', class: 'secundario pequeno nao-imprimir md-mais', 'aria-expanded': String(todasRotinas), on: {click: () => { todasRotinas = !todasRotinas; desenharLembretes(); }}}, todasRotinas ? 'Mostrar menos' : `Mostrar todas (${numero(nRotinas)})`) : null,
                    h('a', {class: 'md-link nao-imprimir', href: '#/rotinas'}, 'Abrir checklist de rotinas', icone('chevron-right', {classe: 'icone-sm'}))),
                h('div', {class: 'md-bloco'},
                    h('h3', {}, icone('receipt', {classe: 'icone-sm'}), 'Contratos renovando em até 30 dias', h('span', {class: `badge ${renov.length ? 'situacao-atrasada' : 'situacao-concluida'}`, text: numero(renov.length)})),
                    renov.length ? h('ul', {class: 'lista-limpa'}, renov.map(r => h('li', {class: 'md-lembrete'},
                        h('div', {class: 'md-lembrete-corpo'},
                            h('strong', {text: r.nome}),
                            h('div', {class: 'texto-suave pequeno-texto', text: [r.fornecedor, `${formatarData(r.data_renovacao)} (${textoDias(r.dias)})`].filter(Boolean).join(' · ')})),
                        h('span', {class: 'md-valor', text: `${moeda(r.custo_mensal)}/mês`}))))
                        : h('p', {class: 'texto-suave', text: 'Nenhum contrato renova nos próximos 30 dias.'}),
                    h('a', {class: 'md-link nao-imprimir', href: '#/despesas/inventario'}, 'Abrir inventário de despesas', icone('chevron-right', {classe: 'icone-sm'}))));
        }

        function desenharHistorico() {
            hist.replaceChildren(
                h('div', {class: 'cartao-topo'}, h('h2', {id: 'md-t-hist'}, icone('calendar'), `Histórico (${DIAS_HISTORICO} dias)`)),
                historico.length ? h('ul', {class: 'lista-limpa md-hist-lista'}, historico.map(d => h('li', {},
                    h('button', {type: 'button', class: `md-hist-item${d.data === dataAtual ? ' ativo' : ''}`, 'aria-current': d.data === dataAtual ? 'date' : null,
                        on: {click: () => irPara(d.data)}},
                    h('span', {class: 'md-hist-data', text: `${diaSemana(d.data, 'short')} ${diaMes(d.data)}`}),
                    h('span', {class: 'md-hist-foco', text: d.foco || 'Sem foco definido'}),
                    h('span', {class: 'badge', text: `${d.itens_concluidos}/${d.itens_total}`})))))
                    : h('p', {class: 'texto-suave', text: 'Os dias que você usar aparecem aqui.'}));
        }

        function preencherCampos(forcar) {
            if (forcar || !sujo.has('foco')) focoInput.value = view.dia.foco ?? '';
            if (forcar || !sujo.has('notas')) notasArea.value = view.dia.notas ?? '';
        }

        async function carregar(forcar = false) {
            const minha = ++sequencia;
            const alvo = dataAtual;
            try {
                const [v, h30] = await Promise.all([
                    get(`${API}/meu-dia`, {data: alvo}, signal),
                    get(`${API}/dias`, {de: somarDias(hoje, 1 - DIAS_HISTORICO), ate: somarDias(hoje, 7)}, signal)]);
                if (signal.aborted || minha !== sequencia) return;
                view = v;
                historico = h30;
                dataAtual = alvo;
                preencherCampos(forcar);
                desenharCabecalho(); desenharPrioridades(); desenharTarefas();
                desenharPendentes(); desenharLembretes(); desenharHistorico();
                aplicarFoco();
            } catch (erro) {
                if (signal.aborted || minha !== sequencia) return;
                if (!view) container.replaceChildren(h('p', {class: 'erro', text: erro.message}));
                tratarErro(erro);
            }
        }

        cabecalho.replaceChildren(carregando(1));
        container.replaceChildren(
            cabecalho,
            h('div', {class: 'md-grade'},
                h('div', {class: 'md-coluna'}, prioridades, pendentes, tarefas, notas),
                h('div', {class: 'md-coluna'}, lembretes, hist)));
        await carregar(true);

        // O router chama este cleanup ao trocar de rota ou de espaço: nada pendente sobrevive à navegação.
        return () => { clearTimeout(timer); timer = null; sujo.clear(); };
    }
};
