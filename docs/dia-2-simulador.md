# Dia 2 - Simulador

Objetivo: validar o fluxo conversacional sem depender ainda do WhatsApp real ou de um provedor LLM.

## Issues em Doing

- #13 OrderAgent
- #18 Prompt v1

## Acoes

### Prompt v1 (#18)

- Documentar o contrato do atendente em `docs/prompts/order_agent_v1.md`.
- Definir persona, regras, estados e formato de saida esperado.
- Restringir o agente para nao inventar itens, precos, prazos ou informacoes nao fornecidas.
- Definir regra de fallback humano.

### OrderAgent (#13)

- Criar catalogo estatico minimo da POC.
- Criar helper deterministico para conduzir o fluxo de pedido.
- Persistir mensagens inbound e outbound usando a camada de conversa.
- Atualizar o estado da conversa a cada mensagem.
- Expor `POST /simulator/messages` para testar o fluxo sem WhatsApp.

## Fluxo Simulado

```text
Cliente informa pedido
Agente reconhece item do catalogo
Agente solicita endereco
Cliente informa endereco
Agente solicita confirmacao
Cliente confirma
Agente finaliza pedido
```

## Validacao

Executar:

```bash
./scripts/validate-foundation.sh
```

Critérios de aceite:

- `POST /simulator/messages` aparece no OpenAPI.
- O fluxo basico chega ao estado `completed`.
- Mensagens inbound e outbound sao persistidas.
- Pedido fora do fluxo pode ir para `handoff`.
