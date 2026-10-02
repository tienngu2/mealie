# Task usage

Mealie uses [Task](https://taskfile.dev/) (`Taskfile.yml`) as the single command surface. Prefer `task` over raw tool invocations.

| Task | What it does |
|---|---|
| `task validate` | **Enforced** full check: Node guard, ruff format check, ruff lint, mypy, pytest, ESLint, vitest (once). Run before every commit. |
| `task security` | **Report-only** scans: bandit, pip-audit, `pnpm audit`, Semgrep. Always exits 0; read the output. |
| `task py` / `task ui` | start backend / frontend |
| `task py:test -- -k name` | pytest (parallel, `-n auto --dist loadfile`) |
| `task py:format:check` | formatting check that does not rewrite files |
| `task py:format` | ruff format (**rewrites files**; part of upstream `py:check`) |
| `task py:lint` / `task py:mypy` | ruff check / mypy |
| `task ui:lint` | ESLint with `--max-warnings=0` |
| `task ui:test:ci` | vitest once. `task ui:test` is watch mode. |
| `task dev:generate` | code generation (required after schema changes) |
| `task py:migrate -- "msg"` | create an Alembic migration |
| `task dev:clean` | **deletes all dev data** |

`validate:node`, `py:format:check`, `ui:test:ci`, `validate`, and `security` were added by the harness; everything else is upstream.
