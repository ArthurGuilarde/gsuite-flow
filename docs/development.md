# Desenvolvimento

Este guia cobre somente contribuição e execução do ciclo local isolado. Para instalação, comandos, validação e encerramento de todos os perfis, consulte o [guia de operações](operations.md). Para implantação, consulte [deploy](deploy.md).

## Antes de implementar

1. Leia AGENTS.md na raiz, [o contexto](project-context.md), [o Master ADR](adrs/MASTER-ADR.md) e os documentos relevantes à tarefa.
2. Identifique o comportamento solicitado, critérios de aceite e restrições. Campos de contexto em aberto não são autorização para inventar um produto.
3. Consulte o código e o contrato `/openapi.json`. Se a mudança for arquitetural, siga a [convenção de ADRs](adrs/README.md).

## Adicionar um domínio

| Camada | Local | Regra |
|---|---|---|
| Rotas | `src/backend/api/v1/` | Registrar o router em `api/v1/router.py` |
| Schemas | `src/backend/schemas/` | Validar entrada, rejeitar campos extras e definir respostas |
| Serviços | `src/backend/services/` | Regras do domínio, sem controlar a transação |
| Repositórios | `src/backend/repositories/` | Consultas com tenant explícito, sem commit |
| Modelos | `src/backend/models/` | Importar o modelo em models/__init__.py para o Alembic |
| Migrações | `src/backend/migrations/versions/` | Revisar SQL, privilégios e políticas RLS |
| Frontend | `src/frontend/js/` | Usar api.js e o contexto selecionado; inserir texto via textContent |

Use `TenantRecord` como base de registros compartilhados. Uma rota de leitura usa `Depends(read_db, scope="function")` e `Depends(read_context)`; uma escrita usa write_db/write_context. As dependências autorizam no Core e delimitam uma única transação com SET LOCAL. O repositório filtra pelo tenant; o PostgreSQL também o restringe por RLS.

Cada tabela de domínio tem `tenant_id` e índices. Em PostgreSQL, a migração habilita ENABLE/FORCE ROW LEVEL SECURITY e cria política USING/WITH CHECK; use condições por dialeto para SQL RLS. Use `(tenant_id,id)` e chaves estrangeiras compostas em relações entre registros. Conceda DML à role runtime sem transferir ownership. Nunca receba `tenant_id` de um schema de criação como autoridade.

A referência executável está em `tests/support/tenant_example.py`, com política RLS em `tests/conftest.py` e casos negativos em `tests/test_postgres.py`. É infraestrutura de teste: não importe `tests` a partir de `src`, não copie o domínio de teste como funcionalidade e não inclua sua tabela nas migrações reais.

## Contratos e interface

`GET /api/v1/context` valida o tenant selecionado e retorna permissões e features; não cria dados de domínio. O frontend limpa o contexto ao trocar de espaço. A UI pode usar permissões para apresentar ações; o backend sempre as verifica novamente.

Mantenha o contrato FastAPI/OpenAPI atualizado pelos schemas e rotas. Registre alterações incompatíveis de integração em [core-contract.md](core-contract.md) e ADR quando aplicável. Não gere contratos duplicados manualmente.

## Concluir uma alteração

- Execute `python scripts/validate.py` (inclui mypy e cobertura mínima); para identidade, permissões, banco ou migrações, execute também `--integration` em PostgreSQL descartável.
- Cubra o comportamento alterado e falhas relevantes, especialmente acesso entre tenants.
- Atualize os documentos afetados na mesma alteração do código. Mudanças em CLI, variáveis de ambiente, scripts ou deploy exigem sincronização de `README.md`, `docs/operations.md`, `docs/deploy.md` se aplicável, `docs/troubleshooting.md`, `docs/README.md` e `AGENTS.md`.
- Não introduza abstrações, plugins, novas dependências ou documentos sem necessidade concreta.

## Uso do perfil dev

Use somente `python -m src --profile dev` no ciclo local isolado. Ele usa SQLite e fixtures sem serviços externos, em loopback. Transações tenant usam filtros ORM automáticos; SQL textual e bulk DML são recusados. Use PostgreSQL integrated para consultas específicas de dialeto e validação de RLS. Não use o perfil dev para simular uma implantação.

Migrações e tipos devem declarar diferenças de dialeto explicitamente. Tipos exclusivos de PostgreSQL, políticas RLS, extensões e comportamento concorrente precisam de testes PostgreSQL. Não reescreva migrações já aplicadas em aplicações derivadas; a adaptação da baseline preserva o mesmo schema PostgreSQL.

A revisão `0001_template` é ponto de partida para bancos novos. Aplicações já criadas mantêm o histórico de migrações e recebem alterações próprias. PWA, temas, ícones e módulos de produto são adicionados apenas quando exigidos.
