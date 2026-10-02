# Common issues

Gotchas discovered while setting up and baselining this repository. Add new ones here.

| Symptom | Cause | Fix |
|---|---|---|
| 6 failures in `use-unit-system.test.ts`: `Cannot read properties of undefined (reading 'clear')` | Node 26 defines an experimental global `localStorage` that shadows jsdom's | Use Node 24 (`mise exec node@24 -- task validate`). `task validate:node` fails early with this hint. |
| `pnpm test` / `task ui:test` never exits | `vitest` starts in watch mode | Use `task ui:test:ci` (`vitest --watch=false`) |
| `warning: VIRTUAL_ENV=... does not match the project environment` and pytest says `unrecognized arguments: -n --dist` | A `VIRTUAL_ENV` from a parent folder leaks into `uv` | `unset VIRTUAL_ENV` before running `task`/`uv` |
| `ruff format --check` flags files in `.agents/` or `.claude/` | APM-installed third-party skills contain Python and Markdown | They are excluded in `pyproject.toml` (`[tool.ruff] exclude`); keep new managed folders in that list |
| `[WARN] This project is configured to use 11.23.0 of pnpm` | Newer local pnpm than `packageManager` pins | Harmless; install the pinned version to silence it |
| `semgrep --config auto` fails with "Cannot create auto config when metrics are off" | `--metrics=off` is incompatible with `--config auto` | Do not pass `--metrics=off`, or use an explicit config |
| `bandit` skips 9 files with "syntax error while parsing AST" | The installed bandit parser predates some Python 3.14 syntax | Known limitation; see [tech debt](../tech-debt.md) |
| `timeout` command not found | macOS has no GNU `timeout` | Run without it, or `brew install coreutils` |
| Vitest logs `Logout API call failed: Error: Unauthorized` / `Woe, exception be upon ye` | Expected output from tests that exercise error paths | Not a failure; check the summary line |
