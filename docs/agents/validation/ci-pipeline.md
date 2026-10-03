# CI pipeline

Upstream CI (`.github/workflows/`) already runs the equivalent of `task validate` on pull requests. `pull-requests.yml` ("PR CI") calls these reusable workflows:

| Local step | CI workflow |
|---|---|
| ruff format and lint, mypy, pytest | `test-backend.yml` ("Backend Lint and Test"): Python 3.12, matrix of SQLite and PostgreSQL, with an LDAP service container |
| `yarn nuxt prepare`, ESLint (`--max-warnings=0`), Vitest | `test-frontend.yml` ("Frontend Lint and Test"): Node 22, yarn |
| build | `build-package.yml` ("Build Python package") |
| security scanning | `codeql.yml`, `partial-trivy-container-scanning.yml` |
| PR title format | `pull-request-lint.yml` |
| end-to-end (not part of `task validate`) | `e2e.yml` (Playwright against a Docker image) |
| weekly maintenance (not a check) | `scheduled-checks.yml`, Mondays 07:00 |

Differences to keep in mind:

- CI also tests PostgreSQL and LDAP; `task validate` locally uses SQLite and skips the LDAP tests (plus the long-running parser and scraper tests that are skipped everywhere by default).
- `task validate` runs `yarn nuxt prepare` before linting, in the same order as CI.
- `task security` (bandit, `yarn audit`, Semgrep) has no CI twin; CodeQL and Trivy cover similar ground.
- No workflow was added by the harness: duplicating upstream's jobs would only add noise. If the checks diverge, update this table.

## Not wired (by decision)

- **Dependabot:** not added. This repository already uses Renovate (`renovate.json`); both would open duplicate update PRs.
- **APM drift check:** not added. `apm install` fetches skills from a private organization and needs a token that a personal clone cannot supply without a secret. Run `apm install` locally and check `git status -- .agents .claude .github/skills apm.lock.yaml` for drift.
- **`task security` in CI:** CodeQL and Trivy cover similar ground; the baseline is in [tech debt](../tech-debt.md).
