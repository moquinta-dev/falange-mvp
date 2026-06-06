# Deploy na VPS Hostinger

Este pipeline publica a imagem Docker no GitHub Container Registry e atualiza a VPS por SSH usando Docker Compose.

## Pre-requisitos na VPS

- Ubuntu na VPS.
- DNS do dominio ou subdominio apontando para o IP publico da VPS.
- Portas `80` e `443` liberadas no firewall.
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

## Secrets no GitHub

Crie um environment chamado `production` e cadastre:

```text
VPS_HOST          IP ou FQDN da VPS
VPS_USER          usuario SSH de deploy
VPS_SSH_KEY       chave privada SSH
VPS_APP_DOMAIN    dominio publico da API, sem https://
```

Opcionais:

```text
VPS_PORT          porta SSH, padrao 22
VPS_APP_DIR       diretorio remoto, padrao /opt/falange-mvp
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
4. O workflow copia `deploy/hostinger/docker-compose.yml` e `deploy/hostinger/Caddyfile` para a VPS.
5. A VPS faz pull da imagem e executa `docker compose up -d`.
6. O pipeline valida `https://<VPS_APP_DOMAIN>/health`.

## Rollback manual

Na VPS, edite `.env.deploy` para apontar `FALANGE_IMAGE` para uma tag anterior e suba novamente:

```bash
cd /opt/falange-mvp
docker compose --env-file .env.deploy -f docker-compose.yml pull
docker compose --env-file .env.deploy -f docker-compose.yml up -d
```
