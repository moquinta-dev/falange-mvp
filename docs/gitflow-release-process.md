# GitFlow e Release Candidates

Este repositorio usa `main` como branch protegida de producao, `develop` como integracao e branches temporarias para trabalho.

## Branches

- `main`: historico estavel. Recebe merge somente por pull request vindo de `release/*` ou `hotfix/*`.
- `develop`: integra trabalho aprovado antes de estabilizacao.
- `feature/*`: novas funcionalidades contra `develop`.
- `bugfix/*`: correcoes contra `develop` ou `release/*`.
- `release/vMAJOR.MINOR.PATCH-rc.N`: estabilizacao de release candidate.
- `hotfix/*`: correcao urgente baseada em `main`.

## Fluxo de RC

1. Crie ou atualize `develop` com as funcionalidades aprovadas.
2. Abra `release/vMAJOR.MINOR.PATCH-rc.N` a partir de `develop`.
3. Envie a branch `release/*` para o GitHub.
4. O workflow `Release Candidate` valida testes, Dockerfile, compose e gera uma prerelease `vMAJOR.MINOR.PATCH-rc.N`.
5. Corrija bugs apenas com PRs `bugfix/*` para a branch `release/*`.
6. Quando a RC for aprovada, abra PR de `release/*` para `main`.
7. Apos merge em `main`, crie a release final a partir do commit mergeado e sincronize `develop` com `main`.

## Protecao da main

A branch `main` deve exigir:

- Pull request antes de merge.
- Pelo menos 1 aprovacao.
- Reviews obsoletos descartados quando houver novo push.
- Aprovacao do ultimo push por outra pessoa.
- Resolucao de conversas antes do merge.
- Status check `required-ci` atualizado com a base.
- Historico linear.
- Administradores sujeitos as mesmas regras.
- Force push e delecao bloqueados.

A politica auditavel efetiva esta em `.github/ruleset-main.json`. Ela foi aplicada no GitHub como Ruleset `protect-main-gitflow`.

Para reaplicar ou recriar a Ruleset:

```bash
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/falange-labs/falange-mvp/rulesets \
  --input .github/ruleset-main.json
```

Se a instalacao precisar usar a Branch Protection classica em vez de Rulesets, ha uma configuracao equivalente em `.github/branch-protection-main.json`:

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/falange-labs/falange-mvp/branches/main/protection \
  --input .github/branch-protection-main.json
```
