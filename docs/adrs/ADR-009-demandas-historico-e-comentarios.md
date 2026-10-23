# ADR-009 — Demandas: detalhe, histórico e comentários

**Data:** 2026-10-23  
**Status:** ✅ Aceito  
**Área:** Produto e domínio  
**Origem da decisão:** Decisões explicitamente autorizadas pelo usuário na sessão de implementação da extensão de Demandas (detalhe, histórico e comentários). Sem links ou IDs de conversa informados.  
**Responsável pelo aceite:** Usuário/responsável pelo projeto — autorização expressa nas respostas da sessão.  
**Depende de:** [ADR-008](ADR-008-demandas-triagem-em-grupos.md)  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

---

## Contexto

O [ADR-008](ADR-008-demandas-triagem-em-grupos.md) criou as Demandas, o ciclo ABERTA/CONCLUIDA/CANCELADA e a exceção em que o solicitante só com read abre e vê as próprias demandas. Ele registra, como "A definir", anexos e comentários. O solicitante e a equipe precisam acompanhar o que aconteceu com cada demanda e conversar sobre ela, sem sair do módulo. O ADR-008 guarda apenas os últimos campos de classificação, conclusão e cancelamento; reabrir os limpa, então o percurso completo se perde.

Restrições herdadas: `tenant_id` em todas as tabelas, chaves estrangeiras compostas com tenant, RLS no PostgreSQL, guarda SQLite, repositórios e serviços sem commit e contrato vindo do OpenAPI gerado.

## Decisão

Este ADR estende o ADR-008 sem alterar suas decisões. Ele apenas amplia a exceção de leitura do item 5: o solicitante só com read também pode comentar nas próprias demandas.

1. **Detalhe, linha do tempo e comentários.** Cada demanda tem tela de detalhe com a linha do tempo (aberta, classificada, concluída, reaberta, cancelada) e uma conversa de comentários entre solicitante e equipe. Não há edição de título nem de descrição.
2. **Quem comenta e quem lê.** O solicitante comenta nas próprias demandas, mesmo só com read (amplia a exceção do ADR-008). A equipe com write comenta em qualquer demanda do tenant. Ler o histórico segue a visibilidade da demanda: sem write e não sendo sua, responde 404. Comentar em demanda de outra pessoa, sem write, também responde 404.
3. **Comentários imutáveis.** Não há editar nem apagar. São aceitos em demanda ABERTA ou CONCLUIDA; em CANCELADA a demanda é só leitura e comentar responde 409. O texto tem de 1 a 5000 caracteres, após trim.
4. **Modelo.** Migração `0008_demandas_historico` (`down_revision` `0007_demandas`) cria `demanda_historico`: `id` UUID, `tenant_id`, `created_by`, `created_at`, `demanda_id` (obrigatório), `tipo` (CHECK ABERTURA, CLASSIFICACAO, CONCLUSAO, REABERTURA, CANCELAMENTO, COMENTARIO), `autor_sub`, `texto` (obrigatório quando o tipo é COMENTARIO, por CHECK) e `grupo_nome`. `grupo_nome` é um snapshot do nome do grupo de destino na CLASSIFICACAO, sem chave estrangeira, para não travar a exclusão de grupos. Chave estrangeira composta `(tenant_id, demanda_id)` para `demandas(tenant_id, id)` com `ON DELETE CASCADE`, UNIQUE `(tenant_id, id)` e índices por `(tenant_id)` e `(tenant_id, demanda_id, created_at)`. No PostgreSQL há ENABLE/FORCE RLS com a policy padrão de tenant (USING e WITH CHECK) e GRANT a `guilarde_app`. Não há policy por sujeito: a visibilidade é do serviço, como no ADR-008.
5. **Eventos de estado.** Abrir, classificar, concluir, reabrir e cancelar gravam o evento correspondente na mesma transação da mudança, com o autor vindo de `ctx.sub`. A migração faz backfill das demandas existentes: ABERTURA (autor `solicitante_sub`, data de criação) e, quando houver, CLASSIFICACAO, CONCLUSAO e CANCELAMENTO, cada um com o autor e o timestamp já gravados. Reaberturas anteriores à migração não são recuperáveis.
6. **Contrato.** Em `/api/v1/demandas`: `GET /{id}/historico` (read) lista os eventos em ordem cronológica, e `POST /{id}/comentarios` (read) cria um comentário e responde 201 com o evento. O contrato detalhado vem do OpenAPI gerado, sem cópia manual. As rotas do ADR-008 permanecem inalteradas.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Apenas tela de detalhe, sem comentários | O usuário escolheu incluir a conversa entre solicitante e equipe |
| Permitir ao solicitante editar título e descrição | O usuário escolheu não permitir edição; o pedido original fica estável |
| Só a equipe comenta | O usuário escolheu que o solicitante também comente nas próprias demandas, mesmo só com read |
| Autor editar ou apagar o próprio comentário | O usuário escolheu comentários imutáveis, preservando o histórico |

## Consequências

### Benefícios

O percurso completo de cada demanda fica registrado, inclusive reaberturas, e solicitante e equipe conversam no mesmo lugar. O snapshot do nome do grupo preserva o histórico mesmo se o grupo for renomeado ou excluído.

### Custos e limitações

A exceção do solicitante com read passa a cobrir também escrita de comentários, uma regra a mais para manter e testar. Toda transição de estado paga uma inserção de evento. O histórico anterior à migração se resume aos campos que existiam. Fora do escopo (A definir): notificações de novos comentários, anexos e menções.

### Riscos

Vazamento entre solicitantes, já que a RLS é só por tenant: mitigado por testes de API que exigem 404 para histórico e comentário em demanda de outro. Divergência entre o estado e o histórico: mitigada pela gravação do evento na mesma transação. Divergência entre guardrails do SQLite e RLS: mitigada por testes de integração PostgreSQL.

## Validação

Critérios: testes de API do histórico e dos comentários (solicitante só com read comenta e lê o histórico das próprias; 404 para demanda de outro; equipe com write comenta em qualquer demanda; comentário em CANCELADA 409; texto vazio ou acima de 5000 caracteres recusado; eventos gravados em abrir, classificar, concluir, reabrir e cancelar, com `grupo_nome` na classificação; ordem cronológica); teste da migração `0008_demandas_historico` com backfill; testes de integração PostgreSQL (RLS ENABLE/FORCE em `demanda_historico`, tenant divergente negado, FK composta para `demandas` entre tenants bloqueada). Execução: registrada no PR/CI; nenhuma evidência é anexada a este ADR.

## Referências

- [Contexto do projeto](../project-context.md)
- [Arquitetura](../architecture.md)
- [ADR-008](ADR-008-demandas-triagem-em-grupos.md)
- [Master ADR](MASTER-ADR.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-23 | ✅ Aceito | Registro de decisões explicitamente autorizadas pelo usuário na sessão da extensão de Demandas |
