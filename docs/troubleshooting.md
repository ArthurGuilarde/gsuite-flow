# Diagnóstico

| Sintoma | Verificação ou correção |
|---|---|
| `--profile` é obrigatório | Inclua `--profile dev`, `--profile integrated` ou `--profile production` em cada comando. `ENVIRONMENT` não seleciona perfil. |
| Arquivo `--env-file` não encontrado | Confira o caminho relativo à pasta atual ou use caminho absoluto. |
| Porta ocupada | Escolha uma porta livre, por exemplo `python -m src --profile dev --port 8010`. |
| Login local não aparece | Confirme `--profile dev` e abra o endereço loopback informado pela configuração de inicialização. |
| CSRF rejeitado em dev | Use `127.0.0.1` ou `localhost` consistentemente na mesma porta e atualize a página para obter nova sessão. |
| SQLite não aparece no caminho esperado | O perfil dev usa `.local/dev.sqlite3`; defina `DEV_DATABASE_URL` para mudar o arquivo. Ele ignora `DATABASE_URL` e `MIGRATION_DATABASE_URL`. |
| Banco sem revisão atual | Execute `python -m src migrate --profile <perfil>` usando o arquivo de ambiente correto. Em production, migre com `.env.production.migration`. |
| Migração production não tem credencial owner | Inclua `MIGRATION_DATABASE_URL` no arquivo `.env.production.migration`; use role owner diferente da role runtime e o mesmo alvo PostgreSQL. |
| Check/serve recusou `MIGRATION_DATABASE_URL` em production | Remova essa variável do shell/secret runtime. Ela só deve estar no ambiente da tarefa de migração. |
| Falha de acesso PostgreSQL | Confira URLs e roles runtime/migration, firewall e conectividade. Os logs mostram apenas identificador do banco sem credenciais. |
| Falha discovery/JWKS | Confira `OIDC_ISSUER` e acesso HTTPS ao Authentik; não use fixtures para contornar falha em production. |
| Login funciona, tenant negado | Confira `APP_ID`, audience, membership, permissões e disponibilidade do Core. |
| Sessão local inválida após troca de chave | Faça login novamente; não copie a chave local para production. |
| `mypy` falha no validate ou no hook | Corrija o tipo apontado em `src/`. Use `# type: ignore[código]` só com o código do erro; ignores sem uso também falham. |
| Cobertura abaixo do mínimo | Adicione testes para o código novo. Só reduza `fail_under` em `pyproject.toml` com justificativa no PR. |
| Hook do pre-commit falha ou não roda | Ative o `.venv` antes de commitar; os hooks de ruff e mypy usam o Python do ambiente. Rode `pre-commit install` em clones novos. |
| `pip-audit` acusa vulnerabilidade | Atualize só o pacote com `pip-compile ... --upgrade-package <pacote>`, restaure os marcadores de Windows em `requirements.lock` e rode o validate. |
| Trivy reprova a imagem no CI | Aceite o PR do Dependabot para a imagem base ou atualize o pacote Python apontado; não desative o passo. |
| `bootstrap.py --check` sai com código 1 | É esperado enquanto houver pendência listada. Resolva cada item `PENDENTE`; seções `A definir` dependem do responsável pelo produto. |
| Container recusa iniciar com `MIGRATION_DATABASE_URL` | O `CMD` da imagem usa `--profile production`. Entregue a credencial owner só à tarefa de migração. |
| PostgreSQL local não sobe no Compose | Confira as variáveis `POSTGRES_PASSWORD`, `APP_DB_PASSWORD` e a saúde do serviço. A inicialização cria roles apenas em volume novo. |

Se a configuração do Compose usa volume existente, mudar senha no arquivo `.env` não altera roles já criadas; faça rotação explícita. Consulte também [operações](operations.md), [deploy](deploy.md) e [segurança](security.md).
