# Contributing

Upstream's contributor guide is the baseline: `docs/docs/contributors/` (code contributions, dev server, database changes). This file is the working path for a change in this repository, for people and for AI agents. [AGENTS.md](AGENTS.md) holds the rules agents must follow.

## 1. Set up

Prerequisites: `uv`, Node 22 (via `mise`), `yarn` 1 (via corepack) and `task`. Full steps, including a preflight check that the installed frontend matches the lockfile: [first-time setup](docs/agents/dev-environment/first-time-setup.md).

```bash
unset VIRTUAL_ENV                  # only if a parent folder has a .venv
mise exec node@22 -- task setup    # uv sync and yarn install
task py                            # backend  http://localhost:9000
mise exec node@22 -- task ui       # frontend http://localhost:3000
```

A fresh database shows the default login on the login page (`changeme@example.com` / `MyPassword`). More in [running the app](docs/agents/dev-environment/running-the-app.md).

## 2. Branch

Work on one branch per change, named after the OpenSpec change (`feat/<change-name>`, `fix/...`, `docs/...`). Do not commit to the base branch directly.

## 3. Specify

Non-trivial changes start as an OpenSpec change in `openspec/changes/<name>/` (proposal, spec deltas, design, tasks). Small fixes can skip this step.

| Step | Claude Code | Cursor and GitHub Copilot | Codex |
|---|---|---|---|
| Explore or propose | `/opsx:explore`, `/opsx:propose` | `/opsx-explore`, `/opsx-propose` | `$openspec-explore`, `$openspec-propose` |
| Implement | `/opsx:apply` | `/opsx-apply` | `$openspec-apply-change` |
| Verify | `/opsx:verify` | `/opsx-verify` | `$openspec-verify-change` |
| Archive | `/opsx:archive` | `/opsx-archive` | `$openspec-archive-change` |

Project context and per-artifact rules live in `openspec/config.yaml`. Check a change with `openspec validate <name> --strict`.

## 4. Implement

- Follow the rules in [AGENTS.md](AGENTS.md): generated files, `en-US` only, layering, and group and household scoping.
- After changing a Pydantic schema run `task dev:generate`.
- Add tests with the change: pytest for the backend (a new data endpoint also needs an isolation test), Vitest next to new composables.

## 5. Validate

`task validate` must exit 0 before every commit. It takes about 9 minutes, so run it detached and read the log. UI changes also need a browser check on the running app; note what you checked in the change's tasks. When touching dependencies, raw SQL, `v-html` or auth, run `task security` and add no new findings. Details: [local validation](docs/agents/validation/local-validation-workflow.md), [testing strategy](docs/agents/validation/testing-strategy.md).

## 6. Commit and review

- Commit and PR titles use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `dev:`). CI checks the PR title in `.github/workflows/pull-request-lint.yml`.
- The PR description follows `.github/pull_request_template.md`: what and why, tests added, and the validation results.
- Reviewers check: layering, group and household scoping, type hints, generated files untouched, `en-US` only, and an Alembic migration for schema changes (tested on SQLite and PostgreSQL).
- Once a change is done, archive it (`/opsx-archive`) so `openspec/specs/` reflects the new behaviour.

## Remotes

`origin` is upstream (`mealie-recipes/mealie`). Do not push or open pull requests against it. To publish work, add your own fork as another remote and push there only when asked.

## Docs map

[Workflow overview](docs/agents/workflow-overview.md), [architecture](docs/agents/architecture/overview.md), [coding standards](docs/agents/conventions/coding-standards.md), [common issues](docs/agents/dev-environment/common-issues.md), [tech debt](docs/agents/tech-debt.md).
