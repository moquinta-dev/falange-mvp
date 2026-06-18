# Persistência (PostgreSQL) e funil de atendimento

Esta camada armazena os dados gerados pelo funil da FalangeLabs e serve de data
source para o Grafana. A infraestrutura (container do PostgreSQL com volume
persistente + backup diário e o Grafana) vive no repositório `falange-mvp-infra`.

## Banco de dados

- **Local/testes:** SQLite (`sqlite:///data/falange.db`).
- **Produção:** PostgreSQL via `psycopg` (driver `postgresql+psycopg://`).
  O backend conecta-se ao container `falange-postgres` pela rede privada
  `falange-internal`. O banco **não tem exposição na internet**.

`DATABASE_URL` em produção:

```text
postgresql+psycopg://falange:SENHA@falange-postgres:5432/falange
```

No startup o backend espera o banco ficar disponível (retry configurável por
`DATABASE_CONNECT_RETRIES` / `DATABASE_CONNECT_RETRY_DELAY`), cria as tabelas e,
no PostgreSQL, cria as views de métricas.

## Modelo de dados

| Tabela           | Conteúdo                                                        |
| ---------------- | --------------------------------------------------------------- |
| `landing_events` | Topo do funil: `page_view` e `whatsapp_click` (com UTM)         |
| `conversations`  | Conversas do WhatsApp + marcos `completed_at` / `handed_off_at` |
| `messages`       | Histórico de mensagens (inbound/outbound)                       |
| `leads`          | Lead capturado pelo discovery + status do funil comercial       |
| `pilots`         | Pilotos executados com leads qualificados                       |
| `clients`        | Primeiros clientes convertidos                                  |

## Funil

```
Landing page (www.falangelabs.io)
   │  beacon page_view / whatsapp_click -> POST /funnel/landing-events
   ▼
Clique no WhatsApp (wa.me com prompt determinístico)
   ▼
Discovery agent determinístico (webhook WhatsApp)
   │  coleta: negócio, canais, dor, objetivo, volume, contato
   ▼
Persistência no banco
   │  resumo confirmado -> lead "qualified" + conversation.completed_at
   │  pedido de humano  -> lead "handoff"  + conversation.handed_off_at
   ▼
Follow-up comercial
      GET /leads?status=qualified  ->  PATCH /leads/{id}/status (contacted, pilot, client...)
```

Status do lead: `new` → `contacted` → `qualified` → `pilot` → `client`
(ou `lost` / `handoff`).

## Métricas

Calculadas de duas formas equivalentes:

- **API** (`GET /funnel/metrics`): computadas em Python (funciona em SQLite e
  PostgreSQL).
- **Grafana**: lê as views SQL criadas no PostgreSQL pelo backend
  (`app/core/analytics.py`), com o papel somente leitura `grafana_ro`.

| Métrica                          | Origem                                  |
| -------------------------------- | --------------------------------------- |
| % conversas concluídas sem humano| `vw_conversation_metrics` (agregado no Grafana, filtro por seed) |
| % conversas com handoff          | `vw_conversation_metrics` (agregado no Grafana, filtro por seed) |
| Tempo médio de atendimento       | `vw_conversation_metrics.handle_time_seconds` (primeira à última mensagem) |
| Volume / engajamento / por seed  | `vw_daily_metrics`, `vw_tenant_overview` |

Views criadas: `vw_conversation_metrics`, `vw_funnel_metrics`,
`vw_daily_metrics`, `vw_lead_funnel`, `vw_tenant_overview`.

O dashboard Grafana inclui variável **Seed** (tenants ativos de
`falange-mvp-seeds`) para filtrar todas as métricas por adopter.

## Variáveis de ambiente relevantes

```text
DATABASE_URL                  conexão do banco
DATABASE_CONNECT_RETRIES      tentativas de conexão no startup (default 10)
DATABASE_CONNECT_RETRY_DELAY  intervalo entre tentativas, em segundos (default 3)
GRAFANA_DB_ROLE               papel somente leitura do Grafana (default grafana_ro)
CORS_ALLOW_ORIGINS            origens permitidas para o beacon da landing page
```

## Deploy

O `deploy/hostinger/docker-compose.yml` conecta o backend às redes
`traefik-proxy` (público) e `falange-internal` (privada, acesso ao banco). O
workflow de deploy injeta `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD`,
e garante a rede `falange-internal`. Suba a stack de dados (`falange-mvp-infra`)
antes do backend.
