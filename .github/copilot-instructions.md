# Copilot instructions for Mealie

Read `AGENTS.md` first: it holds the architecture, generated-file rules, and the validation workflow.

- Definition of done: `task validate` exits 0 (enforced). `task security` is report-only and must not add findings.
- Use Node 24 for anything frontend (`mise exec node@24 -- <cmd>`); `unset VIRTUAL_ENV` before `uv`/`task`.
- Never run `task ui:test` (watch mode); use `task ui:test:ci`.
- Never hand-edit `frontend/app/lib/api/types/` or `mealie/schema/*/__init__.py`; run `task dev:generate`.
- Only edit `en-US` locale files.
- Non-trivial changes go through OpenSpec (`/opsx-propose`, `/opsx-apply`, `/opsx-verify`, `/opsx-archive`).
- Agent docs: `docs/agents/` (start with `workflow-overview.md`, `dev-environment/common-issues.md`).
- Commit and PR titles use Conventional Commits.
