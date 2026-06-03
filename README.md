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
- persistência SQLite para conversas e mensagens
- configuração por ambiente
- `Dockerfile`
- `docker-compose.yml`

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
