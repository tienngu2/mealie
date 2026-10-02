# CI pipeline

Upstream CI already runs the equivalent of `task validate` on pull requests (`.github/workflows/`):

| Local step | CI workflow |
|---|---|
| ruff, mypy, pytest | `test-backend.yml` ("Backend Lint and Test"): matrix of SQLite and PostgreSQL, with an LDAP service container |
| ESLint, vitest | `test-frontend.yml` ("Frontend Lint and Test"): Node 24 |
| security scanning | `codeql.yml`, `partial-trivy-container-scanning.yml` |
| weekly maintenance (not a check) | `scheduled-checks.yml` runs Mondays 07:00 and opens update PRs |
| PR title format | `pull-request-lint.yml`, `semantic.yml` |
| end-to-end | `e2e.yml` (Playwright against a Docker image) |

Differences to keep in mind:

- CI also tests PostgreSQL and LDAP; `task validate` locally uses SQLite and skips 9 LDAP tests (plus 7 long-running parser/scraper tests that are skipped everywhere by default).
- `task security` (bandit, pip-audit, pnpm audit, Semgrep) has no CI twin; CodeQL and Trivy cover similar ground.
- Workflows install from the lockfile (`UV_FROZEN=1`).
- No new workflow was added by the harness: duplicating upstream's jobs would only add noise. If the checks diverge, update this table.

## Not wired (by decision)

- **Dependabot:** not added. This repo already uses Renovate (`renovate.json`); both would open duplicate update PRs.
- **APM drift check:** not added. It needs a token with access to the private `cisco-genai` organization (`apm install` fetches from it), which a personal fork cannot supply without a secret. Until then run `apm install` locally and check `git status -- .agents .claude .github/skills apm.lock.yaml` for drift.
- **`task security` in CI:** CodeQL and Trivy cover similar ground; the baseline is in [tech debt](../tech-debt.md).
