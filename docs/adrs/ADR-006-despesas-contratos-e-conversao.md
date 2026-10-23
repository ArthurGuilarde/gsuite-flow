# ADR-006 — Despesas & Contratos: inventário, orçamento e conversão em iniciativa

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Sessão de implementação da Fase 4 (Despesas & Contratos): as três decisões abaixo (conversão via iniciativa, orçamento mensal e ligação com fonte de custo) foram autorizadas explicitamente pelo usuário na sessão. Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-005](ADR-005-finops-valor-das-decisoes.md), [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

A Fase 4 do porte ([ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)) traz Despesas & Contratos. No MVP o módulo mantinha um inventário de despesas com status de auditoria, alertas de renovação e uma tabela própria de "ações de economia" (cancelamento e renegociação) que gerava saving fora do FinOps. Desde o [ADR-005](ADR-005-finops-valor-das-decisoes.md), as iniciativas são a fonte única de saving; manter uma segunda tabela de ações duplicaria o saving e a regra de janela. Além disso, o usuário quis que a despesa dialogue com as fontes de custo e faturas já existentes e que haja orçamento mensal opcional.

Restrições: `tenant_id` em todas as tabelas, chaves estrangeiras compostas com tenant, RLS no PostgreSQL, guarda SQLite que recusa SQL textual (agregações em Python) e frontend com CSP estrita, sem CDN.

## Decisão

1. **Inventário e auditoria.** Uma despesa tem nome, fornecedor, categoria (texto livre; o frontend sugere as seis categorias do MVP), tipo de custo RECORRENTE_MENSAL ou PONTUAL, valor (mensal na recorrente; total na pontual), datas de início e de renovação, responsável e observações. O status de auditoria é EM_REVISAO (inicial), VALIDADO, DESPERDICIO, CANCELADO ou RENEGOCIADO. CANCELADO e RENEGOCIADO só são atingidos pelas ações (decisão 2); o PATCH os recusa.
2. **Cancelar e renegociar criam uma iniciativa vinculada.** A ação roda em transação única: muda a despesa (status, `mes_acao`, e `valor`/`valor_anterior` na renegociação) e, quando há economia mensal, cria uma iniciativa OTIMIZACAO_CUSTO, DIRETO_REAIS, com `valor_mensal` igual ao custo mensal eliminado (cancelamento) ou ao valor anterior menos o novo (renegociação), `mes_inicio` no mês da ação, janela padrão de 6 meses (editável na ação), fonte de custo herdada da despesa, `despesa_id` e `conversao_despesa = true`. Cancelar despesa PONTUAL só muda o status, sem iniciativa. **Reverter** apaga as iniciativas de conversão da despesa, restaura o valor anterior (se renegociada), zera `valor_anterior` e `mes_acao` e aplica o novo status escolhido (EM_REVISAO, VALIDADO ou DESPERDICIO). As "ações de economia" do MVP passam a ser iniciativas ligadas à despesa por `despesa_id`; não existe tabela de ações.
3. **Orçamento mensal, opcional.** Tabela `orcamentos_despesas` com um valor por competência (data no dia 1), única por (tenant, competência). Há um atalho "anual ÷ 12": onze meses com `round(valor/12, 2)` e dezembro com o resto, de modo que a soma é exata; sem sobrescrever, meses já cadastrados são ignorados. Toda a tela e o painel funcionam sem orçamento cadastrado (orçado e variação ficam nulos).
4. **Ligação opcional despesa → fonte de custo.** A despesa pode apontar para uma fonte de custo do FinOps. Com ligação, o **custo considerado** do mês vem do realizado da fatura da fonte na competência (origem FATURA); sem fatura no mês, vale o custo contratual (origem CONTRATO). No mês de referência atual, se não houver fatura em M, usa-se a última fatura anterior da fonte, se existir. Na série mensal histórica, só se usa a fatura do próprio mês ou o contrato.
5. **Regras de cálculo.** O custo mensal contratual é zero para PONTUAL, antes de `data_inicio`, para CANCELADO a partir do mês da ação, e usa `valor_anterior` antes do mês da ação de uma renegociada. Pontuais entram no mês de `data_inicio`, exceto canceladas. Alertas de renovação cobrem hoje até hoje + 60 dias, exceto canceladas: URGENTE até 30 dias, ATENCAO acima disso. A % de auditoria é a fração de despesas fora de EM_REVISAO. O cálculo fica em módulo puro `src/backend/services/despesas_calculos.py` (Decimal, sem I/O).
6. **O que muda no FinOps.** `iniciativas` ganha `despesa_id` (FK composta com tenant para `despesas`) e `conversao_despesa` (boolean, padrão falso). A iniciativa aceita `despesa_id` como vínculo manual (404 se a despesa não for do tenant); no PUT de uma iniciativa de conversão o `despesa_id` não pode mudar (422); excluir iniciativa de conversão responde 409 (reverter pela despesa); excluir fonte com despesas vinculadas também responde 409; a simulação ignora `despesa_id`. A view da iniciativa expõe `despesa_id`, `despesa_nome` e `conversao_despesa`. Excluir despesa com qualquer iniciativa vinculada responde 409.
7. **Modelo.** Tabelas `despesas` e `orcamentos_despesas` e as colunas novas de `iniciativas` (migração `0005_despesas`), com UUID, `tenant_id`, `created_by`, RLS ENABLE/FORCE (USING e WITH CHECK) no PostgreSQL e FKs compostas `(tenant_id, id)` sem cascata: despesa→fonte e iniciativa→despesa.
8. **Painel.** O painel de despesas traz run-rate mensal e anual, pontuais do ano, desperdício, saving capturado e novo normal (das iniciativas vinculadas), orçado × realizado, % de auditoria, alertas de renovação, série mensal do ano, por categoria e por status. Agregação em Python; gráficos SVG locais reutilizando os do FinOps.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Manter tabela própria de ações de economia como no MVP | Duplicaria a fonte de saving do [ADR-005](ADR-005-finops-valor-das-decisoes.md) e a regra de janela de 6 meses |
| Despesa sem ligação com fonte de custo | O usuário quis usar o realizado das faturas quando existir, evitando manter o mesmo custo em dois lugares |
| Orçamento obrigatório | O usuário definiu o orçamento como opcional; tudo deve funcionar sem ele |
| Gravar o valor do orçamento anual e derivar os meses | Orçamento é mensal por competência; o anual ÷ 12 é só um atalho de preenchimento |

## Consequências

### Benefícios

O saving de cancelamentos e renegociações aparece no painel FinOps com a mesma regra (janela, novo normal), sem dupla contagem. A reversão é simples e consistente. O custo considerado reflete a fatura real quando há fonte ligada. Os dados de tenant ficam isolados por RLS e FKs compostas.

### Custos e limitações

Excluir despesa ou iniciativa de conversão exige reverter antes. A ligação com fonte usa a fatura da competência, sem rateio. Despesas recorrentes anuais, multi-moeda, cancelamento de despesa pontual com saving e fluxo de aprovação: A definir.

### Riscos

Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL (RLS FORCE, tenant divergente negado e FKs compostas entre tenants). Inconsistência entre despesa e iniciativa de conversão: mitigada por transação única nas ações e pelos 409 que impedem edição direta.

## Validação

Critérios: testes unitários do módulo de cálculo (custo contratual e considerado, pontuais, alertas, % de auditoria e anual ÷ 12); testes de API de despesas, ações (cancelar, renegociar e reverter), orçamentos e painel; testes dos 409 e 422 no FinOps; testes de integração PostgreSQL das tabelas novas (RLS ENABLE/FORCE, tenant divergente negado, FKs compostas despesa→fonte e iniciativa→despesa e unicidade de orçamento por competência). Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)
- [ADR-005](ADR-005-finops-valor-das-decisoes.md)
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão da Fase 4 |
