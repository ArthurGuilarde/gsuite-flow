# GFlow

Indicadores de engenharia da suíte Guilarde: capacidade BUILD ≥ 70% / RUN ≤ 30%, rotinas, Planner pessoal, FinOps e Despesas & Contratos, portados do MVP "Indicadores de Engenharia" em fases ([ADR-003](docs/adrs/ADR-003-porte-mvp-indicadores-em-fases.md)). Stack: FastAPI, SQLAlchemy 2, Alembic e frontend HTML/CSS/JS, com integração OIDC/Core, sessões BFF, autorização por tenant e testes de isolamento PostgreSQL.

**Módulos:** Capacidade (Fase 1: grupos, semanas, lançamentos e dashboard) Rotinas (Fase 2: rotinas recorrentes, esforço estimado/real e pendências, [ADR-004](docs/adrs/ADR-004-rotinas-esforco-e-pendencias.md)) FinOps (Fase 3: iniciativas de melhoria/automação/otimização como fonte de saving com janela de 6 meses, perfis de custo/hora, ROI e faturas de acompanhamento, [ADR-005](docs/adrs/ADR-005-finops-valor-das-decisoes.md)) e Despesas & Contratos (Fase 4: inventário com auditoria, cancelar/renegociar como iniciativas vinculadas, orçamento mensal e alertas de renovação, [ADR-006](docs/adrs/ADR-006-despesas-contratos-e-conversao.md)) e o Planner pessoal "Meu Dia" (Fase 5: foco, prioridades, tarefas e notas por pessoa, rotinas pendentes e renovações urgentes, e pendências que migram entre dias, [ADR-007](docs/adrs/ADR-007-planner-pessoal-meu-dia.md)) estão implementados. Aviso: o grupo padrão "Rotinas (N0)" continua existindo para lançamentos manuais, mas as rotinas cadastradas não somam mais nele; agora somam pela própria categoria no painel. Um tenant é um cliente (PF ou PJ) que contrata o sistema.

## Escolha um cenário

| Cenário | Quando usar | Pré-requisitos | Comandos principais | Guia completo |
|---|---|---|---|---|
| `dev` | Interface e trabalho local sem serviços externos e sem rate limit | Python 3.12+ e dependências instaladas | `python -m src --profile dev --reload`<br>`python -m src seed --profile dev` (dados fictícios de demonstração) | [Operações — dev](docs/operations.md#dev-isolado) |
| `integrated` | Integrar com PostgreSQL, Authentik e Core reais | PostgreSQL, OIDC/Core configurados e runtime/migration roles | `python -m src migrate --profile integrated`<br>`python -m src check --profile integrated`<br>`python -m src --profile integrated` | [Operações — integrated](docs/operations.md#integrated) |
| `production` | Operar release com configurações e segredos de produção | PostgreSQL, Authentik/Core e arquivos runtime/migration separados | `python -m src migrate --profile production --env-file .env.production.migration`<br>`python -m src check --profile production --env-file .env.production`<br>`python -m src --profile production --env-file .env.production` | [Deploy](docs/deploy.md) e [operações](docs/operations.md#production) |

O perfil é sempre informado por `--profile`; `ENVIRONMENT` não seleciona perfil. O comando recusa iniciar sem perfil. Pare o servidor com Ctrl+C. Consulte [diagnóstico](docs/troubleshooting.md) quando um comando falhar.

## Instalar dependências

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install -e '.[dev]'
```

No Windows PowerShell, use `py -3.12 -m venv .venv`, ative com `.\.venv\Scripts\Activate.ps1` e instale o extra com `python -m pip install -e ".[dev]"`.

Instale os hooks uma vez por clone com `pre-commit install`; eles rodam ruff, mypy e checagens de arquivo a cada commit. Com `make` disponível, `make help` lista atalhos para os mesmos comandos (`make dev`, `make validate`, `make audit`); no Windows, use os comandos `python` diretamente.

## Criar e integrar uma aplicação

Opcionalmente personalize os metadados do projeto e gere `.env`:

```bash
python scripts/bootstrap.py --app-id minha-app --name "Minha aplicação" --issuer https://auth.guilarde.com/application/o/minha-app/
```

O bootstrap recusa sobrescrever `.env`. Ele renomeia o projeto em `README.md`, `pyproject.toml` (versão `0.1.0`), `suite-app.json`, `src/frontend/index.html`, `docs/project-context.md` e no Master ADR, e imprime os próximos passos. Ajuste as configurações OIDC, Core e PostgreSQL e registre `suite-app.json` segundo o [contrato com o Core](docs/core-contract.md).

Para ver o que ainda é do template (nome, `.env`, credenciais OIDC vazias, seções `A definir` do contexto) sem alterar nada:

```bash
python scripts/bootstrap.py --check
```

## Documentação

Comece pelo [índice](docs/README.md). Os guias principais são [operações](docs/operations.md), [desenvolvimento](docs/development.md), [deploy](docs/deploy.md), [arquitetura](docs/architecture.md), [segurança](docs/security.md), [testes](docs/testing.md) e [contrato com o Core](docs/core-contract.md).

## Estrutura

| Caminho | Responsabilidade |
|---|---|
| `docs/` | Contexto, arquitetura, integração, segurança e operação |
| `src/backend/api/` | Autenticação, contexto de tenant e rotas da aplicação |
| `src/backend/core/`, `integrations/`, `tenancy/` | Configuração, integração e isolamento |
| `src/backend/models/`, `schemas/`, `services/`, `repositories/` | Domínios Capacidade (Fase 1), Rotinas (Fase 2), FinOps (Fase 3) e Despesas & Contratos (Fase 4), Planner pessoal (Fase 5) e pontos de extensão |
| `src/backend/migrations/` | Migrações, executadas como etapa separada em perfis externos |
| `src/frontend/` | Login, seleção de tenant e cliente BFF |
| `tests/` | Contratos, segurança e integração PostgreSQL |
| `scripts/`, `deploy/` | Bootstrap, validação e provisionamento |
| `Makefile`, `.pre-commit-config.yaml` | Atalhos dos comandos documentados e hooks locais |
| `AGENTS.md`, `CLAUDE.md` | Regras para agentes de IA; `CLAUDE.md` só importa `AGENTS.md` |
