# Contexto do projeto

**Projeto:** Guilarde Suite  
**APP_ID:** suite-example

Este arquivo descreve o produto a ser construído. Bootstrap personaliza os metadados; o responsável pelo projeto preenche as regras abaixo. LLMs devem tratar campos pendentes como desconhecidos, sem inventar requisitos.

## Objetivo e público

A definir: problema resolvido, usuários e resultado esperado.

## Escopo

A definir: funcionalidades incluídas e explicitamente excluídas da primeira entrega.

## Tenant e acesso

Um tenant representa um espaço compartilhado. A definir: o significado desse espaço neste produto, quem participa e como ocorre o ingresso. Não use a aplicação ou o usuário como tenant automaticamente.

Em produção/integrated, identidade é externa (Authentik), e memberships/entitlements são centrais (Core). Dev isolado usa identidades/grants fictícios somente para desenvolvimento. Permissões básicas: access/read/write; o Core é a autoridade. A definir: regras específicas do produto, se houver.

## Domínio e regras

A definir: termos do negócio, entidades, invariantes, cálculos, validações e exemplos aprovados. Não deduza regras de domínio a partir das fixtures de teste.

## Jornadas e critérios de aceite

A definir: principais jornadas, entradas, resultados esperados e falhas relevantes. Para cada funcionalidade, explicite critérios verificáveis na solicitação/issue correspondente.

## Restrições e integrações

Base técnica: FastAPI, SQLAlchemy 2, Alembic e frontend vanilla; SQLite para dev isolado e PostgreSQL para integrated/produção. A definir: integrações de domínio, restrições operacionais e de dados. Nunca inclua credenciais ou dados pessoais reais neste documento.

## Pendências

Os campos acima precisam ser definidos para implementar o domínio. Registre dúvidas bloqueantes na tarefa; prossiga apenas nas partes independentes já autorizadas. Decisões arquiteturais ficam no Master ADR, sem duplicar seu histórico aqui.
