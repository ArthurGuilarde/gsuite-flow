# Security behavior
- Browser receives opaque HttpOnly, SameSite=Lax cookie, Secure in production; tokens, PKCE and OAuth state stay encrypted server-side. Login rotates the session identifier.
- Authlib handles state, nonce and PKCE; access JWT accepts only RS256, fixed issuer/JWKS and app-specific audience. Fail closed for missing/invalid claims and key fetch failures.
- Writes and logout require session-bound CSRF token plus exact Origin. APIs and auth responses use no-store; the template has no service worker or offline cache. Frontend inserts user text with textContent.
- Tenant IDs from headers are never trusted without Core grant bound to subject, app and tenant.
- SELECT, INSERT, UPDATE and DELETE are constrained by RLS, including WITH CHECK; context is transaction-local and pooled connections cannot keep it after transaction end.
- Worker startup rejects superuser/BYPASSRLS/table-owner runtime roles. Owner connection is restricted to migration jobs.
- Logs use path without query string. Do not log access tokens, cookies, authorization decisions with personal data, or OIDC callback query parameters.

## Operational requirements
Use TLS and a persistent Fernet key from secret management. Changing that key invalidates stored sessions. BFF has no refresh token flow; token expiry requires a new OIDC login. Local logout deletes the app session, not the global IdP SSO session.
The current in-memory rate limiter is per process; configure shared limits on the platform proxy for multiple replicas. App does not trust arbitrary X-Forwarded-For. Uvicorn disables access logs to avoid OAuth code leakage and disables forwarded headers by default. If needed, configure only explicitly trusted proxy addresses.
Sessions expire absolutely and are not extended by reads. Schedule `python -m scripts.cleanup_sessions` daily. PostgreSQL backup contains encrypted session tokens; protect its encryption key separately. Do not add private offline caching.
Configure the central proxy with request/body/time limits and TLS. TLS/proxy provisioning belongs to the platform.


## Autenticação local de desenvolvimento

O perfil precisa ser selecionado explicitamente com `--profile`; `ENVIRONMENT` nunca escolhe o perfil. `python -m src --profile dev` usa SQLite separado e uma chave persistente em `.local/session.key`, nunca a URL ou chave dos perfis externos. Arquivos `.local` não devem ser versionados ou enviados na imagem.

AUTH_MODE=local é aceito somente com banco SQLite, ENVIRONMENT=development, HOST de loopback e PUBLIC_URL HTTP de loopback. O middleware rejeita peers e Host externos; as rotas /auth/dev não existem quando a aplicação é carregada em OIDC. Produção rejeita SQLite, fixtures locais, debug e cookies inseguros.

O login local exige nonce CSRF da sessão mais Origin de loopback na porta configurada; rotaciona o cookie ao escolher uma identidade fictícia. Não emite JWTs locais nem imita os endpoints de um IdP. Fixtures não podem ser usadas como autenticação real.

No SQLite local, sem RLS, use exclusivamente a transação tenant e os modelos TenantRecord para dados compartilhados. O filtro ORM e a guarda de escrita limitam testes funcionais, mas não defendem uma aplicação comprometida ou acesso direto à conexão. Os testes PostgreSQL continuam obrigatórios para banco/permissões.
