# Arquitetura da aplicação

O template contém uma aplicação e um BFF. Produção/integrated usam PostgreSQL; dev isolado usa SQLite. Authentik fornece identidade; Core fornece memberships, acesso à aplicação e entitlements. Nenhum serviço consulta diretamente o banco de outro.

Tenant é um espaço compartilhado entre membros. APP_ID identifica a aplicação. O subject OIDC identifica o usuário e é tratado como string opaca.

Fluxo de domínio: cookie opaco → sessão criptografada no PostgreSQL → access token validado → autorização do Core para subject/app/tenant/permissão → TenantContext → transação com SET LOCAL → repositório com filtro de tenant + RLS.

A base não inclui um domínio de negócio. A única tabela criada pela migração inicial é browser_sessions; alembic_version controla as revisões. Contexto e transações tenant-aware são pontos de extensão. O exemplo executável de RLS existe exclusivamente nos testes, com metadata separada do Alembic da aplicação.

## Extensão

Rotas → schemas → serviços → repositórios → modelos. As dependências controlam transações; repositórios/serviços não executam commit. Derive tenant_id e created_by do contexto validado. created_by é auditoria, não uma restrição de propriedade individual.

Cada tabela compartilhada exige tenant_id, índices e FORCE/ENABLE RLS com USING e WITH CHECK. Relações entre registros usam `(tenant_id,parent_id)` para impedir vínculos entre tenants.

A role runtime guilarde_app não é proprietária das tabelas, superuser ou BYPASSRLS. Uma role separada executa migrações. RLS protege consultas acidentalmente sem filtro; não substitui autorização central nem protege contra credenciais da aplicação comprometidas com SQL arbitrário.

Veja o [guia de desenvolvimento](development.md) para os caminhos e a referência de implementação.


## Domínio Capacidade (Fase 1)

Decisão em [ADR-003](adrs/ADR-003-porte-mvp-indicadores-em-fases.md); regras em [project-context.md](project-context.md). Camadas: `api/v1/capacidade.py` → `services/capacidade.py` → `repositories/capacidade.py` → `models/capacidade.py`, com schemas Pydantic de entrada que proíbem campos extras e nunca aceitam `tenant_id`. O dashboard agrega em Python sobre linhas lidas via ORM, porque a guarda SQLite recusa SQL textual.

Tabelas (migração `0002_capacidade`): `grupos`, `semanas` e `lancamentos`, todas com `id` UUID, `tenant_id` e `created_by`. `lancamentos` referencia grupo e semana por chaves estrangeiras compostas `(tenant_id, id)` com `ON DELETE CASCADE`. No PostgreSQL as três têm ENABLE/FORCE RLS com USING e WITH CHECK; no SQLite valem apenas os guardrails do ORM. Fases seguintes (rotinas, FinOps, Despesas & Contratos, Planner pessoal) entram como domínios próprios, cada uma com seus ADRs quando houver decisão arquitetural.

## Domínio Rotinas (Fase 2)

Decisão em [ADR-004](adrs/ADR-004-rotinas-esforco-e-pendencias.md). Mesmas camadas da Capacidade. O cálculo de agenda (dias úteis, datas previstas por tipo de agendamento, vigência, situação e resumo de esforço) fica em `services/rotinas_agenda.py`, módulo puro sem I/O, SQLAlchemy ou FastAPI, para ser testável sem banco; o serviço o alimenta com dataclasses carregadas via ORM.

Tabelas (migração `0003_rotinas`): `rotinas` e `rotina_execucoes`, com `id` UUID, `tenant_id` e `created_by`. `rotina_execucoes` referencia rotina e semana por chaves estrangeiras compostas `(tenant_id, id)` com `ON DELETE CASCADE`, e é única por (tenant, rotina, semana, ocorrência); a ausência de linha significa PENDENTE. No PostgreSQL ambas têm ENABLE/FORCE RLS com USING e WITH CHECK. As ocorrências de rotinas entram no painel da Capacidade pela categoria da rotina.

## Domínio FinOps (Fase 3)

Decisão em [ADR-005](adrs/ADR-005-finops-valor-das-decisoes.md). Mesmas camadas dos domínios anteriores. O cálculo (participantes, janela, status, investimento, ROI e payback) fica em `services/finops_calculos.py`, módulo puro sem I/O; as agregações do painel são feitas em Python, por causa da guarda SQLite.

Tabelas (migração `0004_finops`): `perfis_custo`, `fontes_custo`, `faturas`, `iniciativas` e `iniciativa_participantes`, com `id` UUID, `tenant_id` e `created_by`. `faturas` referencia a fonte e `iniciativa_participantes` referencia a iniciativa por chaves estrangeiras compostas `(tenant_id, id)` com `ON DELETE CASCADE`; `iniciativas` referencia a fonte sem cascata (o serviço responde 409 ao excluir fonte com iniciativas). No PostgreSQL as cinco têm ENABLE/FORCE RLS com USING e WITH CHECK. Os gráficos do frontend são SVG locais, compatíveis com a CSP.

## Domínio Despesas & Contratos (Fase 4)

Decisão em [ADR-006](adrs/ADR-006-despesas-contratos-e-conversao.md). Mesmas camadas dos domínios anteriores. O cálculo (custo contratual e considerado, pontuais, alertas de renovação, % de auditoria e orçamento anual ÷ 12) fica em `services/despesas_calculos.py`, módulo puro sem I/O; as ações cancelar, renegociar e reverter rodam numa única transação do serviço e criam ou apagam a iniciativa de conversão no FinOps.

Tabelas (migração `0005_despesas`): `despesas` e `orcamentos_despesas`, com `id` UUID, `tenant_id` e `created_by`, e as colunas `despesa_id` e `conversao_despesa` em `iniciativas`. `despesas` referencia a fonte de custo e `iniciativas` referencia a despesa por chaves estrangeiras compostas `(tenant_id, id)` sem cascata (o serviço responde 409 ao excluir despesa com iniciativas e fonte com despesas); `orcamentos_despesas` é único por (tenant, competência). No PostgreSQL as duas tabelas novas têm ENABLE/FORCE RLS com USING e WITH CHECK.

## Domínio Planner pessoal (Fase 5)

Decisão em [ADR-007](adrs/ADR-007-planner-pessoal-meu-dia.md). Mesmas camadas dos domínios anteriores, com uma diferença: os dados pertencem a (tenant, sub). O `sub` vem de `ctx.sub` (nunca do corpo) e toda consulta filtra por tenant e sub. A visão "Meu Dia" reutiliza as pendências de Rotinas e o alerta URGENTE de renovação de Despesas, em somente leitura.

Tabelas (migração `0006_planner`): `planner_dias` (única por tenant, sub e data, com `versao` otimista) e `planner_itens`, com `id` UUID, `tenant_id` e `sub`. `planner_itens` referencia o dia por chave estrangeira composta `(tenant_id, dia_id)` com `ON DELETE CASCADE`. No PostgreSQL ambas têm ENABLE/FORCE RLS com a policy `planner_owner`, cujo USING e WITH CHECK exigem `tenant_id` igual a `app.tenant_id` e `sub` igual a `app.subject`; no SQLite valem apenas os guardrails do ORM.

## Desenvolvimento isolado

O perfil dev usa um adaptador de identidade/grants com fixtures locais, sem criar um provedor OIDC falso. A sessão opaca, CSRF e verificação de tenant continuam no mesmo fluxo da aplicação. Configuração e middleware limitam esse adaptador ao ambiente development e ao loopback; endpoints locais não são montados em OIDC/produção.

SQLite não oferece RLS. Transações tenant em dev filtram SELECT ORM e validam escritas de instância via SQLAlchemy; SQL bruto e operações bulk são recusados nesse escopo. Isso permite testes funcionais e não substitui a garantia de RLS, roles e concorrência testada no PostgreSQL. Login OIDC real só é validado pelos testes específicos e em ambiente integrado.
