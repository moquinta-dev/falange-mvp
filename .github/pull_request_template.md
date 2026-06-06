## Objetivo

Descreva a mudanca e o motivo.

## Tipo de branch

- [ ] `feature/*` para nova funcionalidade contra `develop`
- [ ] `bugfix/*` para correcao contra `develop` ou `release/*`
- [ ] `chore/*` ou `chore-*` para governanca, automacao e manutencao contra `develop`
- [ ] `release/*` para estabilizacao de RC contra `main`
- [ ] `hotfix/*` para correcao urgente contra `main`

## Checklist

- [ ] Testes locais executados
- [ ] CI obrigatoria passando
- [ ] Sem secrets, tokens ou dados sensiveis no diff
- [ ] Impacto de migracao/configuracao documentado
- [ ] Para RC: branch no formato `release/vMAJOR.MINOR.PATCH-rc.N`
