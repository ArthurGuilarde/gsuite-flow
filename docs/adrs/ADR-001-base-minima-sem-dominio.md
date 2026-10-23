# ADR-001 — Base mínima sem domínio de demonstração

**Data:** 2026-10-15  
**Status:** 🔄 Em discussão  
**Área:** Estrutura do template  
**Origem da decisão:** Solicitação de Guilarde para limpar o template e melhorar o contexto fornecido às LLMs; proposta detalhada neste PR.  
**Responsável pelo aceite:** Não informado  
**Depende de:** Não se aplica  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

## Contexto

O template continha um CRUD de notas, arquivos históricos, conteúdo de outro produto, estilos e utilitários não utilizados. Esses elementos aumentavam o contexto e podiam induzir a reprodução de um domínio incorreto. Remover a demonstração exige preservar os testes de isolamento e distinguir a nova base das migrações já usadas em aplicações anteriores.

## Decisão

Proposta: manter no runtime apenas infraestrutura, autenticação e contexto de tenant. A referência executável de domínio/RLS passa a existir somente nos testes, com metadata separada. O domínio de cada produto será definido em project-context.md.

Para bancos novos, usar a revisão 0001_template contendo apenas sessões. Aplicações existentes preservam seu histórico e exigem plano próprio de atualização. Não executar remoção de tabelas, stamp ou migrações em bancos existentes durante esta limpeza.

A proposta permanece Em discussão até o aceite do PR pelo responsável. A solicitação autoriza a limpeza; o detalhamento da nova baseline fica explícito para revisão.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Manter notas no runtime | Todo produto herdaria um domínio que não solicitou |
| Remover os testes junto com a demonstração | Perderia a evidência executável de isolamento |
| Reutilizar a revisão antiga com conteúdo diferente | Ocultaria a diferença entre bancos já migrados e a nova base |
| Adicionar uma migração que apague notas | Poderia apagar dados de aplicações derivadas sem um plano específico |

## Consequências

### Benefícios

Menos arquivos e conteúdo para interpretar, domínio inicial vazio e isolamento ainda testado.

### Custos e limitações

Bancos anteriores não são atualizados automaticamente. LLMs precisam ler o contexto do produto e adicionar modelos, rotas e migrações correspondentes.

### Riscos

Uma aplicação existente pode tentar usar a nova baseline; a revisão distinta faz o Alembic recusar o histórico desconhecido. A documentação proíbe contornar esse erro com stamp ou exclusão de dados.

## Validação

Exigir metadados de produção sem tabelas de demonstração, OpenAPI sem rotas de notas e testes de autorização/RLS no PostgreSQL. Resultados executados e pendências são publicados no PR/CI.

## Referências

- [Arquitetura](../architecture.md)
- [Desenvolvimento](../development.md)
- [Deploy](../deploy.md)
- tests/support/tenant_example.py e tests/test_postgres.py

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-15 | 🔄 Em discussão | Proposta implementada em branch para revisão, sem alteração de bancos existentes |
