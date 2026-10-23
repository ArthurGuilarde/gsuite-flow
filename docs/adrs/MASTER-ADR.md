# 📋 Master ADR — Guilarde Suite

> Registro central dos Architecture Decision Records deste projeto.
> Cada entrada referencia um ADR completo com contexto, decisão, alternativas e consequências.

**Última atualização:** 2026-10-15  
**Projeto:** template_suite_guilarde — Guilarde  
**Stack principal:** FastAPI · SQLAlchemy 2 · Alembic · SQLite (dev) / PostgreSQL (integrated/prod) · Vanilla HTML/CSS/JS · Python

> [!NOTE]
> Ao criar uma aplicação, ajuste os metadados e revise os ADRs herdados. Status Em discussão não representa uma decisão aprovada. Decisões de outros projetos permanecem nos respectivos repositórios.

---

## Tabela Resumo

| # | ADR | Data | Status | Área | Decisão Resumida |
|---|---|---|---|---|---|

| 001 | [Base mínima sem domínio de demonstração](ADR-001-base-minima-sem-dominio.md) | 2026-10-15 | 🔄 Em discussão | Estrutura do template | Infraestrutura no runtime, domínio/RLS de referência só nos testes e baseline distinta para bancos novos. |

| 002 | [Desenvolvimento isolado e perfis de execução](ADR-002-perfis-dev-integrated-production.md) | 2026-10-15 | ✅ Aceito | Operação e desenvolvimento | SQLite e fixtures apenas em dev; PostgreSQL/OIDC nos perfis externos; CLI serve/migrate/check. |

## Mapa de Dependências

ADR-002 usa a estrutura de partida descrita em [ADR-001](ADR-001-base-minima-sem-dominio.md), sem alterar seu status.

## Índice por Área

### Estrutura do template

- [ADR-001](ADR-001-base-minima-sem-dominio.md) — Base mínima sem domínio de demonstração

### Operação e desenvolvimento

- [ADR-002](ADR-002-perfis-dev-integrated-production.md) — Desenvolvimento isolado e perfis de execução

## Como Criar um Novo ADR

1. Leia a [convenção obrigatória](README.md).
2. Copie [TEMPLATE-ADR.md](TEMPLATE-ADR.md) para `docs/adrs/ADR-NNN-descricao-curta.md`.
3. Preencha o registro, incluindo status e origem real da decisão.
4. Atualize a tabela acima, o índice por área, as dependências aplicáveis e a data deste Master.
5. Confira que o ID da tabela corresponde ao título e ao nome do arquivo.

*Mantenha este índice junto com os ADRs na mesma alteração.*
