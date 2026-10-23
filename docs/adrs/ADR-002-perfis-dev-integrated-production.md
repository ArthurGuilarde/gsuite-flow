# ADR-002 — Desenvolvimento isolado e perfis de execução

**Data:** 2026-10-15  
**Status:** ✅ Aceito  
**Área:** Operação e desenvolvimento  
**Origem da decisão:** Solicitação de Guilarde para executar a aplicação com python -m src, usar SQLite em dev e PostgreSQL em produção, com testes isolados de autenticação.  
**Responsável pelo aceite:** Guilarde — autorização expressa da separação dev/produção na solicitação.  
**Depende de:** [ADR-001](ADR-001-base-minima-sem-dominio.md) — estrutura mínima de partida, ainda registrada Em discussão; este ADR não altera seu status.  
**Substitui:** Não se aplica  
**Substituído por:** Não se aplica

## Contexto

A execução exigia PostgreSQL e a infraestrutura externa mesmo para testar interface e domínio. O usuário solicitou operação autônoma com comandos documentados, SQLite em dev e PostgreSQL em produção.

## Decisão

Oferecer os perfis dev (SQLite local com migrações antes do servidor e fixtures de identidade/grants), integrated (PostgreSQL e OIDC/Core reais) e production (PostgreSQL/OIDC, HTTPS e configuração segura obrigatórios).

O adaptador local mantém os contratos de sessão e autorização, sem implementar um servidor OIDC falso ou emitir tokens próprios. Ele é restrito a development/loopback e não pode ser configurado em produção. A CLI local usa URL e chave separadas das de produção.

Oferecer serve, migrate e check pelo módulo src com `--profile` obrigatório e explícito. `ENVIRONMENT` configura a validação, mas nunca seleciona o perfil. Somente dev migra o SQLite automaticamente antes de iniciar o servidor; perfis externos mantêm a etapa de migração separada. Production usa credencial owner separada apenas na tarefa de migração e executa runtime com role não-owner.

## Alternativas Consideradas

| Alternativa | Motivo de descarte |
|---|---|
| Exigir a suíte completa em todo teste | Impede desenvolvimento independente solicitado |
| Usar fixtures locais em produção | Viola identidade e autorização centrais |
| Criar um IdP falso completo | Adiciona protocolo e manutenção sem validar interoperabilidade real com Authentik |
| Tratar SQLite como prova de isolamento RLS | SQLite não implementa essas políticas PostgreSQL |

## Consequências

### Benefícios

Execução local rápida, comandos reproduzíveis e testes de UI/domínio sem serviços externos.

### Custos e limitações

Dois dialetos de banco precisam ser considerados nas migrações. SQLite permite testes funcionais, mas PostgreSQL continua obrigatório para RLS, permissões, tipos específicos e concorrência. Check externo verifica discovery/JWKS, não valida um fluxo de usuário nem grants do Core.

### Riscos

Exposição do adaptador fictício é mitigada por validação de configuração, restrição de peer/Host ao loopback e ausência das rotas no modo OIDC. O perfil dev ignora conexão/key de produção em favor de arquivos locais próprios.

## Validação

Testes de comandos, login HTTP local, CSRF, sessão e grants; casos negativos de configuração de produção; filtros/guardas ORM em SQLite; suíte RLS PostgreSQL e build Docker. Evidências de execução ficam no PR/CI.

## Referências

- [Operações](../operations.md)
- [Segurança](../security.md)
- [Deploy](../deploy.md)

## Histórico

| Data | Estado | Registro |
|---|---|---|
| 2026-10-15 | ✅ Aceito | Separação dev SQLite / produção PostgreSQL autorizada pelo usuário; implementação com adaptador local restrito |
