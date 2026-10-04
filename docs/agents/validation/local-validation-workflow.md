# Local validation workflow

One command: **`task validate`**. It is **enforced**: any failure exits non-zero. Run it before every commit and before declaring work done.

Steps, in order:

| # | Check | Command | Passes when |
|---|---|---|---|
| 1 | Node version | `task validate:node` | Node major is 22 |
| 2 | Format | `uv run ruff format --check .` | no file would be reformatted |
| 3 | Lint | `uv run ruff check mealie` | no violations |
| 4 | Types | `uv run mypy mealie` | no issues |
| 5 | Nuxt prepare | `yarn nuxt prepare` | `.nuxt` and the ESLint config are generated (same as CI) |
| 6 | Frontend lint | `yarn lint --max-warnings=0` | no errors or warnings |
| 7 | Frontend tests | `yarn test:ci` | all pass (currently 112; upstream baseline 71) |
| 8 | Backend tests | `TZ=UTC uv run pytest` (`task py:test:utc`) | all pass (currently 1,408 passed, 18 skipped; upstream baseline 1,357 passed; serial and about 9 minutes, so it runs last) |

Baseline recorded on 2026-10-03 against upstream commit `7fe358e` with no local changes: all green (ruff clean on 561 files, mypy clean on 413 files, ESLint clean, 71 frontend tests, 1,357 backend tests). After the Recipe Quality change: 84 frontend tests and 1,408 backend tests (the 1,357 plus 51 new), all green. The Recipe Comparison change is frontend only and added 28 frontend tests (112 in total) and no backend tests.

## Security scans (`task security`, report-only)

Not part of `validate` because upstream already has findings that are not ours to fix inside a feature change. They are logged in [tech debt](../tech-debt.md). Run `task security` when touching dependencies, raw SQL, `v-html`, regexes, or auth code, and make sure you add **no new** findings.

## Targeted runs while iterating

```bash
task py:test -- tests/unit_tests/test_security.py
cd frontend && yarn vitest run composables
```

Run the full `task validate` once at the end.

## Browser check (UI changes)

Start both servers ([running the app](../dev-environment/running-the-app.md)), exercise the changed screen in a browser, and note what was checked in the change's tasks.
