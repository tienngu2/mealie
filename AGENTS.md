# Mealie: guide for AI agents

Self-hosted recipe manager and meal planner. Backend: FastAPI + SQLAlchemy (Python 3.12, `uv`). Frontend: Nuxt 3 + Vue 3 + TypeScript (Node 22, `yarn`). SQLite by default, PostgreSQL supported. This file is a routing map; the detail lives in `docs/agents/`.

## Repository map

```text
mealie/           backend: routes/ (HTTP), services/ (logic), repos/ (data access), db/models/, schema/ (Pydantic), alembic/
frontend/         Nuxt 3 app: pages/, components/, composables/, lib/api/ (types/ is generated), lang/, tests/
tests/            pytest: unit_tests/, integration_tests/, multitenant_tests/, e2e/ (Playwright, not part of validate)
dev/              code generation (dev/code-generation/) and local dev data (dev/data/)
docs/docs/        upstream MkDocs site (user and contributor docs)
docs/agents/      agent-facing docs, start at workflow-overview.md
openspec/         specs/ and changes/ for spec-driven development
Taskfile.yml      the command surface
.agents/ .claude/ .cursor/ .github/skills/ .github/prompts/   installed by APM and OpenSpec: never edit by hand
```

## Commands

Run `task` from the repository root. Use `unset VIRTUAL_ENV` if a parent folder has a `.venv`, and Node 22 (`mise exec node@22 -- task ...`).

| Command | Purpose |
|---|---|
| `task validate` | **Enforced.** Run before every commit and before saying "done". Node guard, ruff format, ruff, mypy, `nuxt prepare`, ESLint, Vitest, pytest. About 9 minutes: run it detached and read the log |
| `task security` | Report-only: bandit, `yarn audit`, Semgrep. A change must not add findings |
| `task py` / `task ui` | Dev servers: backend on :9000, frontend on :3000 |
| `task dev:generate` | Required after any Pydantic schema change |
| `task py:test -- <path>` | Focused pytest run |
| `task ui:test:ci` | Vitest once (`task ui:test` is watch mode and never exits) |
| `task py:migrate -- "message"` | New Alembic migration |

## Rules that are easy to get wrong

1. Never hand-edit generated files: `frontend/lib/api/types/` and `mealie/schema/*/__init__.py`. Run `task dev:generate`.
2. Layering is controller (HTTP only), then service (logic), then repository (data). Get repositories through `get_repositories`; they scope every query to the caller's group and household. A new data endpoint needs a test proving that other households and groups are excluded.
3. Only edit the `en-US` locale. All other locales belong to Crowdin.
4. Use `uv run` for Python, never bare `python` or `pip`. Type hints are required (mypy runs over `mealie/`).
5. Frontend components are named by role (`Domain`, `Base*` primitives, `App*` or `The*` layout). API calls go through `useUserApi()`; shared logic lives in `composables/`.
6. Run one pytest at a time: the tests share one SQLite file in `tests/.temp`. Run long jobs and dev servers in the background with output redirected to a log file.
7. Do not commit or push unless asked. Commit and PR titles use Conventional Commits.
8. Ask before destructive commands such as `task dev:clean` (deletes all dev data) or anything that rewrites git history.

## Spec-driven workflow (OpenSpec)

Non-trivial changes start as an OpenSpec change in `openspec/changes/<name>/` (proposal, spec deltas, design, tasks):

`/opsx-propose` (or `/opsx-explore` first), then `/opsx-apply`, `/opsx-verify`, `/opsx-archive`. Claude Code uses `/opsx:propose` and so on; Codex uses `$openspec-propose`. Project context and per-artifact rules are in `openspec/config.yaml`. Check a change with `openspec validate <name> --strict`. Every task list ends with "run `task validate`", and UI changes also need a browser check on http://localhost:3000.

## Where to look next

| Need | Doc |
|---|---|
| The workflow loop | [workflow overview](docs/agents/workflow-overview.md) |
| Set up, run, troubleshoot | [first-time setup](docs/agents/dev-environment/first-time-setup.md), [running the app](docs/agents/dev-environment/running-the-app.md), [common issues](docs/agents/dev-environment/common-issues.md), [environment variables](docs/agents/dev-environment/environment-variables.md) |
| Architecture and data model | [overview](docs/agents/architecture/overview.md), [data model](docs/agents/architecture/data-model.md) |
| Coding standards, Task usage, skills | [coding standards](docs/agents/conventions/coding-standards.md), [Task usage](docs/agents/conventions/task-usage.md), [APM management](docs/agents/conventions/apm-management.md) |
| Checks, CI, tests | [local validation](docs/agents/validation/local-validation-workflow.md), [CI pipeline](docs/agents/validation/ci-pipeline.md), [testing strategy](docs/agents/validation/testing-strategy.md) |
| Security rules and scanners | [security](docs/agents/security/security.md) |
| Deployment | [deployment overview](docs/agents/deployment/overview.md) |
| Known debt and security baseline | [tech debt](docs/agents/tech-debt.md) |

Code entry points: `mealie/routes/_base/base_controllers.py` (controller bases), `mealie/repos/repository_factory.py` (repositories), `frontend/lib/api/base/base-clients.ts` (API clients), `tests/conftest.py` (fixtures), `dev/code-generation/main.py` (generators).
