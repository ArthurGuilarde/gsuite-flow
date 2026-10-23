# Deploy

Produção usa o PostgreSQL da plataforma e o proxy TLS central. Não instale outra instância de Authentik, Core, gateway ou proxy. O perfil `production` consome PostgreSQL e OIDC/Core reais; ele exige HTTPS público, cookies seguros e chave de criptografia de sessão, e nunca aceita autenticação local. Consulte [operações](operations.md) para preparar os comandos e [contrato com o Core](core-contract.md) para a integração.

## Preparar serviços e configuração

1. Crie um banco dedicado à aplicação, com usuário owner de migração e role de runtime `guilarde_app` com `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`. Revogue `PUBLIC CREATE` no schema `public`; conceda ao runtime somente os privilégios necessários. Use credenciais e regras de rede separadas.
2. Registre `suite-app.json` no Core pelo mecanismo da plataforma. O bootstrap personaliza metadados e prepara o manifesto, mas não faz o registro remoto.
3. Configure no Authentik um provider OIDC confidencial. Confirme issuer e descoberta, JWKS, audience, client ID/secret e callback exato da aplicação. Configure endereço e credenciais do Core conforme [contrato](core-contract.md).
4. Copie [.env.production.example](../.env.production.example) para `.env.production` e substitua todos os placeholders. Esse é o arquivo de runtime: não inclua MIGRATION_DATABASE_URL. Os valores de issuer/audience/callback precisam corresponder ao provider da aplicação. A URL owner deve usar uma role diferente da role runtime e apontar para o mesmo banco e servidor.

## Preparar os arquivos

No PowerShell:

```powershell
Copy-Item .env.production.example .env.production
# Edite .env.production com as URLs, client/secret e credenciais runtime reais.
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Grave a chave gerada em SESSION_ENCRYPTION_KEY do arquivo runtime.
Copy-Item .env.production .env.production.migration
# Acrescente MIGRATION_DATABASE_URL com a URL de outra role owner SOMENTE ao arquivo .migration.
```

No Linux:

```bash
cp .env.production.example .env.production
# Edite .env.production com a configuração real, sem credencial owner.
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Grave a chave gerada em SESSION_ENCRYPTION_KEY.
cp .env.production .env.production.migration
# Acrescente MIGRATION_DATABASE_URL de uma role owner diferente da runtime, SOMENTE ao arquivo .migration.
chmod 600 .env.production .env.production.migration
```

Ambos os arquivos são privados e ignorados pelo Git. Apenas o exemplo sem segredos é versionado. Não os inclua na imagem. A aplicação precisa preservar a chave de sessão entre reinícios; gerar outra chave invalida as sessões existentes.

Carregue cada arquivo no gerenciador de segredos do ambiente correspondente. Disponibilize `.env.production.migration` apenas à tarefa de migração; o processo app recebe somente `.env.production`. Não imprima arquivos ou valores de segredo nos logs de CI.

## Aplicar migrações e iniciar

Faça backup antes de alterar um banco existente. Execute uma única tarefa com o arquivo de migração e inicie os servidores com o arquivo runtime:

```bash
python -m src migrate --profile production --env-file .env.production.migration
python -m src check --profile production --env-file .env.production
python -m src --profile production --env-file .env.production
```

O CLI recusa check/serve de production quando MIGRATION_DATABASE_URL ainda está no ambiente. Se você exportou essa variável no shell, remova-a antes do runtime: `unset MIGRATION_DATABASE_URL` no Bash ou `Remove-Item Env:MIGRATION_DATABASE_URL -ErrorAction SilentlyContinue` no PowerShell. Variáveis exportadas no shell têm precedência sobre o arquivo de ambiente.

O check valida configuração, banco, revisão e discovery/JWKS OIDC; o fluxo real de usuário e grants do Core deve ser validado em staging. O servidor não migra banco nem cria usuários ao iniciar. Execute uma tarefa de migração por release antes de iniciar réplicas.

## Rede, probes e aceite

Construa a imagem em CI (docker build -t <imagem>:<versao> .), publique-a no registry aprovado com tag imutavel ou digest e implante o mesmo artefato que passou pelas validacoes. Encaminhe o proxy central para app:8000 em rede privada. Restrinja PostgreSQL as redes da aplicacao e da migracao. Monitore /health/live para saude do processo e /health/ready para prontidao; colete logs de stdout. O `CMD` da imagem é `python -m src serve --profile production --host 0.0.0.0 --port 8000`: a CLI aplica as travas de production (recusa `MIGRATION_DATABASE_URL`, proíbe `--reload`) antes de iniciar o Uvicorn e informa profile, auth, endereço e identificador seguro do banco. A imagem declara `HEALTHCHECK` em `/health/ready`. Mantenha o processo runtime sem credenciais owner. Antes de publicar, o CI audita `requirements.lock` com pip-audit e faz o scan da imagem com Trivy (HIGH/CRITICAL com correção reprovam).

Antes de liberar tráfego, valide em staging com Authentik/Core reais e role runtime não-owner, incluindo revogação de membership. Testes unitários e mocks não substituem essa verificação de interoperabilidade e revogação.

## Migrações existentes e recuperação

A revisão `0001_template` é o baseline para bancos novos e cria `browser_sessions`. Bancos em revisões anteriores (`0001_suite` ou `0001_initial_users`) precisam de plano de migração próprio; não use `stamp` nem apague dados para contornar divergência. Preserve o histórico de migrações da aplicação existente e valide qualquer upgrade em cópia/staging.

Faça rollback da versão da aplicação apenas quando o schema continuar compatível. Caso contrário, publique uma migração corretiva para frente. O script local de inicialização PostgreSQL do Compose só roda em volume novo; mudar senha no `.env` não altera roles de volume existente. Rotacione credenciais explicitamente e nunca remova dados para corrigir configuração.


## Execução sem shell interativo

Para subir em outra interface atrás do proxy, use `--host 0.0.0.0 --port 8000` somente em integrated/production. O mesmo comando deve ser configurado no supervisor de processos ou orquestrador utilizado; não mantenha o terminal como processo de produção permanente. Use um arquivo/secret de migração separado do arquivo de runtime para não distribuir credenciais owner.

O Compose entregue é uma topologia de desenvolvimento PostgreSQL. Seus serviços app/migrate rodam a CLI com `--profile integrated` e AUTH_MODE=oidc; não habilitam o login fictício. Para produção em Docker, use o `CMD` padrão da imagem (perfil production) e injete os segredos do arquivo runtime; para a migração, rode a mesma imagem com `python -m src migrate --profile production` e apenas os segredos do arquivo de migração. A imagem não migra na inicialização.
