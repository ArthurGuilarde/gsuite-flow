# Documentação

Leia apenas o que a tarefa exige. Evite duplicar regras: cada documento abaixo é responsável por um assunto.

| Documento | Quando consultar |
|---|---|
| [Contexto do projeto](project-context.md) | Antes de definir funcionalidades e regras de negócio |
| [Desenvolvimento](development.md) | Para implementar ou alterar funcionalidades |
| [Arquitetura](architecture.md) | Ao alterar camadas, dados ou isolamento |
| [Contrato com o Core](core-contract.md) | Ao integrar identidade, tenants e permissões |
| [Segurança](security.md) | Ao alterar autenticação, autorização, sessões ou RLS |
| [Operações](operations.md) | Guia canônico: quando usar, pré-requisitos, comandos, validação e encerramento de cada perfil |
| [Diagnóstico](troubleshooting.md) | Ao encontrar falhas de CLI, banco, login, rede ou Compose |
| [Deploy](deploy.md) | Ao aprovisionar infraestrutura, gerir segredos, publicar e reverter |
| [Testes](testing.md) | Para escolher e executar validações |
| [ADR-003 — porte em fases](adrs/ADR-003-porte-mvp-indicadores-em-fases.md) | Para entender o escopo por fases do porte do MVP |
| [ADR-004 — rotinas: esforço e pendências](adrs/ADR-004-rotinas-esforco-e-pendencias.md) | Para entender esforço estimado/real, pendências e o painel de Rotinas |
| [ADR-005 — FinOps: valor das decisões](adrs/ADR-005-finops-valor-das-decisoes.md) | Para entender iniciativas, janela de saving, perfis de custo/hora e ROI do módulo FinOps |
| [ADR-006 — Despesas & Contratos](adrs/ADR-006-despesas-contratos-e-conversao.md) | Para entender inventário de despesas, orçamento mensal e conversão de cancelamento/renegociação em iniciativa FinOps |
| [ADR-007 — Planner pessoal](adrs/ADR-007-planner-pessoal-meu-dia.md) | Para entender o Meu Dia por pessoa, RLS por sujeito, pendências que migram e o escopo integrado |
| [ADR-008 — Demandas](adrs/ADR-008-demandas-triagem-em-grupos.md) | Para entender demandas nos Grupos, a Triagem como grupo de sistema, a contagem no painel BUILD × RUN e a exceção do solicitante com read |
| [ADR-009 — Demandas: histórico e comentários](adrs/ADR-009-demandas-historico-e-comentarios.md) | Para entender o detalhe da demanda, a linha do tempo, os comentários imutáveis e quem pode comentar |
| [Master ADR](adrs/MASTER-ADR.md) | Antes de alterar decisões arquiteturais |
| [Convenção de ADRs](adrs/README.md) | Para registrar decisões |
| [Template de ADR](adrs/TEMPLATE-ADR.md) | Ao criar um ADR |

Agentes de IA começam por `AGENTS.md` na raiz; `CLAUDE.md` só o importa. A documentação geral fica em `docs/` e todos os ADRs em `docs/adrs/`. Contratos de API da própria aplicação são gerados em `/openapi.json`; não mantenha uma cópia manual que possa divergir do código. O contrato de integração externa continua em core-contract.md. Para desenvolvimento local (SQLite, identidades fictícias, rate limit desligado e o seed de demonstração `python -m src seed --profile dev`), consulte a seção dev de operations.md; para produção, use deploy.md.

Atualize os documentos afetados na mesma alteração do código. Não adicione relatórios de execução, transcrições de conversas ou guias de outros sistemas ao template; evidências de execução ficam no PR/CI.
