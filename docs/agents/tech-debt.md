# Tech debt

Found while setting up the harness (2026-10-02). Logged here, not fixed inline. Most items are **upstream** and not ours to fix within a feature change.

| # | Item | Where | Why it matters | Suggested fix |
|---|---|---|---|---|
| 1 | Python dependency vulnerabilities | `nltk 3.10.3` (PYSEC-2026-3740), `oauthlib 3.3.1` (PYSEC-2026-4114, fixed in 4.0.0) | pip-audit findings | Upgrade through Renovate or an upstream PR |
| 2 | Frontend dependency vulnerability | `node-forge` (high, GHSA-86w9-cpqp-85rv), transitive via Nuxt/nitropack dev tooling | `pnpm audit --prod` finding | Wait for Nuxt/nitropack update or override |
| 3 | Bandit baseline | `mealie/`: 42 findings (0 high, 28 medium, 14 low; most low confidence) | Report-only noise hides new findings | Triage and suppress known false positives with justification |
| 4 | Bandit cannot parse 9 files | includes `core/security/providers/ldap_provider.py`, `pkgs/safehttp/fetch.py`, a 2026-09-24 Alembic revision | Those files are not scanned | Track a bandit release with Python 3.14 syntax support |
| 5 | Semgrep baseline | 117 findings: 61 mutable GitHub Action tags, 25 `avoid-sqlalchemy-text`, 8 `avoid-v-html`, 5 `direct-use-of-jinja2`, 4 non-literal regexps, 3 unsafe format strings, 2 `run-shell-injection`, 2 logger credential disclosure | Mostly upstream CI config and ORM raw-SQL use | Pin actions to SHAs; review `text()` and `v-html` usages |
| 6 | Security scans are not enforced | `task security` | Findings never fail | Enforce after items 1-5 are triaged |
| 7 | `ui:test` is watch mode | `Taskfile.yml` | Agents hang on it | Use `ui:test:ci` (added); consider changing upstream |
| 8 | `py:check` rewrites files | `Taskfile.yml` (`py:format`) | A "check" that mutates the tree | Use `py:format:check` (added) |
| 9 | Node not pinned upstream | repo root | Node 26 breaks 6 tests | `.node-version` and `mise.toml` added in this fork |
| 10 | Irrelevant bundled skill | `.agents/skills/accelint-ts-best-practices` | TypeScript guidance in a mostly Python/Vue repo | Remove from the stack package install if unwanted |
| 11 | pnpm version drift | `frontend/package.json` pins 11.23.0 | Local pnpm 12.x warns | Install the pinned version |
