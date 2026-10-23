# Contexto do projeto

**Projeto:** GFlow  
**APP_ID:** gflow

Este arquivo descreve o produto a ser construído. Bootstrap personaliza os metadados; o responsável pelo projeto preenche as regras abaixo. LLMs devem tratar campos pendentes como desconhecidos, sem inventar requisitos.

## Objetivo e público

Acompanhar indicadores de engenharia: capacidade **BUILD ≥ 70% / RUN ≤ 30%**, rotinas, Planner pessoal, FinOps e Despesas & Contratos. Este produto é o porte para o gflow do MVP "Indicadores de Engenharia de Dados". Usuários: membros de um tenant com acesso à aplicação. A definir: perfis de usuário detalhados e resultados de negócio mensuráveis além da meta BUILD/RUN.

## Escopo

O porte é feito em fases ([ADR-003](adrs/ADR-003-porte-mvp-indicadores-em-fases.md)).

- **Fase 1 (Capacidade):** grupos (squads), semanas/ciclos, lançamentos ABERTO/RESOLVIDO e dashboard BUILD × RUN.
- **Próximas fases:** rotinas (N0, somadas ao dashboard apenas na Fase 2), Planner pessoal, FinOps e Despesas & Contratos. A definir: ordem e regras detalhadas das fases 2–5.
- **Removido do MVP:** alias `/api` legado, `audit_log`, `/metrics/latest`, `/raw`, exportação HTML standalone e "copiar contexto LLM" (volta com Rotinas).

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
- Rotinas (N0) não somam nesta fase.
- Grupos padrão (seis do MVP, entre eles "EngDados - Projetos" BUILD e "Rotinas (N0)" RUN) só são criados por ação explícita e apenas os que faltam, por nome.
- Excluir um grupo ou semana remove seus lançamentos.

A definir: metas configuráveis por tenant (hoje fixas em 70%/30%).

## Jornadas e critérios de aceite

Fase 1:

1. **Configurar:** com write, o usuário cria grupos (ou cria os padrão) e semanas. Aceite: nome ou identificação duplicados no tenant retornam conflito; fim anterior ao início é recusado.
2. **Lançar:** o usuário inicializa uma semana (cria ABERTO e RESOLVIDO faltantes) e edita o par de quantidades de um grupo. Aceite: quantidade negativa é recusada; grupo ou semana de outro tenant resulta em não encontrado.
3. **Acompanhar:** qualquer membro com read vê o dashboard e as metas atingidas ou o gap. Aceite: totais e percentuais seguem as regras acima.
4. **Isolamento:** tenant sem acesso recebe 403 e nunca vê dados de outro tenant (validado por testes de RLS em PostgreSQL).

A definir: critérios de aceite das fases 2–5.

## Restrições e integrações

Base técnica: FastAPI, SQLAlchemy 2, Alembic e frontend vanilla (ES modules, CSP estrita); SQLite para dev isolado e PostgreSQL para integrated/produção. Não há importação de dados do MVP: cada tenant começa vazio. O Planner pessoal pertence a (tenant, sub) e terá ADR próprio na fase dele. A definir: integrações de domínio das fases futuras. Nunca inclua credenciais ou dados pessoais reais neste documento.

## Pendências

Permanecem "A definir": perfis de usuário, regras de ingresso específicas, metas configuráveis por tenant e regras detalhadas das fases 2–5. Registre dúvidas bloqueantes na tarefa; decisões arquiteturais ficam no Master ADR.
