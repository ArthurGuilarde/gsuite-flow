# Contexto do projeto

**Projeto:** GFlow  
**APP_ID:** gflow

Este arquivo descreve o produto a ser construído. Bootstrap personaliza os metadados; o responsável pelo projeto preenche as regras abaixo. LLMs devem tratar campos pendentes como desconhecidos, sem inventar requisitos.

## Objetivo e público

Acompanhar indicadores de engenharia: capacidade **BUILD ≥ 70% / RUN ≤ 30%**, rotinas, Planner pessoal, FinOps e Despesas & Contratos. Este produto é o porte para o gflow do MVP "Indicadores de Engenharia de Dados". Usuários: membros de um tenant com acesso à aplicação. A definir: perfis de usuário detalhados e resultados de negócio mensuráveis além da meta BUILD/RUN.

## Escopo

O porte é feito em fases ([ADR-003](adrs/ADR-003-porte-mvp-indicadores-em-fases.md)); as Fases 2 e 3 estão registradas no [ADR-004](adrs/ADR-004-rotinas-esforco-e-pendencias.md) e no [ADR-005](adrs/ADR-005-finops-valor-das-decisoes.md).

- **Fase 1 (Capacidade):** grupos (squads), semanas/ciclos, lançamentos ABERTO/RESOLVIDO e dashboard BUILD × RUN.
- **Fase 2 (Rotinas, em andamento):** catálogo de rotinas recorrentes, execução por semana/ocorrência, esforço estimado e real, pendências (vence hoje e atrasadas) e soma no painel BUILD × RUN pela categoria da rotina. Fora da fase: grade de agenda do MVP (A definir).
- **Fase 3 (FinOps, em andamento):** iniciativas (melhoria, automação e otimização de custo) como fonte única de saving, janela de 6 meses até virar novo normal, perfis de custo/hora, investimento/ROI/payback, e fontes de custo com faturas (orçado × realizado) apenas para acompanhamento.
- **Próximas fases:** Planner pessoal e Despesas & Contratos. A definir: ordem e regras detalhadas das fases 4–5.
- **Removido do MVP:** alias `/api` legado, `audit_log`, `/metrics/latest`, `/raw`, exportação HTML standalone e "copiar contexto LLM" (volta com Rotinas). Removidos também, no porte de Rotinas: grade de agenda e `bloco`, `data_especifica`, status no catálogo e o campo `recorrencia`. Removidos também, no porte de FinOps: tabela de meses cadastráveis (a competência é derivada de datas), histórico de saves como fonte de saving, busca "fabric" por nome, sincronização automática fatura→saving e Chart.js por CDN.

## Tenant e acesso

Um tenant representa um cliente (pessoa física ou jurídica) que contrata o sistema; é um espaço de trabalho compartilhado, nunca a aplicação ou um usuário. Membros e ingresso vêm do Core. A definir: regras de ingresso específicas deste produto.

Em produção/integrated, identidade é externa (Authentik), e memberships/entitlements são centrais (Core). Dev isolado usa identidades/grants fictícios somente para desenvolvimento. Permissões básicas: access/read/write; o Core é a autoridade. Leitura exige read; criar, alterar e remover exigem write.

## Domínio e regras

Termos da Fase 1:

- **Grupo:** squad ou frente de trabalho, com nome (único por tenant), categoria BUILD ou RUN, ícone, cor e indicador ativo.
- **Semana:** ciclo identificado por texto (único por tenant), com datas de início e fim opcionais; o fim não pode ser anterior ao início.
- **Lançamento:** quantidade (≥ 0) de itens de um grupo em uma semana, com status ABERTO ou RESOLVIDO e observação opcional. Cada par grupo/semana tem no máximo um ABERTO e um RESOLVIDO.

Regras do dashboard (todas as semanas ou uma semana):

- Considera apenas grupos ativos; total = soma das quantidades; BUILD/RUN pela categoria do grupo.
- Percentual = parte / total (0 se o total é 0). Meta atingida: BUILD ≥ 70% e RUN ≤ 30%; a diferença é informada em pontos percentuais.
- Os mesmos cálculos valem para o subconjunto de resolvidos e o de abertos; a taxa de resolução é resolvidos / total.
- As ocorrências de rotinas somam pela categoria da própria rotina (ver Termos da Fase 2): pendente conta como aberto e concluída como resolvida. Sem semana selecionada, somam todas as semanas.
- Grupos padrão (seis do MVP, entre eles "EngDados - Projetos" BUILD e "Rotinas (N0)" RUN) só são criados por ação explícita e apenas os que faltam, por nome. O grupo "Rotinas (N0)" continua existindo para lançamentos manuais; as rotinas cadastradas não somam mais nele.
- Excluir um grupo ou semana remove seus lançamentos.

A definir: metas configuráveis por tenant (hoje fixas em 70%/30%).

Termos da Fase 2 (Rotinas):

- **Rotina:** tarefa recorrente com título, categoria BUILD ou RUN (padrão RUN), responsável, link opcional (somente http/https), período (Manhã, Tarde ou Integral), esforço estimado em minutos por ocorrência (0–1440), ordem e indicador ativo.
- **Tipo de agendamento:** SEMANAL (exige dia da semana), DIARIA (os cinco dias úteis), QUINZENAL (dias 1 e 15), MENSAL_DIA_FIXO (exige dia do mês; dia 31 em mês curto vale o último dia), MENSAL_PRIMEIRO_UTIL e MENSAL_ULTIMO_UTIL. Apelidos como MENSAL, 1_UTIL e ULTIMO_DIA são normalizados. Dias úteis são segunda a sexta e ignoram feriados.
- **Vigência:** a rotina existe a partir da semana em que começa (`inicio_vigencia`, hoje se não informado). Rotina inativa só aparece em uma semana se tiver execução registrada nela.
- **Ocorrência:** uma data prevista da rotina numa semana. Rotinas diárias têm uma por dia útil; as demais têm uma por semana em que a data cai. Semana sem datas mostra a rotina sem data prevista.
- **Execução:** registro por (rotina, semana, ocorrência) com status PENDENTE ou CONCLUIDA, esforço real em minutos (opcional) e observação. Sem registro, a ocorrência está PENDENTE. Reiniciar a semana volta tudo a PENDENTE.
- **Esforço estimado e real:** minutos previstos somam o estimado de todas as ocorrências; minutos executados somam, nas concluídas, o real quando informado e o estimado quando não.
- **Situação:** CONCLUIDA; SEM_DATA (pendente sem data prevista); VENCE_HOJE; ATRASADA (data anterior a hoje); PREVISTA. Ocorrências pendentes que vencem hoje ou estão atrasadas, de qualquer semana com datas, aparecem na lista de pendências até serem concluídas.

Termos da Fase 3 (FinOps):

- **Iniciativa:** melhoria, automação ou otimização de custo, com título, mês de início, janela, mês de encerramento opcional, fonte de custo opcional e investimento opcional. É a única fonte de saving.
- **Modo de cálculo:** DIRETO_REAIS (valor mensal informado, para dinheiro que sai de fatura ou contrato) ou POR_TEMPO (capacidade do time convertida em R$ a partir dos participantes e da frequência).
- **Participante:** perfil, quantidade de pessoas e horas antes e depois por execução. Nome e custo/hora do perfil são copiados ao salvar (snapshot): alterar o perfil depois não reescreve o passado. A economia de horas pode ser negativa e é mostrada como está.
- **Perfil de custo/hora:** preset do tenant (por exemplo Analista R$ 80, Executivo R$ 300). O formulário sugere R$ 80 quando não há perfil.
- **Cálculo mensal:** horas/mês = (antes − depois) × pessoas × multiplicador de frequência (DIARIA_UTIL 22, DIARIA_CORRIDA 30, SEMANAL 4,33, QUINZENAL 2, MENSAL 1); valor/mês = horas/mês × custo/hora; FTE = horas/mês ÷ 168.
- **Janela e status:** toda iniciativa nasce com janela de 6 meses, editável de 1 a 60. O saving conta do mês de início até o fim da janela (ou do encerramento, se anterior). Status no mês de referência: PLANEJADA, EM_SAVING, NOVO_NORMAL (janela concluída; deixa de somar saving no período) e ENCERRADA.
- **Investimento, ROI e payback:** investimento = R$ + horas × custo/hora. ROI na janela = (saving da janela − investimento) ÷ investimento; payback = investimento ÷ valor mensal, arredondado para cima; sem investimento o payback é 0 e o ROI não se aplica.
- **Fonte de custo e fatura:** a fatura é por (fonte, competência) com orçado opcional, realizado e métrica opcional; mostra variação (orçado − realizado) e custo unitário (realizado ÷ métrica). Faturas não somam saving; a otimização de uma fatura é uma iniciativa que aponta para a fonte. Excluir uma fonte remove suas faturas, mas é recusado se houver iniciativas vinculadas.
- **Painel FinOps:** saving realizado (meses até a referência) e projetado (depois), saving em curso por mês (direto × horas do time), horas e FTE liberados, novo normal incorporado, ROI, série mensal, resumo por tipo, por fonte e por iniciativa. Competências são "AAAA-MM"; o intervalo máximo é de 36 meses.

## Jornadas e critérios de aceite

Fase 1:

1. **Configurar:** com write, o usuário cria grupos (ou cria os padrão) e semanas. Aceite: nome ou identificação duplicados no tenant retornam conflito; fim anterior ao início é recusado.
2. **Lançar:** o usuário inicializa uma semana (cria ABERTO e RESOLVIDO faltantes) e edita o par de quantidades de um grupo. Aceite: quantidade negativa é recusada; grupo ou semana de outro tenant resulta em não encontrado.
3. **Acompanhar:** qualquer membro com read vê o dashboard e as metas atingidas ou o gap. Aceite: totais e percentuais seguem as regras acima.
4. **Isolamento:** tenant sem acesso recebe 403 e nunca vê dados de outro tenant (validado por testes de RLS em PostgreSQL).

Fase 2 (Rotinas):

1. **Cadastrar:** com write, o usuário cria rotinas (ou as padrão, só por ação explícita). Aceite: SEMANAL sem dia da semana e MENSAL_DIA_FIXO sem dia do mês são recusados; link fora de http/https é recusado; tipo inválido é recusado.
2. **Executar:** o usuário conclui uma ocorrência, informando opcionalmente o tempo real. Aceite: ocorrência que não pertence à rotina naquela semana é recusada; voltar a PENDENTE limpa a conclusão e o tempo real.
3. **Não deixar nada para trás:** a lista de pendências mostra o que vence hoje e o que está atrasado até a conclusão. Aceite: ordem das atrasadas por data prevista e depois título.
4. **Medir esforço:** o resumo por categoria mostra contagem, minutos previstos e minutos executados, e o painel soma as ocorrências pela categoria. Aceite: valores conforme as regras acima.
5. **Isolamento:** rotina e execução de outro tenant nunca são visíveis nem referenciáveis (validado por testes de RLS e FK composta em PostgreSQL).

Fase 3 (FinOps):

1. **Cadastrar perfis e fontes:** com write, o usuário cria perfis de custo/hora e fontes de custo. Aceite: nome duplicado no tenant retorna conflito; custo negativo é recusado.
2. **Registrar iniciativa:** DIRETO_REAIS exige valor mensal e nenhum participante; POR_TEMPO exige frequência e ao menos um participante. Aceite: encerramento anterior ao início e janela fora de 1–60 são recusados; fonte de outro tenant resulta em não encontrado.
3. **Simular antes de salvar:** a prévia calcula valor, horas, FTE, janela, ROI e payback sem gravar.
4. **Acompanhar faturas:** orçado × realizado e custo unitário por fonte. Aceite: fonte + competência duplicada retorna conflito; fatura nunca soma saving.
5. **Demonstrar o efeito financeiro:** o painel mostra o saving por período e o ROI. Aceite: iniciativa em NOVO_NORMAL não soma saving no período.
6. **Isolamento:** perfis, fontes, faturas, iniciativas e participantes de outro tenant nunca são visíveis nem referenciáveis (validado por testes de RLS e FK composta em PostgreSQL).

A definir: critérios de aceite das fases 4–5.

## Restrições e integrações

Base técnica: FastAPI, SQLAlchemy 2, Alembic e frontend vanilla (ES modules, CSP estrita); SQLite para dev isolado e PostgreSQL para integrated/produção. Não há importação de dados do MVP: cada tenant começa vazio. O Planner pessoal pertence a (tenant, sub) e terá ADR próprio na fase dele. A definir: integrações de domínio das fases futuras. Nunca inclua credenciais ou dados pessoais reais neste documento.

## Pendências

Permanecem "A definir": perfis de usuário, regras de ingresso específicas, metas configuráveis por tenant, metas de esforço de rotinas, grade de agenda, feriados (os dias úteis os ignoram), fuso horário por tenant (hoje é o relógio do servidor), moeda além de BRL, fechamento contábil, fluxo de aprovação de iniciativas e regras detalhadas das fases 4–5. Registre dúvidas bloqueantes na tarefa; decisões arquiteturais ficam no Master ADR.
