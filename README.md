# falange-mvp
Automatizar atendimento operacional via WhatsApp usando IA.

## Ambiente local da POC

Carregue as ferramentas locais:

```bash
source scripts/dev-env.sh
```

Valide o ambiente:

```bash
node --version
npm --version
gh auth status
gh repo view falange-labs/falange-mvp
gh project view 1 --owner falange-labs
```

As ferramentas baixadas e a credencial local do GitHub CLI ficam em `.tools/`,
que é ignorado pelo Git.

## Foundation

O backend inicial já inclui:

- `FastAPI`
- `GET /health`
- `GET /`
- persistência para conversas, mensagens, leads, pilotos e clientes
- SQLite em local/testes e PostgreSQL em produção (`postgresql+psycopg://...`)
- configuração por ambiente
- `Dockerfile`
- `docker-compose.yml`

## Migrações (Alembic) e multi-tenant

Em produção (PostgreSQL) o schema é gerido por **Alembic** — `create_all` não
altera tabelas existentes. As migrações rodam automaticamente no startup; bancos
legados (criados pela versão antiga via `create_all`) são adotados com `stamp` da
baseline antes das migrações novas. Em local/testes (SQLite) seguimos com
`create_all`.

Comandos úteis:

```bash
alembic upgrade head        # aplica migrações
alembic revision --autogenerate -m "minha mudança"
alembic check               # acusa drift entre models e migrações
```

O backend é **multi-tenant**: um único webhook/token atende vários adopters,
roteando por `phone_number_id`. Cadastrar um adopter é inserir dados (sem
deploy). Seed inicial (Falangelabs tenant-zero + Natália):

```bash
FALANGE_WHATSAPP_PHONE_NUMBER_ID=... NATALIA_WHATSAPP_PHONE_NUMBER_ID=... \
  python -m app.seed
```

Detalhes do modelo e do roadmap em
[`docs/arquitetura-multi-tenant.md`](docs/arquitetura-multi-tenant.md).

## Persistência e funil

Em produção o backend usa o PostgreSQL provisionado pelo repositório
`falange-mvp-infra` (container `falange-postgres` na rede privada
`falange-internal`, sem exposição na internet). Veja
[`docs/persistencia-postgres.md`](docs/persistencia-postgres.md) para o modelo
de dados, o funil e as métricas usadas pelo Grafana.

Execução local esperada:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Para preparar e validar tudo de uma vez:

```bash
./scripts/bootstrap-local.sh
./scripts/validate-foundation.sh
```

Endpoints de persistência:

```text
POST /conversations
GET /conversations/{conversation_id}
PATCH /conversations/{conversation_id}/state
POST /conversations/{conversation_id}/messages
GET /conversations/{conversation_id}/messages
```

Endpoint do simulador:

```text
POST /simulator/messages
```

Endpoints do funil e comercial:

```text
POST /funnel/landing-events        # topo do funil (page_view / whatsapp_click)
GET  /funnel/metrics               # % sem humano, % handoff, tempo médio
GET  /leads                        # lista (filtra por ?status=)
POST /leads
GET  /leads/{lead_id}
PATCH /leads/{lead_id}/status      # follow-up comercial
POST /pilots
GET  /pilots
PATCH /pilots/{pilot_id}
POST /clients
GET  /clients
```
