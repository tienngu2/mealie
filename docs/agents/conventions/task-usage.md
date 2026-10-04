# Task usage

Mealie uses [Task](https://taskfile.dev/) (`Taskfile.yml`) as the single command surface. Prefer `task` over raw tool invocations.

| Task | What it does |
|---|---|
| `task validate` | **Enforced** full check: Node guard, ruff format check, ruff lint, mypy, `nuxt prepare`, ESLint, vitest (once), then pytest in UTC. Run before every commit. |
| `task security` | **Report-only** scans: bandit, `yarn audit`, Semgrep. Always exits 0; read the output. |
| `task py` / `task ui` | start backend / frontend |
| `task py:test -- -k name` | pytest, serial (`-k` selects tests; extra arguments go after `--`) |
| `task py:test:utc -- -k name` | the same with `TZ=UTC`, as upstream CI runs it; `validate` uses this one |
| `task py:format:check` | formatting check that does not rewrite files |
| `task py:format` | ruff format (**rewrites files**; part of upstream `py:check`) |
| `task py:lint` / `task py:mypy` | ruff check / mypy |
| `task ui:prepare` | `nuxt prepare`: generates `.nuxt` and the ESLint config (CI does this before linting) |
| `task ui:lint` | ESLint with `--max-warnings=0` |
| `task ui:test:ci` | vitest once. `task ui:test` is watch mode. |
| `task dev:generate` | code generation (required after schema changes) |
| `task py:migrate -- "msg"` | create an Alembic migration |
| `task dev:clean` | **deletes all dev data** |

`validate:node`, `py:format:check`, `ui:prepare`, `ui:test:ci`, `py:test:utc`, `validate`, and `security` were added by the harness; everything else is upstream.
