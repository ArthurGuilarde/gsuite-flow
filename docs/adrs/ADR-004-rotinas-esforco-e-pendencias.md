# ADR-004 — Rotinas: esforço medido e pendências

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Sessão de implementação da Fase 2 (Rotinas): objetivos e escolhas expressos pelo usuário na sessão. Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

A Fase 2 do porte ([ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)) traz as Rotinas: tarefas recorrentes da engenharia. O usuário definiu dois objetivos para o módulo: (1) medir quanto esforço está sendo gasto e (2) garantir que nada do que precisa ser mantido fique para trás.

No MVP, as rotinas só contavam ocorrências: cada execução era PENDENTE ou CONCLUIDA, sem tempo. A soma no painel BUILD x RUN dependia de localizar pelo nome o grupo "Rotinas (N0)". Não havia lista de pendências: uma ocorrência não concluída de uma semana passada só era vista ao abrir aquela semana. O MVP também trazia uma grade fixa de agenda (blocos por dia e período), campos redundantes (`data_especifica`, `recorrencia`, status no catálogo) e `semana_inicio_id` como vigência. O gflow exige `tenant_id` em todas as tabelas, chaves estrangeiras compostas com tenant e RLS, e a guarda SQLite recusa SQL textual.

## Decisão

1. **Esforço = contagem + minutos.** Cada rotina tem `esforco_estimado_min` por ocorrência (0–1440). Uma execução concluída pode registrar `esforco_real_min`. Os relatórios mostram, por categoria, ocorrências, concluídas, pendentes, minutos previstos e minutos executados. Minutos executados usam o tempo real quando existe e o estimado quando não.
2. **Painel pela categoria.** As ocorrências de rotinas entram no painel BUILD x RUN pela categoria da própria rotina, em linhas próprias "Rotinas" (aberto = pendente; resolvido = concluída). O truque do MVP de achar o grupo "Rotinas (N0)" pelo nome deixa de existir. O grupo padrão "Rotinas (N0)" continua disponível para lançamentos manuais, mas as rotinas cadastradas não somam mais nele.
3. **Data prevista no backend e pendências.** O backend calcula a data prevista de cada ocorrência (módulo puro `src/backend/services/rotinas_agenda.py`, sem I/O). A API lista as pendências que vencem hoje e as atrasadas (pendentes com data prevista passada, de qualquer semana) até serem concluídas. Os dias úteis são segunda a sexta e ignoram feriados.
4. **Modelo.** Tabelas `rotinas` e `rotina_execucoes` (migração `0003_rotinas`), com UUID, `tenant_id`, `created_by`, RLS ENABLE/FORCE (USING e WITH CHECK) no PostgreSQL e FKs compostas `(tenant_id, id)` com `ON DELETE CASCADE` de execução para rotina e para semana. A ocorrência é única por (tenant, rotina, semana, ocorrência). A ausência de linha de execução significa PENDENTE.
5. **Grade de agenda fora desta fase.** Os blocos fixos por dia e período do MVP, o endpoint de agenda e o campo `bloco` não são portados.
6. **Remoções e substituições do porte:**
   - `data_especifica` sai: o MVP nunca a usava no agendamento.
   - O status no nível do catálogo sai: o status existe só por ocorrência/semana.
   - O campo texto `recorrencia` sai: é derivado do tipo de agendamento.
   - Os aliases de tipo de agendamento (por exemplo MENSAL, 1_UTIL, ULTIMO_DIA) são normalizados na entrada para seis tipos canônicos.
   - `semana_inicio_id` vira `inicio_vigencia` (date), porque uma FK composta com tenant não admite `ON DELETE SET NULL` sem anular `tenant_id`.
   - Rotinas inativas aparecem numa semana só se tiverem execução registrada nela, preservando o histórico de esforço.
   - As "rotinas padrão" (exemplos semanais e mensais do MVP, sem links internos e com esforço 0) são criadas só por ação explícita, como os grupos padrão.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Só contagem, como no MVP | Não responde "quanto esforço está sendo gasto", objetivo central do usuário |
| Somar todas as rotinas no grupo "Rotinas (N0)" | Mistura BUILD e RUN em N0 e depende do nome do grupo; a categoria da rotina é a informação correta |
| Calcular "vence hoje" apenas no cliente | O cálculo dependeria do navegador e de cada tela, sem lista única de atrasadas entre semanas; o backend é testável e o fuso é decidido em um lugar |
| Manter a grade fixa de agenda do MVP | O usuário a deixou fora da fase; os blocos eram dados fixos no código, sem tenant |
| Manter `semana_inicio_id` como FK | `SET NULL` em FK composta com tenant anularia `tenant_id` (NOT NULL); `inicio_vigencia` é mais simples e independe de semanas |

## Consequências

### Benefícios

O esforço fica mensurável por categoria e as pendências ficam visíveis até a conclusão. O painel BUILD x RUN passa a refletir as rotinas sem depender do nome de um grupo. A lógica de agenda é pura e testável sem banco.

### Custos e limitações

Quem usava o grupo "Rotinas (N0)" para as rotinas deve saber que elas agora somam pela categoria; lançamentos manuais no grupo continuam válidos. Dias úteis ignoram feriados. A data "hoje" usa o relógio do servidor; fuso horário por tenant: A definir. Metas de esforço: A definir. A grade de agenda: A definir (fora da fase). O cálculo de pendências lê as semanas com datas e expande em Python, aceitável no volume atual.

### Riscos

Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL (RLS FORCE, isolamento, FK composta, unicidade da ocorrência e cascatas). Datas calculadas podem divergir do calendário real em feriados: limitação declarada.

## Validação

Critérios: testes unitários do módulo de agenda (dias úteis, tipos de agendamento, vigência, situação e resumo de esforço); testes de API das rotinas, pendências e do painel; testes de integração PostgreSQL das tabelas `rotinas` e `rotina_execucoes`. Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão da Fase 2 |
