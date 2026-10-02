# Local validation workflow

One command: **`task validate`**. It is **enforced**: any failure exits non-zero. Run it before every commit and before declaring work done.

Steps, in order:

| # | Check | Command | Passes when |
|---|---|---|---|
| 1 | Node version | `task validate:node` | Node major is 24 |
| 2 | Format | `uv run ruff format --check .` | no file would be reformatted |
| 3 | Lint | `uv run ruff check mealie` | no violations |
| 4 | Types | `uv run mypy mealie` | no issues |
| 5 | Backend tests | `uv run pytest -n auto --dist loadfile` | all pass (baseline: 3,179 passed, 16 skipped) |
| 6 | Frontend lint | `pnpm lint --max-warnings=0` | zero warnings |
| 7 | Frontend tests | `pnpm test:ci` | all pass (baseline: 518) |

Baseline recorded on 2026-10-02 against upstream `mealie-next`: all green.

## Security scans (`task security`, report-only)

Not part of `validate` because upstream already has findings that are not ours to fix inside a feature change. They are logged in [tech debt](../tech-debt.md). Run `task security` when touching dependencies, raw SQL, `v-html`, regexes, or auth code, and make sure you add **no new** findings.

## Targeted runs while iterating

```bash
task py:test -- tests/unit_tests/test_security.py
cd frontend && pnpm exec vitest run app/composables
```

Run the full `task validate` once at the end.

## Browser check (UI changes)

Start both servers ([running the app](../dev-environment/running-the-app.md)), exercise the changed screen in a browser, and note what was checked in the change's tasks.
