# Tech debt and security baseline

Measured on 2026-10-03 at upstream commit `7fe358e` with no local changes. `task security` is report-only: a change must not make these numbers worse. Log new debt here instead of fixing unrelated things inline. Re-measured after the Recipe Quality change and again after the Recipe Comparison change: the counts below are identical and none of the findings are in the new files.

## Security baseline

| # | Scanner | Result | Detail |
|---|---|---|---|
| 1 | `uvx pip-audit` on the `uv.lock` export | 252 known vulnerabilities in 28 packages (142 unique advisories) | Most affected: `nltk` (67), `pillow` (37), `pyjwt` (19), `cryptography` (13), `authlib` (13), `python-multipart` (12). The lockfile is about ten months old; upstream updates dependencies through Renovate |
| 2 | `yarn audit --groups dependencies` | 421 advisories in 1,213 packages | 5 critical, 226 high, 162 moderate, 28 low |
| 3 | `bandit -r mealie` | 43 issues (1 high, 26 medium, 16 low), 0 files skipped | Mostly B608 hardcoded SQL expressions (22), B105 (5), B311 `random` (4), B101 `assert` (4), B113 requests without timeout (2), B110 (2), B104 (2), B501 (1) |
| 4 | `semgrep --config auto` | 94 findings (42 blocking) on 1,304 files | GitHub Actions mutable action tags (15), `avoid-sqlalchemy-text` (8), `avoid-v-html` (5), `direct-use-of-jinja2` (4), workflow shell injection (2), one each for disabled certificate validation, a credential-logging rule and others |

`task security` runs scans 2 to 4. Scan 1 is not part of the task yet; run it with `uv export --frozen --no-hashes --no-emit-project -o /tmp/reqs.txt && uvx pip-audit -r /tmp/reqs.txt --no-deps --disable-pip`.

## Tooling and test debt

| # | Item | Evidence | Suggested action |
|---|---|---|---|
| 5 | No Vue type checker | `nuxt typecheck` needs `vue-tsc` or Golar and neither is installed, so `task validate` checks frontend types only through ESLint and Vitest | Add `vue-tsc` as a dev dependency (changes `frontend/yarn.lock`) |
| 6 | `json2ts` is not declared | `task dev:generate` needs `json2ts` on `PATH` to write `frontend/lib/api/types/`; it is in neither `frontend/package.json` nor `node_modules` | Install `json-schema-to-typescript` for the run (see [common issues](dev-environment/common-issues.md)) or declare it as a dev dependency |
| 7 | Slow serial backend tests | No `pytest-xdist` at this commit; the full run takes about 9 minutes | Parallel runs would first need isolated SQLite files, because the tests share `tests/.temp` |
| 8 | Evening failures in `test_create_timeline_events.py` | The scheduler selects meal plans by local date; the tests create them with the UTC date | Worked around in the harness: `task validate` runs pytest with `TZ=UTC` (`task py:test:utc`). Proper fix: make the tests use the same date source as the scheduler |
| 9 | Node is not pinned upstream | Only CI sets Node 22 | `.node-version` and `mise.toml` were added by the harness |
