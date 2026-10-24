# Operações

Este é o guia canônico para escolher e executar cada perfil. O parâmetro `--profile` é obrigatório; `ENVIRONMENT` nunca escolhe o perfil. Selecione também um arquivo de ambiente explicitamente quando não usar `.env`.

| Perfil | Quando usar | Pré-requisitos | Comandos | Como validar | Como parar |
|---|---|---|---|---|---|
| [dev isolado](#dev-isolado) | Interface e trabalho local sem Authentik/Core/PostgreSQL | Python 3.12+ e dependências instaladas | `python -m src --profile dev --reload` | `python -m src check --profile dev`; confira `/health/ready` | Ctrl+C |
| [integrated](#integrated) | Integração com PostgreSQL, OIDC e Core reais | Banco/roles, Authentik e Core configurados | migrate → check → serve usando `--profile integrated` | `check`, depois login e contexto de tenant em staging/integrado | Ctrl+C; encerre serviços locais com `docker compose down` |
| [production](#production) | Release e operação da aplicação | Infraestrutura aprovisionada e arquivos privados runtime/migration | migrate com `.env.production.migration`; check/serve com `.env.production` | `check`, health probes e aceite em staging | Supervisor/orquestrador; drene tráfego antes de parar |

## Dev isolado

**Quando usar:** desenvolver interface e fluxos sem depender de serviços externos. Este perfil usa autenticação local fictícia, SQLite e só pode escutar no loopback.

**Pré-requisitos:** Python 3.12+, dependências do repositório e execução na raiz do projeto. Não precisa de `.env`, Docker, Authentik, Core ou PostgreSQL.

**Comandos:**

```bash
python -m src --profile dev --reload
```

Migre ou valide o SQLite sem iniciar servidor:

```bash
python -m src migrate --profile dev
python -m src check --profile dev
```

Acesse `http://127.0.0.1:8000`. A CLI ignora URLs de banco/Auth dos outros perfis e usa `.local/dev.sqlite3` e `.local/session.key`. As fixtures `editor-a`, `reader-a` e `editor-b` não têm senhas e não representam usuários reais. O perfil dev desliga o rate limit (`RATE_LIMIT_ENABLED=false`, exibido como `rate_limit=off` no `check`); integrated e production mantêm o limite.

**Validação:** `check` verifica banco e revisão de migração. Abra `/health/live` e `/health/ready`. SQLite e fixtures permitem teste funcional local, mas não validam RLS do PostgreSQL.

**Parar:** pressione Ctrl+C. O estado local fica em `.local/`; não compartilhe nem versiona essa pasta.

## Integrated

**Quando usar:** validar a integração com PostgreSQL, OIDC/Authentik e Core reais antes da promoção. O perfil não habilita fixtures locais nem executa migrações ao subir workers.

**Pré-requisitos:** `.env` ou outro arquivo com `DATABASE_URL` PostgreSQL, `AUTH_MODE=oidc`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`, `CORE_URL`, chave de sessão e URL pública/cookie compatíveis com o ambiente. Use roles PostgreSQL separadas para runtime e migração.

**Comandos:**

```bash
python -m src migrate --profile integrated
python -m src check --profile integrated
python -m src --profile integrated
```

Para usar um arquivo dedicado, acrescente `--env-file .env.integrated` aos três comandos. Um Compose local pode subir apenas o PostgreSQL e depois usar os mesmos comandos:

```bash
docker compose up -d postgres
python -m src migrate --profile integrated
python -m src check --profile integrated
python -m src --profile integrated
```

**Validação:** `check` confere conexão, revisão e OIDC discovery/JWKS. Em staging, faça login OIDC, selecione tenant autorizado e confira `/api/v1/context`; teste também revogação de membership. `check` não valida segredo do cliente nem autorização do Core por um fluxo de usuário.

**Parar:** Ctrl+C e, se iniciou dependências locais, `docker compose down`. Evite `docker compose down -v`, pois remove o volume do PostgreSQL.

## Production

**Quando usar:** executar uma versão liberada com Authentik/Core e PostgreSQL da plataforma. O perfil exige OIDC, HTTPS, cookies seguros e chave persistente de sessão. Consulte [deploy](deploy.md) para infraestrutura, segredos, publicação e rollback.

**Pré-requisitos:** dois arquivos privados, fora do Git e da imagem: `.env.production` para runtime, sem `MIGRATION_DATABASE_URL`; `.env.production.migration` para a tarefa de migração, com `MIGRATION_DATABASE_URL` de uma role owner diferente da role runtime e apontando ao mesmo banco. O [exemplo de produção](../.env.production.example) é a base do arquivo runtime.

**Comandos:**

```bash
python -m src migrate --profile production --env-file .env.production.migration
python -m src check --profile production --env-file .env.production
python -m src --profile production --env-file .env.production
```

Execute uma migração por release antes de iniciar réplicas. Check/serve recusam `MIGRATION_DATABASE_URL` no ambiente runtime. Variáveis exportadas no shell têm precedência sobre os arquivos; remova qualquer variável owner do ambiente runtime.

**Validação:** `check` confirma configuração, banco, revisão, descoberta e JWKS. Em staging, valide login, permissões e revogação Core usando a role não-owner. Monitore `/health/live`, `/health/ready` e logs de stdout.

**Parar:** pare ou substitua o processo pelo supervisor/orquestrador depois de drenar o tráfego. Não deixe o terminal como supervisor permanente.

## Testes automatizados

```bash
python scripts/validate.py
```

O validate executa, nesta ordem: paridade da documentação da CLI, `ruff check`, `ruff format --check`, `mypy` em `src/` e `pytest` com cobertura. A cobertura mínima (`fail_under` em `pyproject.toml`) foi medida na suíte unitária; os testes de CLI rodam em subprocesso e não entram na conta. Os mesmos ruff e mypy rodam nos hooks de `pre-commit install`; para conferir tudo sem commitar, use `pre-commit run --all-files`.

Antes de liberar uma versão, ou quando o CI acusar, audite as dependências travadas:

```bash
python -m pip_audit -r requirements.lock
```

O CI também roda essa auditoria e faz o scan da imagem Docker com Trivy, falhando em vulnerabilidades HIGH/CRITICAL que já têm correção. O Dependabot abre PRs semanais agrupados de pip, GitHub Actions e da imagem base. Em PRs de pip, rode o `pip-compile` do cabeçalho de `requirements.lock` e restaure os marcadores de Windows (uvloop e tzdata) antes de aceitar.

Os testes PostgreSQL exigem `TEST_MIGRATION_DATABASE_URL` e `TEST_DATABASE_URL` para um banco descartável com owner e runtime separados:

```bash
python scripts/validate.py --integration
```

Nunca aponte testes ou migrações experimentais para o banco de produção. Veja [testes](testing.md) e [diagnóstico](troubleshooting.md).

## Novo projeto

Depois de criar o repositório a partir do template, rode o bootstrap descrito no [README](../README.md#criar-e-integrar-uma-aplicação) e confira as pendências restantes:

```bash
python scripts/bootstrap.py --check
```

O check só lê arquivos e nunca imprime valores do `.env`. Sai com código 1 enquanto houver pendência: nome do template, `.env` ausente, `OIDC_CLIENT_ID`/`OIDC_CLIENT_SECRET` vazios ou seções `A definir` em `docs/project-context.md`.

## Atalhos

O `Makefile` só repete os comandos acima: `make install`, `make hooks`, `make dev`, `make validate`, `make integration`, `make audit` e `make bootstrap-check`. Use `make PYTHON=python3.12 ...` para escolher o interpretador. No Windows sem `make`, rode os comandos `python` diretamente.
