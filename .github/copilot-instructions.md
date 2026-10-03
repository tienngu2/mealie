# Copilot instructions for Mealie

Read `AGENTS.md` first: it holds the repository map, the rules that are easy to get wrong, and the validation workflow.

- Definition of done: `task validate` exits 0 (enforced). `task security` is report-only and must not add findings.
- Use Node 22 for anything frontend (`mise exec node@22 -- <cmd>`); `unset VIRTUAL_ENV` before `uv` or `task`.
- Never run `task ui:test` (watch mode); use `task ui:test:ci`.
- Never hand-edit `frontend/lib/api/types/` or `mealie/schema/*/__init__.py`; run `task dev:generate`.
- Only edit `en-US` locale files.
- Non-trivial changes go through OpenSpec (`/opsx-propose`, `/opsx-apply`, `/opsx-verify`, `/opsx-archive`).
- Agent docs: `docs/agents/` (start with `workflow-overview.md` and `dev-environment/common-issues.md`).
- Do not commit or push unless asked. Commit and PR titles use Conventional Commits.
