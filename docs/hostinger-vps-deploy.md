# Deploy na VPS Hostinger

Este pipeline publica a imagem Docker no GitHub Container Registry e atualiza a VPS por SSH usando Docker Compose.

## Pre-requisitos na VPS

- Ubuntu na VPS.
- DNS do dominio ou subdominio apontando para o IP publico da VPS.
- Traefik da Hostinger/Docker Manager publicado como proxy reverso nas portas `80` e `443`.
- Network Docker externa `traefik-proxy` compartilhada com o Traefik da Hostinger.
- Docker Engine com plugin `docker compose`.
- Usuario de deploy com permissao para executar Docker.

Instalacao base sugerida:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
mkdir -p /opt/falange-mvp/data
```

Depois, saia e entre novamente no SSH para aplicar o grupo `docker`.

### Bootstrap com Ansible

O setup inicial tambem pode ser executado pelo playbook em
`deploy/hostinger/ansible/setup-vps.yml`.

1. Copie o inventory de exemplo e ajuste host, usuario e porta SSH:

```bash
cp deploy/hostinger/ansible/inventory.example.ini deploy/hostinger/ansible/inventory.ini
nano deploy/hostinger/ansible/inventory.ini
```

2. Execute o bootstrap:

```bash
cd deploy/hostinger/ansible
ansible-playbook -i inventory.ini setup-vps.yml
```

Por padrao, o playbook instala `ca-certificates`, `curl`, Docker Engine com
plugin `docker compose`, adiciona o usuario de deploy ao grupo `docker` e cria
`/opt/falange-mvp/data`.

O firewall `ufw` nao e habilitado automaticamente para evitar perda de acesso
SSH em VPS recem-criadas. Para liberar SSH, HTTP e HTTPS pelo playbook, defina
`configure_ufw=true` e confirme `ssh_port` no inventory antes da execucao.

### Pipeline de infraestrutura

O caminho padrao para mudancas de infraestrutura e o workflow
`Infra Hostinger VPS`, definido em `.github/workflows/infra-hostinger-vps.yml`.

A stack atual do MVP e `hostinger`, representada pelo diretorio
`deploy/hostinger/`.

O workflow executa validacao automaticamente quando houver mudanca em
`deploy/hostinger/**` ou no proprio workflow nas seguintes situacoes:

- pull request para `main` ou `develop`;
- push em branches `feature/hostinger`, `feature/hostinger-*` ou
  `feature/hostinger/**`.

A aplicacao real da infraestrutura na VPS ocorre apenas por execucao manual
via `workflow_dispatch`, escolhendo:

- `stack=hostinger`;
- `check_mode=true` para dry-run;
- `check_mode=false` para aplicar mudancas;
- `configure_ufw=true` apenas quando a porta SSH estiver confirmada.

Use o environment `production` para proteger execucoes reais com aprovacao
manual. Os secrets necessarios para o workflow de infraestrutura sao:

```text
VPS_HOST          IP ou FQDN da VPS
VPS_USER          usuario SSH de deploy
VPS_SSH_KEY       chave privada SSH
```

Opcionais:

```text
VPS_PORT          porta SSH, padrao 22
VPS_APP_DIR       diretorio remoto, padrao /opt/falange-mvp
```

## Secrets no GitHub

Crie um environment chamado `production` e cadastre:

```text
VPS_HOST          IP ou FQDN da VPS
VPS_USER          usuario SSH de deploy
VPS_SSH_KEY       chave privada SSH
VPS_APP_DOMAIN    dominio publico da API, sem https://
WHATSAPP_VERIFY_TOKEN     token forte configurado tambem no app da Meta
WHATSAPP_ACCESS_TOKEN     access token da WhatsApp Cloud API
WHATSAPP_PHONE_NUMBER_ID  phone number ID do WhatsApp Business
META_APP_SECRET           app secret do aplicativo Meta
```

Opcionais:

```text
VPS_PORT          porta SSH, padrao 22
VPS_APP_DIR       diretorio remoto, padrao /opt/falange-mvp
META_GRAPH_API_VERSION    versao da Graph API, padrao v23.0
META_VALIDATE_SIGNATURE   true para exigir X-Hub-Signature-256, padrao false
```

## Arquivo .env da app na VPS

Na primeira execucao, o pipeline cria um `.env` minimo se ele nao existir. Para WhatsApp real, edite na VPS:

```bash
cd /opt/falange-mvp
nano .env
chmod 600 .env
```

Exemplo inicial:

```text
APP_NAME=falange-mvp
APP_ENV=production
APP_VERSION=0.1.0
APP_DEBUG=false
DATABASE_URL=sqlite:////data/falange.db
```

Quando a integracao Meta estiver pronta, incluir os secrets do provedor nesse mesmo arquivo, nunca no Git.

## Como funciona

1. Push em `main` ou execucao manual do workflow `Deploy Hostinger VPS`.
2. GitHub Actions roda testes.
3. GitHub Actions cria e publica a imagem `ghcr.io/<owner>/<repo>:<sha>`.
4. O workflow copia `deploy/hostinger/docker-compose.yml` para a VPS.
5. A VPS faz pull da imagem e executa `docker compose up -d`.
6. O pipeline valida `https://<VPS_APP_DOMAIN>/health`.

O endpoint publico do webhook WhatsApp fica em:

```text
https://<VPS_APP_DOMAIN>/webhook/whatsapp
```

## Roteamento com Traefik

Este deploy nao publica portas `80` ou `443` e nao inclui proxy reverso proprio.
O container `api` e conectado a network externa `traefik-proxy` e recebe labels
Traefik para:

- rotear `https://<VPS_APP_DOMAIN>` para a porta interna `8000`;
- emitir/renovar TLS via certresolver `letsencrypt` configurado no Traefik da Hostinger.

Antes do deploy, confirme na VPS que o projeto Traefik da Hostinger esta ativo e
conectado a network compartilhada. O workflow cria `traefik-proxy` se ela ainda
nao existir, mas o Traefik tambem precisa estar conectado a ela para rotear para
o container `api`:

```bash
docker network inspect traefik-proxy
```

Depois do deploy, valide:

```bash
curl -I "https://<VPS_APP_DOMAIN>/health"
```

## Rollback manual

Na VPS, edite `.env.deploy` para apontar `FALANGE_IMAGE` para uma tag anterior e suba novamente:

```bash
cd /opt/falange-mvp
docker compose --env-file .env.deploy -f docker-compose.yml pull
docker compose --env-file .env.deploy -f docker-compose.yml up -d
```
