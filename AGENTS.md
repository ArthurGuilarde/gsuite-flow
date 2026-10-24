# Regras da aplicação Guilarde Suite
Leia primeiro docs/project-context.md e docs/adrs/MASTER-ADR.md. Use docs/development.md para implementação e docs/core-contract.md para integração. Carregue apenas os arquivos relevantes.

## Invariantes
- Em integrated/production, a identidade pertence ao Authentik e memberships/entitlements pertencem ao Core.
- O dev isolado suporta explicitamente SQLite e identidades locais fictícias pelo adaptador local; nunca o habilite em produção. O perfil dev desliga o rate limit; integrated/production o mantêm.
- Nunca crie senhas locais reais, admin global, billing, impersonation nem acesso direto ao banco do Core. As fixtures de dev local não têm senhas.
- Um tenant é um espaço de trabalho compartilhado, nunca uma aplicação ou um usuário.
- Exija access e read/write antes de abrir uma transação de tenant. Negue em caso de falha do Core.
- Toda tabela de tenant tem tenant_id; no PostgreSQL exige ENABLE/FORCE RLS com USING e WITH CHECK. No SQLite, guardrails do ORM servem apenas a testes funcionais locais.
- A role de runtime não é dona das tabelas, superuser nem BYPASSRLS. Mantenha SET LOCAL dentro de uma única transação.
- Repositórios e serviços não fazem commit. Chaves estrangeiras compostas com tenant impedem relações entre tenants.
- O navegador recebe apenas um cookie opaco HttpOnly. Nunca guarde tokens no storage do navegador nem faça cache de respostas privadas.
- Em integrated/production, migrações rodam em etapa separada; nunca crie usuários nem migre na inicialização dos workers. A CLI dev aplica as migrações SQLite uma vez antes de iniciar o servidor.

## Implementação
- Campos pendentes em docs/project-context.md são desconhecidos; não invente regras de negócio.
- src/ não importa tests/. A referência de domínio/RLS em tests/support é exclusiva dos testes.
- A aplicação inicial não tem módulos de negócio; crie apenas o domínio autorizado.
- Contratos internos vêm do OpenAPI gerado; não mantenha cópias manuais.

## Documentação e ADRs
- A documentação geral fica em docs/. Comece por docs/README.md.
- Antes de alterar arquitetura, leia docs/adrs/MASTER-ADR.md e os ADRs relevantes.
- Siga obrigatoriamente docs/adrs/README.md e docs/adrs/TEMPLATE-ADR.md.
- Grave todos os ADRs em docs/adrs/ADR-NNN-descricao-curta.md.
- Use o próximo número disponível; o ID do arquivo, título e Master ADR deve ser o mesmo.
- Não invente decisões históricas, aprovações, datas, links ou IDs de conversas.
- Propostas sem aprovação ficam Em discussão; registre como Aceito apenas decisões explicitamente autorizadas.
- Atualize o Master ADR, seus índices e as referências entre ADRs na mesma alteração.
- Não reescreva decisões aceitas para substituir seu sentido; crie outro ADR e vincule a substituição.
- Mudanças rotineiras sem impacto arquitetural não precisam de ADR.
- Não há configuração de agentes, modelos ou roteamento neste template. `CLAUDE.md` apenas importa este arquivo para o Claude Code; mantenha as regras somente aqui.

## Validação
python scripts/validate.py (ruff, mypy, testes unitários e cobertura mínima)
Para autenticação, permissões, migrações ou banco: python scripts/validate.py --integration
A integração exige TEST_MIGRATION_DATABASE_URL e TEST_DATABASE_URL apontando para um PostgreSQL descartável.
Nunca teste migrações destrutivas contra produção.
Dependências: python -m pip_audit -r requirements.lock. Ao regenerar requirements.lock com pip-compile, preserve os marcadores de Windows (uvloop e tzdata).
Depois de clonar, rode pre-commit install. Um projeto novo começa com scripts/bootstrap.py; python scripts/bootstrap.py --check lista o que ainda é do template.

## Documentação operacional
- Toda alteração em CLI, variáveis de ambiente, scripts de execução ou arquivos de deploy atualiza na mesma mudança `README.md`, `docs/operations.md`, `docs/troubleshooting.md`, `docs/README.md` e este arquivo; atualize também `docs/deploy.md` quando a configuração ou operação de deploy mudar.
- Mantenha os comandos validados pela checagem automática de paridade da documentação e pelo menos um teste comportamental do perfil afetado.
- Não infira production de `ENVIRONMENT`: todos os comandos da CLI exigem `--profile` explícito. A migração production recebe credencial owner em arquivo separado; runtime nunca recebe essa credencial.
- O Dockerfile e o Compose iniciam pela CLI (`python -m src serve --profile ...`), nunca por Uvicorn direto, para manter as travas de perfil.
- O `Makefile` contém apenas atalhos para os comandos documentados; não coloque lógica nele.
