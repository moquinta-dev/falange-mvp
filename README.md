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
