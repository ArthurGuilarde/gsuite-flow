# Convenção de ADRs

Esta convenção é obrigatória para colaboradores e LLMs. Todos os Architecture Decision Records do projeto ficam em `docs/adrs/`; [MASTER-ADR.md](MASTER-ADR.md) é seu índice central.

## Quando criar

Registre decisões relevantes sobre arquitetura, stack, persistência, identidade, segurança, isolamento de tenants, contratos de integração, padrões de implementação ou operação. Inclua mudanças com alternativas e consequências duradouras.

Correções pontuais, formatação e tarefas rotineiras sem impacto arquitetural não exigem um ADR. Consulte o Master ADR e os registros relacionados antes de propor ou implementar uma nova decisão.

## Fluxo obrigatório

1. Consulte os IDs existentes nos arquivos e no Master ADR. Use o maior ID existente + 1, com no mínimo três dígitos; comece em `001`. Não reutilize números, renumere registros ou crie IDs concorrentes.
2. Copie [TEMPLATE-ADR.md](TEMPLATE-ADR.md) para `ADR-NNN-descricao-curta.md`. Use um slug em minúsculas, sem acentos, com hífens.
3. Preencha todos os campos e seções. Use datas `YYYY-MM-DD`. Quando algo não se aplicar, escreva `Não se aplica`; quando for desconhecido, `Não informado`. Não deixe placeholders no ADR final.
4. Fundamente o contexto e a decisão em evidências disponíveis. Não invente aprovação, participantes, datas históricas, URLs ou IDs de sessões.
5. Use `🔄 Em discussão` para propostas ainda não aprovadas. Use `✅ Aceito` somente quando houver autorização explícita do usuário ou responsável pelo projeto; cite a origem disponível. Autorização para implementar uma decisão expressa conta como aceite dessa decisão, não de alternativas não discutidas.
6. Adicione ou atualize a linha correspondente no Master ADR, mantendo exatamente o mesmo ID no arquivo, título, tabela e índices. Atualize a data do Master, o índice por área e o mapa de dependências quando aplicável.
7. Vincule dependências e substituições usando caminhos relativos para ADRs reais. Se não houver dependências, declare isso; não crie um diagrama vazio.
8. Confira links, IDs únicos, status, datas e coerência com o código. Inclua a atualização da documentação e do índice na mesma alteração.

## Campos e seções do schema

| Elemento | Regra |
|---|---|
| Título | `# ADR-NNN — Título da decisão` |
| Data | Data de criação do registro, em ISO; registre separadamente a data da decisão se conhecida e diferente |
| Status | Um dos quatro estados definidos abaixo |
| Área | Categoria principal usada também no Master ADR |
| Origem da decisão | Solicitação, issue, PR ou sessão identificável; link somente quando conhecido |
| Responsável pelo aceite | Nome ou papel conhecido; `Não informado` quando não disponível |
| Relações | Dependências, ADRs substituídos e ADR substituto, ou `Não se aplica` |
| Contexto | Problema, restrições e critérios que motivam a decisão |
| Decisão | Escolha concreta, escopo e limites |
| Alternativas consideradas | Alternativas reais e motivos de descarte; não crie alternativas fictícias |
| Consequências | Benefícios, custos, riscos e limitações |
| Validação | Critérios de aceite e evidências, distinguindo execução de pendências |
| Referências | Links e documentos existentes, ou `Não se aplica` |

## Estados e evolução

| Estado | Significado |
|---|---|
| 🔄 Em discussão | Proposta pendente de decisão |
| ✅ Aceito | Decisão explicitamente aprovada |
| ⚠️ Depreciado | Decisão antes aceita que deixou de valer ou foi substituída |
| ❌ Rejeitado | Proposta analisada e descartada |

Registre mudanças de estado na seção Histórico. Preserve os registros rejeitados e depreciados para manter a rastreabilidade.

Não altere o sentido de um ADR aceito para representar uma decisão nova. Crie outro ADR, registre nele `Substitui: ADR-NNN`, marque o anterior como Depreciado e registre nele `Substituído por: ADR-MMM`. Atualize o Master e as referências. Correções editoriais e acréscimos de evidências não mudam a decisão.

## Checklist de entrega

- Arquivo em `docs/adrs/`, seguindo o template, sem placeholders.
- Mesmo ID no nome do arquivo, título, Master e referências.
- Status e aceite sustentados por evidências.
- Master com tabela, índice por área e dependências coerentes.
- Links relativos resolvidos e guias gerais atualizados quando afetados.
