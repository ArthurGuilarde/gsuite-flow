# ADR-003 — Porte do MVP Indicadores de Engenharia em fases

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Sessão de implementação: pedido do usuário para implementar o MVP "Indicadores de Engenharia" como o gflow e suas respostas sobre fases, tenant, dados e Planner. Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-001](ADR-001-base-minima-sem-dominio.md) (ainda Em discussão; este ADR não altera seu status), [ADR-002](ADR-002-perfis-dev-integrated-production.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

O MVP de referência é uma aplicação Flask com SPA em Vanilla JS que acompanha capacidade BUILD ≥ 70% / RUN ≤ 30%, rotinas, Planner pessoal ("Meu Dia"), FinOps e Despesas & Contratos. O gflow parte de uma base sem domínio, com identidade no Authentik, memberships no Core, isolamento por tenant com RLS e frontend com CSP estrita. Era preciso decidir como e em que ordem portar o MVP respeitando os invariantes do AGENTS.md. Em dev, a guarda SQLite recusa SQL textual, e o SQL do MVP usa construções próprias do seu banco.

## Decisão

1. **Porte por fases.** A Fase 1 é Capacidade: grupos, semanas, lançamentos ABERTO/RESOLVIDO e dashboard BUILD × RUN. Rotinas (N0 só soma no dashboard na Fase 2), Planner pessoal, FinOps e Despesas & Contratos ficam para fases seguintes.
2. **Tenant = cliente.** Um tenant representa um cliente (PF ou PJ) que contrata o sistema; membros e ingresso vêm do Core.
3. **Sem migração de dados.** Cada tenant começa vazio; os grupos padrão do MVP só são criados por ação explícita.
4. **Modelo de dados.** Chaves UUID, `tenant_id` e `created_by` em todas as tabelas, e chaves estrangeiras compostas `(tenant_id, id)` entre lançamentos, grupos e semanas, com `ON DELETE CASCADE`. Migração `0002_capacidade`.
5. **ORM com agregação em Python.** O dashboard lê linhas pelo ORM e agrega em Python, em vez de SQL textual, porque a guarda SQLite recusa SQL textual.
6. **RLS no PostgreSQL.** `grupos`, `semanas` e `lancamentos` usam ENABLE/FORCE RLS com USING e WITH CHECK e concessões à role de runtime.
7. **Frontend em ES modules com CSP estrita.** `script-src 'self'`, sem handlers inline, sem CDN e sem `innerHTML` com dados.
8. **Remoções do MVP.** Alias `/api` legado, `audit_log`, `/metrics/latest`, `/raw`, exportação HTML standalone e "copiar contexto LLM" (que volta com Rotinas, a partir da Fase 2).
9. **Planner pessoal** pertence a (tenant, sub) e terá ADR próprio na fase dele; não é decidido aqui. O registro dessa decisão é o [ADR-007](ADR-007-planner-pessoal-meu-dia.md).

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Copiar o SQL do MVP | A guarda SQLite recusa SQL textual e o SQL não carrega tenant nem RLS |
| Manter Flask | Contraria a base FastAPI/SQLAlchemy/Alembic e os perfis do ADR-002 |
| Importar os dados do MVP | O usuário optou por começar do zero; o MVP não tem tenant nem o modelo de identidade do Core |
| Portar tudo de uma vez | Aumenta o risco e o tamanho da revisão; o usuário pediu fases |

## Consequências

### Benefícios

Entrega incremental e verificável; isolamento por tenant garantido por FKs compostas e RLS; o mesmo código funciona em SQLite (dev) e PostgreSQL; frontend compatível com a CSP.

### Custos e limitações

A agregação em Python lê mais linhas que um GROUP BY, o que é aceitável no volume atual. Quem usava o MVP precisa recadastrar os dados. Funcionalidades removidas deixam de existir até serem reintroduzidas. Metas fixas em 70%/30% (configuráveis por tenant: A definir).

### Riscos

Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL. Volume maior pode exigir agregação no banco: reavaliar com novo ADR.

## Validação

Critérios: testes unitários e de API de Capacidade; testes de integração PostgreSQL (RLS FORCE, isolamento de SELECT/INSERT/UPDATE/DELETE, FK composta entre tenants, cascata e fluxo autorizado da API). Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-001](ADR-001-base-minima-sem-dominio.md) e [ADR-002](ADR-002-perfis-dev-integrated-production.md)
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão de porte |
