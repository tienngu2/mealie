# Contributing to this Mealie fork

Upstream's contributor guide is the baseline: `docs/docs/contributors/` (code contributions, dev server, database changes). This file covers the agent-assisted workflow added in this fork.

## Workflow

1. **Set up:** [first-time setup](docs/agents/dev-environment/first-time-setup.md), then [run the app](docs/agents/dev-environment/running-the-app.md).
2. **Specify:** non-trivial changes use OpenSpec (`/opsx-propose`, `/opsx-apply`, `/opsx-verify`, `/opsx-archive`). Specs and change history live in `openspec/`; project context in `openspec/config.yaml`.
3. **Implement** following `AGENTS.md` (architecture, generated files, translations).
4. **Validate:** `task validate` must exit 0 before every commit. It is enforced. For UI changes, also check the running app in a browser. See [local validation](docs/agents/validation/local-validation-workflow.md).
5. **Security:** run `task security` when touching dependencies, raw SQL, `v-html`, or auth; add no new findings ([security](docs/agents/security/security.md)).
6. **Commit** with Conventional Commits.

## Docs map

[Workflow overview](docs/agents/workflow-overview.md), [architecture](docs/agents/architecture/overview.md), [conventions](docs/agents/conventions/coding-standards.md), [common issues](docs/agents/dev-environment/common-issues.md), [tech debt](docs/agents/tech-debt.md).

## Remotes

`origin` is the personal fork (`tienngu2/mealie`). Do not push to or open PRs against the upstream project unless intended.
