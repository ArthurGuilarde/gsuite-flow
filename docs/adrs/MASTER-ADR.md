# 📋 Master ADR — Guilarde Suite

> Registro central dos Architecture Decision Records deste projeto.
> Cada entrada referencia um ADR completo com contexto, decisão, alternativas e consequências.

**Última atualização:** 2026-10-23  
**Projeto:** GFlow  
**Stack principal:** FastAPI · SQLAlchemy 2 · Alembic · SQLite (dev) / PostgreSQL (integrated/prod) · Vanilla HTML/CSS/JS · Python

> [!NOTE]
> Ao criar uma aplicação, ajuste os metadados e revise os ADRs herdados. Status Em discussão não representa uma decisão aprovada. Decisões de outros projetos permanecem nos respectivos repositórios.

---

## Tabela Resumo

| # | ADR | Data | Status | Área | Decisão Resumida |
|---|---|---|---|---|---|

| 001 | [Base mínima sem domínio de demonstração](ADR-001-base-minima-sem-dominio.md) | 2026-10-15 | 🔄 Em discussão | Estrutura do template | Infraestrutura no runtime, domínio/RLS de referência só nos testes e baseline distinta para bancos novos. |

| 002 | [Desenvolvimento isolado e perfis de execução](ADR-002-perfis-dev-integrated-production.md) | 2026-10-15 | ✅ Aceito | Operação e desenvolvimento | SQLite e fixtures apenas em dev; PostgreSQL/OIDC nos perfis externos; CLI serve/migrate/check. |

| 003 | [Porte do MVP Indicadores de Engenharia em fases](ADR-003-porte-mvp-indicadores-em-fases.md) | 2026-10-23 | ✅ Aceito | Produto e domínio | Porte por fases (Fase 1 Capacidade), tenant = cliente PF/PJ, sem migração de dados, UUID e FKs compostas, ORM, RLS e frontend ES modules com CSP estrita. |

| 004 | [Rotinas: esforço medido e pendências](ADR-004-rotinas-esforco-e-pendencias.md) | 2026-10-23 | ✅ Aceito | Produto e domínio | Esforço em contagem + minutos estimados/reais, rotinas no painel pela categoria, data prevista e pendências calculadas no backend, grade de agenda fora da fase. |

| 005 | [FinOps: valor financeiro das decisões](ADR-005-finops-valor-das-decisoes.md) | 2026-10-23 | ✅ Aceito | Produto e domínio | Iniciativas como fonte única de saving, janela padrão de 6 meses até virar novo normal, faturas só acompanham, perfis de custo/hora com snapshot, ROI/payback e gráficos SVG locais. |

| 006 | [Despesas & Contratos: inventário, orçamento e conversão em iniciativa](ADR-006-despesas-contratos-e-conversao.md) | 2026-10-23 | ✅ Aceito | Produto e domínio | Inventário com auditoria, cancelar/renegociar criam iniciativa vinculada (reversível), orçamento mensal opcional com anual ÷ 12, ligação opcional despesa→fonte de custo e alertas de renovação 30/60 dias. |

## Mapa de Dependências

ADR-002 usa a estrutura de partida descrita em [ADR-001](ADR-001-base-minima-sem-dominio.md), sem alterar seu status.

ADR-003 depende de [ADR-001](ADR-001-base-minima-sem-dominio.md) e [ADR-002](ADR-002-perfis-dev-integrated-production.md), sem alterar o status do ADR-001.

ADR-004 depende de [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md).

ADR-005 depende de [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md).

ADR-006 depende de [ADR-005](ADR-005-finops-valor-das-decisoes.md) e [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md).

## Índice por Área

### Estrutura do template

- [ADR-001](ADR-001-base-minima-sem-dominio.md) — Base mínima sem domínio de demonstração

### Operação e desenvolvimento

- [ADR-002](ADR-002-perfis-dev-integrated-production.md) — Desenvolvimento isolado e perfis de execução

### Produto e domínio

- [ADR-003](ADR-003-porte-mvp-indicadores-em-fases.md) — Porte do MVP Indicadores de Engenharia em fases
- [ADR-004](ADR-004-rotinas-esforco-e-pendencias.md) — Rotinas: esforço medido e pendências
- [ADR-005](ADR-005-finops-valor-das-decisoes.md) — FinOps: valor financeiro das decisões
- [ADR-006](ADR-006-despesas-contratos-e-conversao.md) — Despesas & Contratos: inventário, orçamento e conversão em iniciativa

## Como Criar um Novo ADR

1. Leia a [convenção obrigatória](README.md).
2. Copie [TEMPLATE-ADR.md](TEMPLATE-ADR.md) para `docs/adrs/ADR-NNN-descricao-curta.md`.
3. Preencha o registro, incluindo status e origem real da decisão.
4. Atualize a tabela acima, o índice por área, as dependências aplicáveis e a data deste Master.
5. Confira que o ID da tabela corresponde ao título e ao nome do arquivo.

*Mantenha este índice junto com os ADRs na mesma alteração.*
