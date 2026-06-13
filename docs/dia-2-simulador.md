# Dia 2 - Simulador

Objetivo: validar o fluxo conversacional sem depender ainda do WhatsApp real ou de um provedor LLM.

## Issues em Doing

- #13 DiscoveryAgent
- #18 Prompt v1

## Acoes

### Prompt v1 (#18)

- Documentar o contrato do atendente em `docs/prompts/discovery_agent_v1.md`.
- Definir persona, regras, estados e formato de saida esperado.
- Restringir o agente para nao inventar preco, prazo, funcionalidade ou resultado.
- Definir regra de fallback humano.

### DiscoveryAgent (#13)

- Criar helper deterministico para conduzir a conversa guiada de descoberta.
- Conduzir o lead a contar a essencia do negocio (uma pergunta por vez).
- Persistir mensagens inbound e outbound usando a camada de conversa.
- Atualizar o estado da conversa a cada mensagem.
- Expor `POST /simulator/messages` para testar o fluxo sem WhatsApp.

## Fluxo Simulado

```text
Lead demonstra interesse (vindo da landing page)
Agente sauda e pergunta sobre o negocio
Agente coleta canais, dor, objetivo de automacao, volume e contato
Agente apresenta um resumo da essencia do negocio
Lead confirma
Agente encaminha para o time da Falangelabs
```

## Validacao

Executar:

```bash
./scripts/validate-foundation.sh
```

Critérios de aceite:

- `POST /simulator/messages` aparece no OpenAPI.
- O fluxo guiado chega ao estado `completed` apos a confirmacao do resumo.
- Mensagens inbound e outbound sao persistidas.
- Pedido de humano (ou reclamacao) pode ir para `handoff`.
