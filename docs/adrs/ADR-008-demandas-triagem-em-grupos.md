# ADR-008 — Demandas: triagem como grupo de sistema e contagem no painel

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Decisões explicitamente autorizadas pelo usuário na sessão de implementação da Fase 6 (Demandas), incluindo a correção de que filas separadas dos Grupos estavam erradas. Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md), [ADR-004](ADR-004-rotinas-esforco-e-pendencias.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

O [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md) organiza o porte em fases. A Fase 6 adiciona um canal para que pessoas do tenant peçam trabalho à equipe e para que a equipe triei e distribua esses pedidos. O painel BUILD × RUN da Capacidade soma, por Grupo (squad), itens abertos e resolvidos; o [ADR-004](ADR-004-rotinas-esforco-e-pendencias.md) já soma as ocorrências de rotinas nesse painel, calculadas na hora e sem gravar Lançamentos. O usuário determinou que uma demanda precisa cair no aberto/resolvido do seu Grupo, e não em um cadastro paralelo.

Os tenants vêm do Core vazios; portanto nenhuma migração pode criar o ponto de entrada de cada tenant. O invariante do projeto é que escrever exige write; abrir uma demanda por quem só tem read é uma exceção que precisa ser explícita e restrita.

Restrições: `tenant_id` em todas as tabelas, chaves estrangeiras compostas com tenant, RLS no PostgreSQL, guarda SQLite que recusa SQL textual, repositórios e serviços sem commit e contrato vindo do OpenAPI gerado.

## Decisão

1. **Demandas pertencem a Grupos.** Não existe cadastro de filas. Toda demanda tem `grupo_id` (obrigatório) para um Grupo da Capacidade. Classificar é mover a demanda da Triagem para outro Grupo.
2. **Triagem é um Grupo de sistema.** Grupo "Triagem", categoria RUN, ícone "📥", cor "#64748B", marcado por `grupos.sistema` (bool, padrão falso). O serviço de Capacidade (`garantir_triagem`) o cria de forma idempotente por tenant no primeiro uso; é chamado em `listar_grupos`, no dashboard e em toda função do serviço de Demandas. Se já existir um grupo não-sistema chamado "Triagem", ele é adotado (sistema, RUN, ativo). A criação usa savepoint (`db.begin_nested()`) e absorve o `IntegrityError` de corrida; um índice único parcial em `tenant_id` onde `sistema` é verdadeiro garante um só grupo de sistema por tenant. Protegido: não pode ser excluído, renomeado, desativado nem mudar de categoria (409); ícone e cor podem mudar. Não é destino de classificação (422). Migração não pode criá-lo, porque os tenants começam vazios.
3. **Ciclo.** ABERTA → CONCLUIDA (reabrir volta para ABERTA) e ABERTA → CANCELADA. Classificar só troca o grupo (e, opcionalmente, a prioridade), registra `classificado_por`/`classificado_em` e não muda o status; só vale para ABERTA (409 nos demais). Concluir registra `concluido_por`/`concluido_em` e pode ocorrer na própria Triagem; reabrir limpa esses campos; cancelar registra `cancelado_em`. Transição inválida responde 409. Grupo de destino de outro tenant ou inexistente responde 404; grupo de sistema ou inativo, 422.
4. **Contagem no painel BUILD × RUN.** Calculada na hora, como as rotinas, e nunca gravada em Lançamentos. ABERTA conta como aberto do grupo atual; CONCLUIDA conta como resolvido; CANCELADA não conta. Com semana selecionada que tem datas, ABERTA conta se a data de abertura (`created_at`) cai em `[data_inicio, data_fim]`, e CONCLUIDA conta se a data de conclusão (`concluido_em`) cai no período; semana sem datas não recebe demandas; sem semana selecionada somam todas as ABERTAS e CONCLUIDAS. Grupo inativo não soma, igual aos lançamentos. As datas usam o relógio do servidor. `GrupoDashboard` ganha `demandas_abertas` e `demandas_resolvidas`, já incluídos em `abertos`/`resolvidos` e nos totais BUILD/RUN; `GrupoView` ganha `sistema`. `calcular_dashboard` recebe a contagem de demandas por grupo como função pura.
5. **Solicitante com apenas read (exceção explícita).** Abrir uma demanda exige apenas read, exceção limitada à regra "escrever exige write". O solicitante (`solicitante_sub`) vem sempre de `ctx.sub`, nunca do corpo. Sem write, a pessoa vê apenas as demandas que abriu (a de outra responde 404). Com write (equipe): vê todas, classifica, conclui, reabre e cancela. A demanda nasce no grupo Triagem, com status ABERTA.
6. **Modelo.** Migração `0007_demandas` (`down_revision` `0006_planner`): coluna `grupos.sistema` com o índice único parcial (`sqlite_where`/`postgresql_where`; o downgrade os remove, em lote no SQLite) e a tabela `demandas` com `id` UUID, `tenant_id`, `created_by`, `created_at`, `updated_at`, `grupo_id`, título, descrição, prioridade (CHECK BAIXA/MEDIA/ALTA), status (CHECK ABERTA/CONCLUIDA/CANCELADA), `solicitante_sub` e os campos de classificação, conclusão e cancelamento. CHECK: `concluido_em` preenchido somente quando o status é CONCLUIDA. Chave estrangeira composta `(tenant_id, grupo_id)` para `grupos(tenant_id, id)` com `ON DELETE RESTRICT` e UNIQUE `(tenant_id, id)`. Excluir grupo com demandas responde 409 ("reclassifique as demandas"); lançamentos continuam em cascata. No PostgreSQL, `demandas` tem ENABLE/FORCE RLS com a policy padrão de tenant (USING e WITH CHECK por `app.tenant_id`) e GRANT a `guilarde_app`. Não há policy por sujeito: o filtro do solicitante é do serviço.
7. **Contrato.** Rotas em `/api/v1/demandas`, tag `demandas`: abrir, listar (filtros status, grupo, minhas), obter, `classificar`, `concluir`, `reabrir` e `cancelar`. Não há rotas de filas; a Triagem é descoberta pela listagem de grupos (`sistema: true`). O contrato detalhado vem do OpenAPI gerado, sem cópia manual.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Filas separadas dos Grupos (`demanda_filas`) | Primeiro rascunho, descartado pelo usuário: a demanda precisa cair no aberto/resolvido do grupo no painel BUILD × RUN |
| Gravar as demandas nos Lançamentos | Duplicaria o dado e exigiria sincronização; o usuário aceitou o padrão das rotinas, com contagem calculada na hora |
| Triagem fora do painel ou na categoria BUILD | A Triagem é trabalho de atendimento e conta como RUN no painel; o usuário definiu a categoria RUN |
| Ciclo com EM_ANDAMENTO | O usuário escolheu o ciclo ABERTA/CONCLUIDA/CANCELADA; o andamento não foi pedido |
| Criar a Triagem por migração ou por ação explícita | Os tenants vêm do Core e começam vazios, então a migração não alcança tenants futuros; a ação explícita deixaria o módulo inutilizável até alguém executá-la. O usuário escolheu a criação automática e idempotente |
| Exigir write para abrir demanda | Impediria o solicitante comum, que só tem read, de pedir trabalho; o usuário autorizou a exceção explícita |

## Consequências

### Benefícios

Qualquer membro com read abre um pedido e acompanha os próprios sem ver os dos demais. A demanda entra no painel BUILD × RUN pelo seu grupo, sem cadastro paralelo e sem duplicar dados. Todo pedido tem destino inicial garantido e rastreável (quem classificou e quando).

### Custos e limitações

A exceção read-abre-demanda é uma regra a mais para manter e testar. A Capacidade passa a conhecer um grupo de sistema e a contagem de demandas. Toda função de listagem, dashboard e Demandas paga uma verificação da Triagem. A semana é contada pela data de abertura/conclusão, no relógio do servidor. Fora do escopo (A definir): notificações, responsável dentro do grupo, solicitante cancelar a própria demanda, anexos e comentários, fuso por tenant para as datas de abertura e conclusão.

### Riscos

Vazamento entre solicitantes, já que a RLS é só por tenant e o filtro por solicitante é do serviço: mitigado por testes de API que exigem 404 para demanda de outro e por listagem sempre filtrada sem write. Corrida na criação da Triagem: mitigada pelo índice único parcial, pelo savepoint e pela absorção do `IntegrityError`. Uso de `ctx.permissions` para decidir a visão: depende do Core ser a autoridade das permissões. Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL.

## Validação

Critérios: testes de API de Demandas (Triagem criada uma vez e adotada se já existir; protegida contra excluir, renomear, desativar e mudar de categoria; solicitante só com read abre e vê só as próprias, 404 para as de outro; equipe com write vê todas, classifica, conclui, reabre e cancela; transições inválidas 409; destino de sistema ou inativo 422, inexistente ou de outro tenant 404; excluir grupo com demandas 409; validação de prioridade e tamanho de campos); testes puros de `calcular_dashboard` com demandas (ABERTA, CONCLUIDA, CANCELADA, semana com e sem datas, grupo inativo); testes de integração PostgreSQL (RLS ENABLE/FORCE em `demandas`, tenant divergente negado, FK composta demanda→grupo entre tenants bloqueada, um grupo de sistema por tenant). Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)
- [ADR-004](ADR-004-rotinas-esforco-e-pendencias.md)
- [ADR-009](ADR-009-demandas-historico-e-comentarios.md) — complementa com detalhe, histórico e comentários
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão da Fase 6; o primeiro rascunho, com filas separadas, foi corrigido pelo usuário na mesma sessão, antes de qualquer commit |
