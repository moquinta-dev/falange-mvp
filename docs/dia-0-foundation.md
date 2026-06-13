# Dia 0 - Foundation

Objetivo: deixar a base tecnica da POC pronta para executar API, persistir conversas e validar o ambiente local com Docker Compose.

## Issues em Doing

- #10 Bootstrap FastAPI
- #11 Persistencia Conversa
- #15 Docker Compose

## Acoes

### Bootstrap FastAPI (#10)

- Criar estrutura inicial do backend.
- Expor `GET /` com metadados da aplicacao.
- Expor `GET /health` para checagem operacional.
- Configurar settings por variaveis de ambiente.
- Documentar bootstrap local.

### Persistencia Conversa (#11)

- Adicionar `DATABASE_URL` em settings.
- Usar SQLite para a POC com arquivo em `/data/falange.db`.
- Criar modelos `Conversation` e `Message`.
- Criar helpers para criar/recuperar conversa, persistir mensagem, atualizar estado e listar historico recente.
- Expor endpoints internos de conversa e mensagem para futura integracao com webhook e DiscoveryAgent.
- Cobrir fluxo minimo com testes funcionais.

### Docker Compose (#15)

- Criar `Dockerfile` para a API.
- Criar `docker-compose.yml` para subir o servico `api`.
- Montar `./app:/app/app` para reload em desenvolvimento.
- Montar `./data:/data` para persistencia SQLite local.
- Validar `docker compose config`.

## Validacao

Executar:

```bash
./scripts/bootstrap-local.sh
./scripts/validate-foundation.sh
docker compose up -d --build api
```

Critérios de aceite:

- `GET /health` retorna `{"status": "ok"}`.
- `http://localhost:8000/docs` lista os endpoints de conversa.
- Testes funcionais passam.
- Compose sobe a API na porta `8000`.

## Entregaveis

- API FastAPI inicial.
- Persistencia SQLite funcional.
- Endpoints de conversa e mensagem.
- Scripts de bootstrap e validacao local.
- Docker Compose pronto para desenvolvimento.
