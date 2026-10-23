# ADR-005 — FinOps: valor financeiro das decisões

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Sessão de implementação da Fase 3 (FinOps): objetivos e escolhas expressos pelo usuário na sessão. Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

A Fase 3 do porte ([ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)) traz o FinOps. No MVP o módulo girava em torno de lançamentos de fatura (Fabric) e de um "saving" derivado de histórico e de sincronização automática fatura→saving. O usuário pediu para não se prender a esse desenho: além das faturas, o módulo deve registrar melhorias e automações feitas pelo time, considerar por padrão os savings por 6 meses antes de se tornarem um novo normal e ajudar os gestores a demonstrar financeiramente a tomada de decisão e como ela afeta o financeiro.

Restrições: `tenant_id` em todas as tabelas, chaves estrangeiras compostas com tenant, RLS no PostgreSQL, guarda SQLite que recusa SQL textual (agregações em Python) e frontend com CSP `script-src 'self'; style-src 'self'`, sem CDN.

## Decisão

1. **Iniciativas são a fonte única de saving.** Uma iniciativa tem tipo MELHORIA, AUTOMACAO ou OTIMIZACAO_CUSTO e modo de cálculo DIRETO_REAIS (valor mensal informado) ou POR_TEMPO (horas economizadas convertidas em R$ por perfis de custo/hora).
2. **Janela padrão de 6 meses, editável.** Toda iniciativa nasce com `janela_meses = 6`, editável por iniciativa (1 a 60). O saving soma do mês de início até o fim da janela (ou até o mês de encerramento, se houver). Depois da janela a iniciativa vira NOVO_NORMAL e deixa de somar saving no período. Status: PLANEJADA, EM_SAVING, NOVO_NORMAL e ENCERRADA, calculados no backend para um mês de referência.
3. **Faturas só acompanham.** Fontes de custo e faturas mostram orçado × realizado, variação e custo unitário (realizado ÷ métrica), mas não somam saving, evitando dupla contagem. Uma otimização de fatura é registrada como iniciativa OTIMIZACAO_CUSTO (normalmente DIRETO_REAIS) que pode apontar para a fonte de custo; a fonte exibe o saving das iniciativas ligadas apenas como contexto.
4. **Perfis de custo/hora com snapshot.** O tenant cadastra perfis (por exemplo Analista R$ 80, Executivo R$ 300). Uma iniciativa POR_TEMPO tem participantes com perfil, quantidade de pessoas e horas antes e depois por execução. O nome e o custo/hora do perfil são copiados para o participante ao salvar; alterar o perfil depois não reescreve o passado. A diferença de horas pode ser negativa e não sofre clamp. O formulário sugere R$ 80 quando não há perfil.
5. **Investimento, ROI e payback.** O investimento é opcional (R$ e/ou horas do time com custo/hora). O sistema calcula ROI na janela e payback em meses, e indica se a iniciativa se paga na janela.
6. **Constantes do MVP.** FTE = horas ÷ 168. Multiplicadores de frequência por mês: DIARIA_UTIL 22, DIARIA_CORRIDA 30, SEMANAL 4,33, QUINZENAL 2 e MENSAL 1.
7. **Saiu do MVP:** a tabela de meses cadastráveis (a competência é derivada de datas e gravada como data no dia 1), o histórico de saves como fonte de saving, a busca "fabric" por nome, a sincronização automática fatura→saving e o Chart.js por CDN.
8. **Gráficos em SVG local.** Os gráficos do painel são SVG criados com `createElementNS` e cores por classe CSS, compatíveis com a CSP e sem dependências externas.
9. **Modelo.** Tabelas `perfis_custo`, `fontes_custo`, `faturas`, `iniciativas` e `iniciativa_participantes` (migração `0004_finops`), com UUID, `tenant_id`, `created_by`, RLS ENABLE/FORCE (USING e WITH CHECK) no PostgreSQL e FKs compostas `(tenant_id, id)`: fatura→fonte e participante→iniciativa com `ON DELETE CASCADE`; iniciativa→fonte sem cascata (o serviço responde 409 ao excluir fonte com iniciativas). O cálculo fica em módulo puro `src/backend/services/finops_calculos.py`, sem I/O.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Manter o desenho do MVP (faturas geram saving) | O usuário quer demonstrar decisões e melhorias do time, não só faturas; somar fatura e iniciativa duplicaria o saving |
| Contar o saving para sempre | O usuário definiu que o saving vale por uma janela e depois se torna o novo normal |
| Custo/hora fixo único | Não representa equipes com perfis diferentes (analista e executivo na mesma iniciativa) |
| Referenciar o perfil por FK nos participantes | Alterar o perfil reescreveria o passado; o snapshot é auditável |
| Manter Chart.js por CDN | Viola a CSP e a regra de não depender de CDN |

## Consequências

### Benefícios

O gestor demonstra o efeito financeiro de cada decisão com regra clara (janela, novo normal, ROI e payback), sem dupla contagem. O cálculo puro é testável sem banco e os dados de tenant ficam isolados por RLS e FKs compostas.

### Custos e limitações

Saving por tempo depende de estimativas informadas pelo time (horas antes e depois). Os multiplicadores de frequência são aproximações do MVP. A agregação do painel é feita em Python. Moeda além de BRL, fuso horário, fechamento contábil e fluxo de aprovação de iniciativas: A definir.

### Riscos

Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL (RLS FORCE, tenant divergente negado e FKs compostas entre tenants). Estimativas otimistas inflarem o saving: o snapshot de custo/hora e o investimento opcional dão rastreabilidade; validação por aprovação: A definir.

## Validação

Critérios: testes unitários do módulo de cálculo (participantes, janela, status, investimento, ROI e payback); testes de API de perfis, fontes, faturas, iniciativas, simulação e painel; testes de integração PostgreSQL das cinco tabelas (RLS ENABLE/FORCE, tenant divergente negado e FKs compostas). Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão da Fase 3 |
