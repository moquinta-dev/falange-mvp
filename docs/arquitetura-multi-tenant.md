# Arquitetura multi-tenant (triagem por adopter)

Este documento descreve o modelo para servir múltiplos adopters (clientes da
Falangelabs) com **um único backend e um único webhook**, sem deploy a cada novo
adopter. É o roteiro de evolução do `falange-mvp` a partir do agente de
descoberta single-tenant atual.

## Contexto

O primeiro adopter é a **Natália** (personal trainer). O objetivo é automatizar a
**triagem de novos alunos** — hoje uma tarefa manual e demorada. Ela chegou pela
landing page da Falangelabs (virou lead) e tem um número de WhatsApp dedicado,
registrado sob a **Meta Business / WABA da Falangelabs**.

### O insight que torna tudo multi-tenant "de graça"

Como todos os números entram sob a **mesma WABA da Falangelabs**:

- **Um único webhook** recebe eventos de *todos* os números (a Meta assina no
  nível do app, não do número).
- **Um único access token** (system user da Falangelabs) envia em nome de
  qualquer número — o que muda por adopter é apenas o `phone_number_id`.

Logo, "receber e enviar" já é naturalmente multi-tenant. O que falta é
**roteamento por `phone_number_id` + dados por tenant**.

## Princípios

- **Código genérico, comportamento em dados.** Adicionar adopter = inserir
  linhas (tenant + workflow + destino de notificação), nunca deploy.
- **Roteamento por `phone_number_id`** (1 webhook, 1 token, N números).
- **Falangelabs = tenant-zero** (dogfooding): o próprio discovery agent vira só
  mais um workflow. Se o engine não roda o fluxo da Falange, não está pronto
  para a Natália.
- **Duas camadas separadas:**
  - "Conversar e triar" → genérico e multi-tenant.
  - "Vender a plataforma" (piloto, cliente, landing-event, funil de aquisição)
    → exclusivo da Falangelabs.
- **RabbitMQ fica fora do escopo inicial.** O webhook síncrono atende o volume
  atual; o broker é evolução futura gatilhada por dor real (volume/picos/IA
  lenta).

## Modelo de dados

```txt
Tenant
- id
- name                       "Natalia Ferreira Corpo e Mente"
- whatsapp_phone_number_id   ← chave de roteamento (vem da Meta)
- workflow_id                qual fluxo de triagem usar
- notify_channel             "email" | "whatsapp"
- notify_target              e-mail OU telefone pessoal do dono
- active

Workflow
- id / key                   "triagem_personal_v1"
- definition (JSON)          a árvore de perguntas

Conversation (estendida)
- tenant_id                  ← novo
- current_node_id            onde a conversa está na árvore (Fase 1)
- answers (JSON)             respostas coletadas (Fase 1)
```

### Workflow como árvore de decisão (data-driven)

O fluxo da Natália **não é linear** (o discovery agent atual é). É uma árvore com
ramificações:

```txt
Boas-vindas → nome? → faixa etária? → interesse:
   ├─ Personal      → online | presencial
   ├─ Yoga          → particular | em grupo
   └─ Consultoria   → fortalecimento | fortalecimento + corrida
→ resumo → notifica o dono do tenant
```

O `definition` é um grafo de nós serializado em JSON; o engine (Fase 1) caminha
pelos nós com base em `current_node_id` + `answers`:

```json
{
  "start": "ask_name",
  "nodes": {
    "ask_name":     { "type": "text",   "prompt": "Oi! Como é o seu nome?", "collect": "nome", "next": "ask_age" },
    "ask_age":      { "type": "text",   "prompt": "Qual a sua faixa etária?", "collect": "faixa_etaria", "next": "ask_interest" },
    "ask_interest": { "type": "choice", "prompt": "Você está interessada em:", "collect": "interesse",
                      "options": [
                        { "label": "Aulas de Personal",  "next": "personal_mod" },
                        { "label": "Aulas de Yoga",      "next": "yoga_mod" },
                        { "label": "Consultoria online", "next": "consultoria_obj" }
                      ] },
    "personal_mod": { "type": "choice", "prompt": "Personal: online ou presencial?", "collect": "modalidade",
                      "options": [ {"label":"Online","next":"done"}, {"label":"Presencial","next":"done"} ] },
    "yoga_mod":     { "type": "choice", "prompt": "Yoga: particular ou em grupo?", "collect": "modalidade",
                      "options": [ {"label":"Particular","next":"done"}, {"label":"Em grupo","next":"done"} ] },
    "consultoria_obj": { "type": "choice", "prompt": "Consultoria: qual objetivo?", "collect": "objetivo",
                      "options": [ {"label":"Fortalecimento","next":"done"}, {"label":"Fortalecimento + corrida","next":"done"} ] },
    "done":         { "type": "terminal", "summary": true }
  }
}
```

## Notificação ao tenant

Ao concluir a triagem (nó `terminal`), o dono do tenant recebe o resumo no canal
configurado (`notify_channel` + `notify_target`):

- **E-mail (padrão):** simples, confiável, sem restrição de janela.
- **WhatsApp no número pessoal (evolução):** mensagem iniciada pelo negócio fora
  da janela de 24h exige **template utility aprovado** pela Meta — o número
  pessoal nunca iniciou conversa. Por isso o e-mail é o padrão inicial.

## Migrações (Alembic)

O schema deixa de ser criado só por `Base.metadata.create_all`. Adotamos
**Alembic** como ferramenta de migração para PostgreSQL (produção), porque
`create_all` cria tabelas novas, mas **não altera tabelas existentes** (ex.:
adicionar `tenant_id` em `conversations`).

Estratégia de coexistência:

- **SQLite (local/testes):** `Base.metadata.create_all` (caminho rápido).
- **PostgreSQL (produção):** `alembic upgrade head` no startup.
  - Banco legado (criado por `create_all`, sem `alembic_version`): o runner
    detecta a tabela `conversations` existente sem `alembic_version`, faz
    `stamp` da baseline e então aplica as migrações novas. Isso adota o banco
    existente sem recriar tabelas.

## Roteamento no webhook (Fase 0)

1. `extract_whatsapp_message` passa a retornar `phone_number_id`
   (`value.metadata.phone_number_id`).
2. O webhook resolve `tenant = resolve_by_phone_number_id(...)`.
3. Tenant encontrado → conversa recebe `tenant_id`; resposta é enviada **a partir
   do `phone_number_id` do tenant**.
4. Tenant não encontrado → comportamento controlado por
   `REQUIRE_KNOWN_TENANT`:
   - `false` (padrão na transição): fallback para o número único de `settings`
     (retrocompatível com o setup single-tenant atual).
   - `true`: ignora o evento (`status: unknown_tenant`).

O token de acesso passa a ser o **system-user da Falangelabs** (envia por
qualquer número da WABA); `WHATSAPP_PHONE_NUMBER_ID` em `settings` vira apenas o
número de fallback.

## Roadmap por fases

- **Fase 0 — Fundação multi-tenant (esta entrega):** Alembic, models `Tenant` e
  `Workflow`, `Conversation` estendida, roteamento por `phone_number_id` no
  webhook, envio pelo número do tenant, seed de Falange tenant-zero + Natália.
- **Fase 1 — Engine genérico de workflow (implementada):**
  `app/helpers/workflow_engine.py` interpreta a árvore (`text`/`choice`/
  `terminal`) caminhando por `current_node_id` + `answers`. `choice` é
  apresentado como opções numeradas e aceita número ou rótulo. O webhook roteia
  tenants com workflow pelo engine; sem workflow (fallback/sem tenant) segue no
  discovery agent legado. Em `terminal` marca a conversa como concluída e faz
  upsert de lead (a separação de funil por tenant é a Fase 3).
- **Fase 2 — Notificação ao tenant:** e-mail (padrão) e template WhatsApp
  (evolução) ao concluir a triagem.
- **Fase 3 — Funil/analytics por tenant:** `tenant_id` em `leads`/`landing_events`
  e views escopadas por tenant; piloto/cliente/landing-event como extensão
  só-Falange.
- **Fase 4 — Onboarding sem deploy (implementada):** endpoints admin
  autenticados (`PUT /admin/workflows/{key}`, `PUT /admin/tenants/{phone_number_id}`,
  além de `GET` para listagem/leitura) que fazem upsert idempotente de workflow e
  tenant. A definição do workflow é validada (`workflow_engine.validate_definition`)
  antes de persistir. Esses endpoints são a base do GitOps: o repositório
  `falange-mvp-seeds` versiona as definições e uma pipeline as aplica, ativando um
  cliente novo sem deploy do backend.
```

## Fase 4 — Onboarding via API (GitOps)

Ativar um adopter passou a ser declarativo: as definições de workflow e tenant
vivem versionadas em `falange-mvp-seeds` e são aplicadas via API autenticada.

Autenticação: header `X-API-Key: <ADMIN_API_TOKEN>` (ou `Authorization: Bearer`),
o mesmo esquema dos demais endpoints internos.

Endpoints (idempotentes por chave natural):

- `PUT /admin/workflows/{key}` — body `{ "name": str|null, "definition": {...} }`.
  Valida a árvore (`start`/`nodes`, tipos, `next` existentes, alcançabilidade, ao
  menos um `terminal`); `422` se inválida.
- `GET /admin/workflows` e `GET /admin/workflows/{key}` — listagem/leitura.
- `PUT /admin/tenants/{phone_number_id}` — body `{ "name", "workflow_key",
  "notify_channel" (email|whatsapp), "notify_target", "active" }`. `404` se o
  `workflow_key` não existir.
- `GET /admin/tenants` — listagem.

Ordem de aplicação: workflow antes do tenant (o tenant referencia o workflow por
`key`). O `app/seed.py` usa os mesmos helpers (`workflow_helper.upsert_workflow`,
`tenant_helper.upsert_tenant`), então seed local e pipeline GitOps convergem para
o mesmo estado.
