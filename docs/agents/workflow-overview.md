# Agent workflow overview

How to change Mealie with AI agents in this repository. Upstream contributor docs live in `docs/docs/contributors/`; this tree covers the agent-facing harness only (it is not part of the MkDocs site).

## The loop

1. **Specify** non-trivial changes with OpenSpec: `/opsx-propose` (or `/opsx-explore` first) creates `openspec/changes/<name>/` with proposal, specs, design, and tasks. Small fixes can skip this.
2. **Implement** with `/opsx-apply`, following the task list. Follow `AGENTS.md` (architecture, generated files, translations).
3. **Validate** with `task validate` (enforced). For UI work, also check the running app in a browser (http://localhost:3000) and report what was checked.
4. **Verify and archive** with `/opsx-verify` and `/opsx-archive`.
5. **Capture discoveries**: new gotchas go to [common issues](dev-environment/common-issues.md), new debt to [tech debt](tech-debt.md).

## Where things are

| Need | Location |
|---|---|
| Architecture and layering rules | `AGENTS.md`, [architecture](architecture/overview.md) |
| Run the app | [running the app](dev-environment/running-the-app.md) |
| Checks before a commit | [local validation](validation/local-validation-workflow.md) |
| Specs and change history | `openspec/` |
| Installed agent skills | [APM management](conventions/apm-management.md) |
| Known problems | [common issues](dev-environment/common-issues.md), [tech debt](tech-debt.md) |

## Rules that are easy to get wrong

- Never edit generated files (`frontend/lib/api/types/`, `mealie/schema/*/__init__.py`); run `task dev:generate`.
- Only edit `en-US` locale files; other locales are managed by Crowdin.
- Frontend commands need Node 22. Use `mise exec node@22 -- <cmd>` if your default Node differs.
- `task ui:test` is watch mode and never exits. Use `task ui:test:ci`.
