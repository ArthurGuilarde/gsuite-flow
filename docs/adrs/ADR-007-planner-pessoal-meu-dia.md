# ADR-007 — Planner pessoal "Meu Dia": dados por pessoa, escopo integrado e pendências

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Sessão de implementação da Fase 5 (Planner pessoal): as três decisões abaixo (dados pessoais dentro do tenant, escopo "Meu Dia integrado" e um registro por dia com pendências que migram) foram autorizadas explicitamente pelo usuário na sessão. Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md), [ADR-004](ADR-004-rotinas-esforco-e-pendencias.md), [ADR-006](ADR-006-despesas-contratos-e-conversao.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

O [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md) determinou que o Planner pessoal pertence a (tenant, sub) e teria ADR próprio na fase dele; este é esse registro. No MVP o "Meu Dia" guardava um estado JSON livre no `localStorage` do navegador (e uma tabela `planner_estado`), com foco, prioridades, to-do, notas, hidratação, grade de horários e relógio. O gflow não permite guardar dados de negócio no storage do navegador, e um tenant é um espaço compartilhado: sem uma regra explícita, qualquer membro com leitura veria o planner de outro. Além disso, o sistema já conhece rotinas pendentes ([ADR-004](ADR-004-rotinas-esforco-e-pendencias.md)) e renovações de contratos ([ADR-006](ADR-006-despesas-contratos-e-conversao.md)), que fazem sentido no dia da pessoa.

Restrições: `tenant_id` em todas as tabelas, chaves estrangeiras compostas com tenant, RLS no PostgreSQL, guarda SQLite que recusa SQL textual e frontend com CSP estrita, sem CDN.

## Decisão

1. **Dados pessoais dentro do tenant.** Cada registro do Planner pertence a (`tenant_id`, `sub`). O `sub` vem sempre do contexto validado (`TenantContext`), nunca do corpo da requisição, e toda consulta filtra por tenant **e** sub; dia ou item de outra pessoa responde 404. No PostgreSQL a policy `planner_owner` das duas tabelas restringe também por sujeito: USING e WITH CHECK exigem `tenant_id = app.tenant_id` **e** `sub = app.subject` (o `app.subject` já é definido por transação pelo template). Vale ENABLE/FORCE RLS como nas demais tabelas. Duas pessoas do mesmo tenant não veem nem inserem registros uma da outra, nem por SQL acidentalmente sem filtro.
2. **Escopo "Meu Dia integrado".** O dia tem foco (texto curto), até 3 prioridades, lista de tarefas e notas. A visão do dia também traz o que o sistema já sabe: rotinas que vencem hoje e atrasadas (reutilizando as pendências de Rotinas; concluir pela API existente de Rotinas) e contratos com renovação em até 30 dias (alerta URGENTE de Despesas), somente leitura, com link para o inventário. **Fora do MVP:** hidratação/água, grade de horários, relógio e configurações de horário, e o estado JSON livre em `localStorage`/`planner_estado`. Nada do Planner é guardado no navegador, que mantém só o cookie opaco.
3. **Um registro por dia; pendências migram.** Cada dia é salvo (`planner_dias`, único por tenant, sub e data) e dias passados podem ser consultados. Itens não concluídos de dias anteriores (não concluídos, não descartados e ainda não migrados) aparecem como "pendentes de dias anteriores" e podem ser trazidos para o dia ou descartados. Trazer cria uma cópia no dia de destino, com `origem_item_id` apontando para o original, e marca o original como migrado (`migrado_em`); se o dia já tem 3 prioridades, a cópia entra como tarefa. Descartar marca o item como descartado. Item que não é pendente anterior responde 409. O dia é criado sob demanda na primeira escrita; a leitura não cria nada. Excluir um dia apaga seus itens.
4. **Limites.** No máximo 3 itens do tipo PRIORIDADE e 200 itens por dia (422 além disso); notas de até 20 000 caracteres; texto de item de 1 a 500 caracteres.
5. **Concorrência otimista.** O dia tem `versao`; alterar foco ou notas exige a versão atual, e versão divergente responde 409 com a versão atual. Dia inexistente aceita versão 0 ou ausente. O frontend salva com debounce e, em 409, avisa e recarrega.
6. **Permissões.** Leitura exige read; criar, alterar, concluir, trazer, descartar e remover exigem write, como no resto do sistema. Consequência: quem tem só read não grava no próprio planner. Se isso deve mudar, A definir.
7. **Modelo.** Tabelas `planner_dias` e `planner_itens` (migração `0006_planner`) com UUID, `tenant_id`, `sub` e `updated_at`/`versao` no dia. `planner_itens` referencia o dia por chave estrangeira composta `(tenant_id, dia_id)` com `ON DELETE CASCADE`, tem CHECK de tipo (PRIORIDADE ou TAREFA) e o serviço garante que o `sub` do item é o do dia. `origem_item_id` não tem FK, apenas rastreia a origem.
8. **Contrato.** Rotas em `/api/v1/planner` (visão do dia, foco/notas, itens, histórico e as ações de pendentes); o contrato detalhado vem do OpenAPI gerado, sem cópia manual.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Planner compartilhado por todo o tenant | O usuário definiu o planner como pessoal; um tenant é um espaço compartilhado e o foco/notas de uma pessoa não são dos demais |
| Manter o estado JSON livre em `localStorage`/`planner_estado` como no MVP | Dados no navegador contrariam o invariante de não guardar estado no storage, não valem entre dispositivos e não têm validação nem RLS |
| Manter hidratação, grade de horários e relógio | O usuário escolheu o escopo integrado com rotinas e renovações; esses itens ficaram fora |
| Isolar por pessoa apenas no serviço, sem policy por sujeito | Uma consulta acidentalmente sem filtro de sub exporia dados pessoais; a RLS por `app.subject` é a segunda barreira |
| Pendências somem ou ficam presas ao dia de origem | O usuário quis um registro por dia com pendências que migram (trazer ou descartar), sem perder o histórico |

## Consequências

### Benefícios

Privacidade por pessoa garantida no serviço e na RLS. O dia mostra num lugar o foco, as tarefas, as rotinas pendentes e as renovações urgentes, sem duplicar a regra desses módulos. O histórico por dia é consultável e nenhum dado fica no navegador.

### Custos e limitações

O leitor sem write não grava o planner pessoal. Não há compartilhamento de planner entre pessoas nem política de retenção do histórico: A definir. Quem usava o MVP precisa recadastrar. A visão do dia agrega rotinas e despesas, o que depende desses módulos.

### Riscos

Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL com `app.subject`. Edição simultânea em duas abas: mitigada pela `versao` otimista. Crescimento do histórico sem retenção: monitorar e decidir com novo ADR quando necessário.

## Validação

Critérios: testes de API do Planner (isolamento por pessoa e por tenant, 404 para registro de outra pessoa, limite de 3 prioridades, versão otimista, trazer/descartar pendentes e concluir/reabrir); testes de integração PostgreSQL (RLS ENABLE/FORCE nas duas tabelas, mesmo tenant com sujeito diferente não vê nem insere, tenant divergente negado, FK composta item→dia entre tenants bloqueada e unicidade por tenant, sub e data). Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md)
- [ADR-004](ADR-004-rotinas-esforco-e-pendencias.md)
- [ADR-006](ADR-006-despesas-contratos-e-conversao.md)
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão da Fase 5 |
