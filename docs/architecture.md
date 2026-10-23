# Arquitetura da aplicação

O template contém uma aplicação e um BFF. Produção/integrated usam PostgreSQL; dev isolado usa SQLite. Authentik fornece identidade; Core fornece memberships, acesso à aplicação e entitlements. Nenhum serviço consulta diretamente o banco de outro.

Tenant é um espaço compartilhado entre membros. APP_ID identifica a aplicação. O subject OIDC identifica o usuário e é tratado como string opaca.

Fluxo de domínio: cookie opaco → sessão criptografada no PostgreSQL → access token validado → autorização do Core para subject/app/tenant/permissão → TenantContext → transação com SET LOCAL → repositório com filtro de tenant + RLS.

A base não inclui um domínio de negócio. A única tabela criada pela migração inicial é browser_sessions; alembic_version controla as revisões. Contexto e transações tenant-aware são pontos de extensão. O exemplo executável de RLS existe exclusivamente nos testes, com metadata separada do Alembic da aplicação.

## Extensão

Rotas → schemas → serviços → repositórios → modelos. As dependências controlam transações; repositórios/serviços não executam commit. Derive tenant_id e created_by do contexto validado. created_by é auditoria, não uma restrição de propriedade individual.

Cada tabela compartilhada exige tenant_id, índices e FORCE/ENABLE RLS com USING e WITH CHECK. Relações entre registros usam `(tenant_id,parent_id)` para impedir vínculos entre tenants.

A role runtime guilarde_app não é proprietária das tabelas, superuser ou BYPASSRLS. Uma role separada executa migrações. RLS protege consultas acidentalmente sem filtro; não substitui autorização central nem protege contra credenciais da aplicação comprometidas com SQL arbitrário.

Veja o [guia de desenvolvimento](development.md) para os caminhos e a referência de implementação.


## Desenvolvimento isolado

O perfil dev usa um adaptador de identidade/grants com fixtures locais, sem criar um provedor OIDC falso. A sessão opaca, CSRF e verificação de tenant continuam no mesmo fluxo da aplicação. Configuração e middleware limitam esse adaptador ao ambiente development e ao loopback; endpoints locais não são montados em OIDC/produção.

SQLite não oferece RLS. Transações tenant em dev filtram SELECT ORM e validam escritas de instância via SQLAlchemy; SQL bruto e operações bulk são recusados nesse escopo. Isso permite testes funcionais e não substitui a garantia de RLS, roles e concorrência testada no PostgreSQL. Login OIDC real só é validado pelos testes específicos e em ambiente integrado.
