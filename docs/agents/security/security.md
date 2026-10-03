# Security

Mealie is multi-tenant (groups and households). The highest-impact mistakes are tenancy leaks and injection.

**Rules for changes**
- Always go through repositories obtained by `get_repositories`; they scope by group/household. Add a multitenant test for new data endpoints.
- Authenticate with `Depends(get_current_user)` or the `BaseUserController`/`BaseAdminController` bases; do not hand-roll auth.
- Avoid raw SQL (`sqlalchemy.text`); use the ORM or parameters.
- Avoid `v-html` with user-controlled data; recipe content is user input.
- Never log credentials or tokens; never commit secrets (`.env`, `.dev.env` are local).
- Do not add dependencies without a reason; upstream manages updates with Renovate (`renovate.json`).

**Scanners**
- `task security` (report-only): bandit, `yarn audit`, Semgrep (`brew install semgrep`).
- Upstream CI: CodeQL, Trivy container scanning, and Renovate dependency updates (`renovate.json`).
- Baseline (2026-10-03) is in [tech debt](../tech-debt.md); a change must not increase it.

Vulnerability reports: see `SECURITY.md`.
