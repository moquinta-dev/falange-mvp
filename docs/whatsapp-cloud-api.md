# WhatsApp Cloud API

Este documento cobre a primeira integracao oficial com a WhatsApp Cloud API da
Meta.

## Endpoint publico

Configure no painel da Meta:

```text
https://<VPS_APP_DOMAIN>/webhook/whatsapp
```

Use o mesmo `WHATSAPP_VERIFY_TOKEN` cadastrado nos secrets do environment
`production` do GitHub.

## Secrets

Obrigatorios para deploy:

```text
WHATSAPP_VERIFY_TOKEN
WHATSAPP_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID
META_APP_SECRET
```

Opcionais:

```text
META_GRAPH_API_VERSION=v23.0
META_VALIDATE_SIGNATURE=false
```

`META_VALIDATE_SIGNATURE=false` e o padrao da POC para permitir os testes curl
sem assinatura. Para exigir `X-Hub-Signature-256`, defina
`META_VALIDATE_SIGNATURE=true`.

## FT-WA-001 - Webhook verification

```bash
curl "https://<VPS_APP_DOMAIN>/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=<WHATSAPP_VERIFY_TOKEN>&hub.challenge=123"
```

Esperado:

```text
123
```

## FT-WA-002 - Receber mensagem fake

```bash
curl -X POST "https://<VPS_APP_DOMAIN>/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "5571999999999",
            "id": "wamid.test001",
            "type": "text",
            "text": { "body": "quero uma pizza grande de calabresa" }
          }]
        }
      }]
    }]
  }'
```

Esperado:

```json
{"status":"ok","conversation_id":1}
```

O `conversation_id` varia por ambiente.

## FT-WA-003 - Evento sem mensagem

```bash
curl -X POST "https://<VPS_APP_DOMAIN>/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "statuses": [{ "id": "wamid.status001" }]
        }
      }]
    }]
  }'
```

Esperado:

```json
{"status":"ignored"}
```

## Comportamento

- `GET /webhook/whatsapp` retorna o `hub.challenge` quando o verify token bate.
- `POST /webhook/whatsapp` ignora eventos sem mensagem.
- Mensagens de texto sao persistidas como inbound com `external_message_id`.
- `message_id` repetido retorna `duplicate` e nao chama a Cloud API de novo.
- Mensagens nao-texto recebem a resposta `MESSAGE_TYPE_NOT_SUPPORTED`.
- A resposta do OrderAgent e enviada via
  `/{WHATSAPP_PHONE_NUMBER_ID}/messages`.
