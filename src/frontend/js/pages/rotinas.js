import {get, post, put} from '../api.js';
import {podeEscrever} from '../state.js';
import {h, campo, carregando, confirmar, estadoVazio, data, hojeLocal, icone, minutos, numero, toast, tratarErro} from '../ui.js';

export const TIPOS = [
    ['SEMANAL', 'Semanal'], ['DIARIA', 'Diária'], ['QUINZENAL', 'Quinzenal (01 e 15)'],
    ['MENSAL_DIA_FIXO', 'Mensal, dia fixo'], ['MENSAL_PRIMEIRO_UTIL', '1º dia útil do mês'], ['MENSAL_ULTIMO_UTIL', 'Último dia útil do mês']
];
const SITUACOES = {
    VENCE_HOJE: ['Vence hoje', 'hoje'], ATRASADA: ['Atrasada', 'atrasada'], PREVISTA: ['Prevista', 'prevista'],
    SEM_DATA: ['Sem data', 'sem-data'], CONCLUIDA: ['Concluída', 'concluida']
};
const DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];

// Texto do agendamento a partir de uma rotina ou ocorrência.
export function textoAgendamento(r) {
    switch (r.tipo_agendamento) {
        case 'DIARIA': {
            const dia = r.ocorrencia && r.ocorrencia !== 'SEMANA' ? r.ocorrencia : 'Seg–Sex';
            return `Diária • ${dia}`;
        }
        case 'QUINZENAL': return 'Quinzenal 01 e 15';
        case 'MENSAL_DIA_FIXO': return `Todo dia ${String(r.dia_mes ?? '').padStart(2, '0')}`;
        case 'MENSAL_PRIMEIRO_UTIL': return '1º dia útil';
        case 'MENSAL_ULTIMO_UTIL': return 'Último dia útil';
        default: return `Semanal • ${r.dia_semana ?? '—'} • ${r.periodo ?? 'Manhã'}`;
    }
}
export const badgeAgendamento = r => h('span', {class: `badge badge-agenda agenda-${String(r.tipo_agendamento).toLowerCase()}`, text: textoAgendamento(r)});
export function badgeSituacao(situacao) {
    const [texto, classe] = SITUACOES[situacao] ?? [situacao, 'prevista'];
    return h('span', {class: `badge situacao situacao-${classe}`, text: texto});
}
export const badgeCategoria = categoria => h('span', {class: `badge badge-${String(categoria).toLowerCase()}`, text: categoria});

// link_recurso só vira link com http(s); qualquer outro valor é texto puro.
export function tituloComLink(titulo, link) {
    if (typeof link === 'string' && /^https?:\/\//i.test(link)) {
        return h('a', {href: link, target: '_blank', rel: 'noopener noreferrer', class: 'rotina-titulo', text: titulo});
    }
    return h('span', {class: 'rotina-titulo', text: titulo});
}

const rotuloDia = iso => {
    const [a, m, d] = iso.split('-').map(Number);
    const dia = new Date(a, m - 1, d).toLocaleDateString('pt-BR', {weekday: 'long'});
    return `${dia.charAt(0).toUpperCase()}${dia.slice(1)}, ${data(iso)}`;
};

export function dialogoConclusao(o) {
    return new Promise(resolve => {
        const real = h('input', {type: 'number', min: 0, max: 1440, step: 1, placeholder: `Previsto: ${o.esforco_estimado_min} min`});
        const obs = h('textarea', {rows: 3});
        const dialogo = h('dialog', {class: 'modal'},
            h('form', {class: 'formulario-modal', on: {submit: evento => { evento.preventDefault(); dialogo.close('ok'); }}},
                h('h2', {}, 'Concluir rotina'),
                h('p', {class: 'texto-suave', text: o.titulo}),
                campo('Tempo real gasto, em minutos (opcional)', real),
                campo('Observação (opcional)', obs),
                h('div', {class: 'acoes'},
                    h('button', {type: 'button', class: 'secundario', on: {click: () => dialogo.close('cancel')}}, 'Cancelar'),
                    h('button', {type: 'submit'}, icone('check', {classe: 'icone-sm'}), 'Concluir'))));
        dialogo.addEventListener('close', () => {
            const ok = dialogo.returnValue === 'ok';
            const valor = real.value === '' ? null : Math.round(Number(real.value));
            const texto = obs.value.trim();
            dialogo.remove();
            resolve(ok ? {esforco_real_min: valor, observacao: texto || null} : null);
        });
        document.body.append(dialogo);
        dialogo.showModal();
        real.focus();
    });
}

function cartaoResumo(rotulo, r) {
    const perc = r.ocorrencias ? Math.round((r.concluidas / r.ocorrencias) * 100) : 0;
    const barra = h('div', {class: 'progresso-preenchido'});
    barra.style.width = `${perc}%`;
    return h('div', {class: `resumo-card resumo-${rotulo.toLowerCase()}`},
        h('div', {class: 'resumo-topo'}, h('strong', {text: rotulo}), h('span', {class: 'texto-suave', text: `${numero(r.ocorrencias)} ocorrências`})),
        h('div', {class: 'resumo-pct', text: `${perc}%`}),
        h('div', {class: 'progresso', role: 'img', 'aria-label': `${perc}% concluído`}, barra),
        h('div', {class: 'resumo-linha'},
            h('span', {class: 'leg-resolvido', text: `${numero(r.concluidas)} concluídas`}),
            h('span', {class: 'leg-aberto', text: `${numero(r.pendentes)} pendentes`})),
        h('div', {class: 'resumo-horas'},
            h('span', {text: 'Previsto '}), h('strong', {text: minutos(r.minutos_previstos)}),
            h('span', {text: ' × Executado '}), h('strong', {text: minutos(r.minutos_executados)})));
}

export const rotinas = {
    titulo: 'Rotinas',
    subtitulo: 'Checklist semanal, esforço gasto e nada para trás',
    async render(container, signal) {
        const escrita = podeEscrever();
        const hoje = hojeLocal();
        const semanas = await get('/api/v1/semanas', undefined, signal);
        if (signal.aborted) return;
        if (!semanas.length) {
            container.replaceChildren(estadoVazio({titulo: 'Nenhuma semana cadastrada', icone: 'calendar'},
                'Rotinas são acompanhadas por semana. Cadastre uma semana em Configuração.',
                h('a', {class: 'botao', href: '#/config/semanas'}, icone('calendar', {classe: 'icone-sm'}), 'Configurar semanas')));
            return;
        }
        let semana = null, pendencias = null;
        const filtros = {categoria: '', status: '', tipo: ''};

        const seletor = h('select', {id: 'rotinas-semana'}, semanas.map(s => h('option', {value: s.id, text: s.identificacao})));
        seletor.value = semanas[0].id;
        const areaResumo = h('div', {class: 'resumo-grade'});
        const areaPendencias = h('section', {class: 'cartao pendencias'});
        const areaLista = h('section', {class: 'cartao'});

        const opcoes = (lista, vazio) => [h('option', {value: '', text: vazio}), lista.map(([v, t]) => h('option', {value: v, text: t}))];
        const filtroCategoria = h('select', {}, opcoes([['BUILD', 'BUILD'], ['RUN', 'RUN']], 'Todas'));
        const filtroStatus = h('select', {}, opcoes([['PENDENTE', 'Pendentes'], ['CONCLUIDA', 'Concluídas']], 'Todos'));
        const filtroTipo = h('select', {}, opcoes(TIPOS, 'Todos'));
        for (const [el, chave] of [[filtroCategoria, 'categoria'], [filtroStatus, 'status'], [filtroTipo, 'tipo']]) {
            el.addEventListener('change', () => { filtros[chave] = el.value; desenharLista(); });
        }

        async function alterar(o, status, extra = {}) {
            try {
                await put(`/api/v1/rotinas/${o.rotina_id}/execucao`, {
                    semana_id: o.semana_id, ocorrencia: o.ocorrencia, status,
                    esforco_real_min: status === 'CONCLUIDA' ? (extra.esforco_real_min ?? null) : null,
                    observacao: extra.observacao ?? null
                });
                toast(status === 'CONCLUIDA' ? 'Rotina concluída.' : 'Rotina reaberta.', 'success');
                await carregar();
            } catch (erro) { tratarErro(erro); }
        }
        async function concluir(o) {
            const extra = await dialogoConclusao(o);
            if (extra) await alterar(o, 'CONCLUIDA', extra);
        }
        const botaoAcao = o => !escrita ? null : (o.status === 'CONCLUIDA'
            ? h('button', {type: 'button', class: 'secundario pequeno botao-acao', 'aria-label': `Reabrir: ${o.titulo}`, on: {click: () => alterar(o, 'PENDENTE')}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Reabrir')
            : h('button', {type: 'button', class: 'pequeno botao-acao', 'aria-label': `Concluir: ${o.titulo}`, on: {click: () => concluir(o)}}, icone('check', {classe: 'icone-sm'}), 'Concluir'));

        function desenharResumo() {
            const r = semana.resumo;
            areaResumo.replaceChildren(cartaoResumo('BUILD', r.BUILD), cartaoResumo('RUN', r.RUN), cartaoResumo('TOTAL', r.TOTAL));
        }

        function linhaPendencia(o, atrasada) {
            return h('li', {class: `pendencia-item${atrasada ? ' atrasada' : ''}`},
                h('span', {class: 'pendencia-data', text: data(o.data_prevista)}),
                h('span', {class: 'pendencia-semana texto-suave', text: o.semana_identificacao}),
                h('span', {class: 'pendencia-titulo'}, tituloComLink(o.titulo, o.link_recurso), ' ', badgeCategoria(o.categoria)),
                botaoAcao(o));
        }
        const expandidos = new Set();
        function blocoPendencia(titulo, itens, atrasada) {
            const LIMITE = 6;
            const aberto = expandidos.has(titulo);
            const visiveis = aberto ? itens : itens.slice(0, LIMITE);
            return h('div', {class: 'pendencias-bloco'},
                h('h3', {}, titulo, h('span', {class: `badge situacao ${atrasada ? 'situacao-atrasada' : 'situacao-hoje'}`, text: numero(itens.length)})),
                itens.length ? h('ul', {class: 'lista-limpa'}, visiveis.map(o => linhaPendencia(o, atrasada)))
                    : h('p', {class: 'texto-suave', text: atrasada ? 'Nenhuma rotina atrasada.' : 'Nada vence hoje.'}),
                itens.length > LIMITE ? h('button', {type: 'button', class: 'secundario pequeno', 'aria-expanded': String(aberto), on: {click: () => {
                    if (aberto) expandidos.delete(titulo); else expandidos.add(titulo);
                    desenharPendencias();
                }}}, aberto ? 'Mostrar menos' : `Mostrar todas (${numero(itens.length)})`) : null);
        }
        function desenharPendencias() {
            const total = pendencias.vence_hoje.length + pendencias.atrasadas.length;
            areaPendencias.classList.toggle('pendencias-ok', total === 0);
            areaPendencias.replaceChildren(
                h('div', {class: 'cartao-topo'}, h('h2', {}, icone(total ? 'triangle-alert' : 'circle-check'), 'Não deixe nada para trás'),
                    h('span', {class: 'texto-suave', text: total ? `${numero(total)} em aberto, de qualquer semana` : 'Tudo em dia.'})),
                h('div', {class: 'grade-2'},
                    blocoPendencia('Vence hoje', pendencias.vence_hoje, false),
                    blocoPendencia('Atrasadas', pendencias.atrasadas, true)));
        }

        function linhaOcorrencia(o) {
            const concluida = o.status === 'CONCLUIDA';
            const horas = [`Previsto ${minutos(o.esforco_estimado_min)}`];
            if (concluida) horas.push(`Real ${minutos(o.esforco_real_min ?? o.esforco_estimado_min)}`);
            return h('li', {class: `ocorrencia${concluida ? ' concluida' : ''}`},
                h('div', {class: 'ocorrencia-corpo'},
                    h('div', {class: 'ocorrencia-titulo'}, tituloComLink(o.titulo, o.link_recurso), badgeCategoria(o.categoria), badgeAgendamento(o), badgeSituacao(o.situacao)),
                    h('div', {class: 'ocorrencia-meta texto-suave'},
                        horas.join(' • '), o.responsavel ? ` • ${o.responsavel}` : '',
                        o.concluido_por ? ` • concluída por ${o.concluido_por}` : ''),
                    o.observacao ? h('div', {class: 'ocorrencia-obs', text: o.observacao}) : null),
                botaoAcao(o));
        }

        function desenharLista() {
            if (!semana) return;
            const itens = semana.ocorrencias.filter(o =>
                (!filtros.categoria || o.categoria === filtros.categoria)
                && (!filtros.status || o.status === filtros.status)
                && (!filtros.tipo || o.tipo_agendamento === filtros.tipo));
            const topo = h('div', {class: 'cartao-topo'},
                h('h2', {}, icone('list-checks'), 'Checklist da semana'),
                h('div', {class: 'filtros'}, campo('Categoria', filtroCategoria), campo('Status', filtroStatus), campo('Tipo', filtroTipo)));
            if (!itens.length) {
                areaLista.replaceChildren(topo, semana.ocorrencias.length
                    ? estadoVazio({titulo: 'Nenhuma ocorrência', icone: 'list-filter'}, 'Nenhuma ocorrência para estes filtros.')
                    : estadoVazio({titulo: 'Semana sem rotinas', icone: 'repeat'}, 'Esta semana não tem rotinas previstas. Cadastre rotinas no catálogo.',
                        h('a', {class: 'botao', href: '#/config/rotinas'}, 'Abrir catálogo', icone('chevron-right', {classe: 'icone-sm'}))));
                return;
            }
            const grupos = new Map();
            for (const o of itens) {
                const chave = o.data_prevista ?? '';
                if (!grupos.has(chave)) grupos.set(chave, []);
                grupos.get(chave).push(o);
            }
            const chaves = [...grupos.keys()].sort((a, b) => (a === '' ? 1 : b === '' ? -1 : a.localeCompare(b)));
            areaLista.replaceChildren(topo, ...chaves.map(chave => {
                const doDia = grupos.get(chave);
                const feitas = doDia.filter(o => o.status === 'CONCLUIDA').length;
                return h('div', {class: 'dia-grupo'},
                    h('h3', {class: 'dia-titulo'},
                        chave ? rotuloDia(chave) : 'Sem data prevista',
                        chave === hoje ? h('span', {class: 'badge situacao situacao-hoje', text: 'Hoje'}) : null,
                        h('span', {class: 'texto-suave dia-contagem', text: `${feitas}/${doDia.length}`})),
                    h('ul', {class: 'lista-limpa'}, doDia.map(linhaOcorrencia)));
            }));
        }

        async function carregar(esqueleto = false) {
            if (esqueleto) { areaResumo.replaceChildren(carregando(1)); areaLista.replaceChildren(carregando(2)); }
            try {
                const [s, p] = await Promise.all([
                    get('/api/v1/rotinas/semana', {semana_id: seletor.value, hoje}, signal),
                    get('/api/v1/rotinas/pendencias', {hoje}, signal)]);
                if (signal.aborted) return;
                semana = s; pendencias = p;
                desenharResumo(); desenharPendencias(); desenharLista();
            } catch (erro) {
                if (signal.aborted) return;
                areaLista.replaceChildren(h('p', {class: 'erro', text: erro.message}));
                tratarErro(erro);
            }
        }

        async function reiniciar() {
            const nome = semanas.find(s => s.id === seletor.value)?.identificacao ?? 'esta semana';
            if (!await confirmar(`Reiniciar ${nome}? Todas as ocorrências voltam a pendentes e o tempo real registrado é apagado.`, 'Reiniciar')) return;
            try {
                const r = await post('/api/v1/rotinas/semana/reset', {semana_id: seletor.value});
                toast(`Semana reiniciada: ${r.reset_count} ocorrências reabertas.`, 'success');
                await carregar();
            } catch (erro) { tratarErro(erro); }
        }

        seletor.addEventListener('change', () => carregar(true));
        container.replaceChildren(
            h('div', {class: 'barra-acoes'},
                campo('Semana', seletor),
                h('div', {class: 'acoes'},
                    escrita ? h('button', {type: 'button', class: 'secundario perigo', on: {click: reiniciar}}, icone('rotate-ccw', {classe: 'icone-sm'}), 'Reiniciar semana') : null,
                    h('a', {class: 'botao secundario', href: '#/config/rotinas'}, icone('list-todo', {classe: 'icone-sm'}), escrita ? 'Gerenciar catálogo' : 'Ver catálogo'))),
            areaResumo, areaPendencias, areaLista);
        await carregar(true);
    }
};

export {DIAS};
