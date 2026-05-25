# PRD — MVP Atendimento IA para WhatsApp (Projeto Falange)

Versão 2.0
Data: 24/05/2026

---

# 1. Visão

Criar uma solução de atendimento automatizado via WhatsApp usando IA para reduzir esforço operacional, melhorar tempo de resposta e permitir que pequenas empresas atendam clientes de forma mais rápida, organizada e escalável.

O objetivo não é substituir pessoas, mas automatizar tarefas repetitivas e liberar tempo operacional.

---

# 2. Problema

Hoje restaurantes e pequenos negócios enfrentam problemas como:

* atendimento lento
* excesso de atendimento manual
* dificuldade de manter padrão de comunicação
* perda de pedidos
* desorganização operacional
* atendimento inconsistente
* excesso de burocracia
* dependência de pessoas para operar o WhatsApp

Resultado:

* clientes desistem
* vendas são perdidas
* operação não escala

---

# 3. Público-alvo

## Cliente pagante

* Donos de pizzarias
* Restaurantes
* Microempreendedores
* Pequenos negócios com atendimento via WhatsApp

## Usuário final

Clientes que entram em contato para realizar pedidos.

---

# 4. Objetivo do MVP

Validar se empresas conseguem concluir pedidos pelo WhatsApp utilizando apoio de IA e reduzir esforço operacional.

Objetivos específicos:

* testar aceitação do produto
* captar clientes piloto
* agilizar atendimento
* automatizar pelo menos 30% do fluxo de pedidos

---

# 5. Fluxo principal

```text
Cliente
↓

Envia mensagem no WhatsApp

↓

IA interpreta intenção

↓

Consulta catálogo

↓

Coleta pedido

↓

Coleta endereço

↓

Confirma pedido

↓

Entrega resumo ao restaurante

↓

(Se necessário)
Escala para humano
```

---

# 6. Jornada exemplo

Cliente:

> Quero uma pizza grande de calabresa

IA:

> Gostaria de adicionar borda recheada?

Cliente:

> Sim

IA:

> Informe seu endereço

Cliente:

> Rua X número 123

IA:

> Confirma pedido e endereço?

Cliente:

> Sim

IA:

> Pedido enviado ao restaurante.

---

# 7. Funcionalidades (IN)

## Atendimento

✅ Receber mensagens pelo WhatsApp

✅ Identificar intenção

✅ Responder automaticamente

---

## Pedido

✅ Consultar catálogo simples

✅ Coletar pedido

✅ Confirmar pedido

---

## Endereço

✅ Receber endereço em texto livre

✅ Estruturar endereço

✅ Confirmar endereço

---

## Operação

✅ Encaminhar atendimento para humano

---

# 8. Decisão sobre endereço

## MVP V1

Cliente escreve livremente.

Exemplo:

> Rua das Flores 120 apto 402

A IA interpreta:

```json
{
 "rua":"Rua das Flores",
 "numero":"120",
 "complemento":"402"
}
```

Depois confirma com cliente.

Exemplo:

> Entendi esse endereço, está correto?

---

## Não entra no MVP

❌ Google Maps
❌ Geocoding
❌ Autocomplete
❌ Validação automática

---

# 9. Fora do escopo (OUT)

Não fazem parte do MVP:

❌ Pagamento

❌ CRM

❌ Dashboard administrativo

❌ Catálogo dinâmico

❌ Analytics avançado

❌ Aplicativo mobile

❌ Multiempresa

❌ Voz

❌ Integrações complexas

❌ Concorrer com iFood

Possível integração futura.

---

# 10. Métricas de sucesso

## Principal

% pedidos concluídos sem humano

Meta:
≥ 50%

---

## Negócio

≥ 50 pedidos processados

≥ 1 cliente disposto a continuar usando

---

## Produto

Tempo médio:
≤ 2 minutos

---

## Técnica

Resposta IA:
≤ 5 segundos

---

# 11. Arquitetura MVP

```text
WhatsApp
↓

Webhook

↓

API

↓

Agente IA

↓

Banco

↓

Resumo pedido
```

Princípios:

* simples
* baixo custo
* rápida validação

---

# 12. Hipóteses

Se automatizarmos atendimento via WhatsApp:

→ empresas reduzem esforço operacional

→ clientes concluem mais pedidos

→ existe disposição para pagamento recorrente

---

# 13. Perguntas abertas

1. Quem será o primeiro cliente piloto?

2. Como o pedido será entregue ao restaurante?

3. Como escalar atendimento humano?

4. O que define sucesso após 7 dias?

5. Qual modelo de cobrança futura?

---

# 14. Backlog

## V0 — Prova de conceito

* WhatsApp
* Atendimento
* Pedido
* Confirmação

---

## V1 — MVP

* Catálogo
* Histórico
* Métricas

---

## V2 — Produto

* Integrações
* Analytics
* Multiempresa

---

# 15. Critério de encerramento do MVP

Consideraremos o MVP validado quando:

* 1 cliente utilizar por mais de 7 dias
* ≥ 50% dos pedidos ocorrerem sem humano
* houver intenção real de pagamento
* o fluxo funcionar sem operação manual constante

---

**Projeto Falange — “Automatizar o operacional sem perder o lado humano do atendimento.”**
