## 1. Backend rules

- [x] 1.1 Add the quality-report schemas and the six rule codes. Verified: `mypy mealie` passes (415 files).
- [x] 1.2 Implement the pure rule assessment and the report (ordering, code filter, pagination, full summary) over small input dataclasses.
- [x] 1.3 Cover every rule and boundary in unit tests. Verified: 36 tests pass.

## 2. Backend endpoint

- [x] 2.1 Add `RepositoryRecipes.get_quality_inputs()` (three narrow, scoped queries) and `GET /quality-report`, declared before `/{slug}`, with repeatable `code`, `page` and `perPage` (1-200).
- [x] 2.2 Add the generated artifacts: schema exports, TypeScript types and the pytest route helper. They were produced by `task dev:generate` in an earlier attempt on the same base commit (with `json2ts` installed temporarily) and carried over without the generator's unrelated reordering; `json2ts` is not declared in this repo (see tech debt).
- [x] 2.3 Cover authentication, empty and flagged libraries, filtering, pagination, invalid values, route precedence and read-only behavior in integration tests. Verified: 15 tests pass.
- [x] 2.4 Verify isolation across households in one group and across groups, in the same integration module (the multitenant harness is CRUD-oriented and does not fit a read-only report).

## 3. Frontend

- [x] 3.1 Add the typed `getQualityReport` client method.
- [x] 3.2 Add the composable with Vitest coverage. Verified: 13 new tests, 84 total.
- [x] 3.3 Add the page with issue chips, flagged recipes, loading, empty, no-match and error states.
- [x] 3.4 Add the sidebar entry and `en-US` strings only.

## 4. Verification and archive

- [x] 4.1 Seed a library through the real API (one complete recipe and five that each trigger specific rules). Verified: the report lists exactly the five flagged recipes, in the expected order, with the expected issues and summary counts.
- [x] 4.2 Browser-check on the running Nuxt 3 app: chips and counts, filter on and off, a two-chip filter, clear filters, opening a recipe, the error state with Retry, all-clear, and no-matches. The header image area is blank in the embedded browser on existing pages too (Recipe Finder, Cookbooks), although the SVG itself is served.
- [x] 4.3 Measure response time and memory for a library of about 500 recipes. Verified with 500 API-created recipes (10 ingredients and 8 steps each): the report took a median of 40 ms (maximum 152 ms on the first, cold call), the serving worker's memory stayed flat at about 316 MB, and the temporary recipes were removed afterwards.
- [x] 4.4 Run `task validate` and `task security`; compare the security findings with `docs/agents/tech-debt.md`. Verified: `task validate` exits 0 (1,408 backend tests passed, 18 skipped; 84 frontend tests; ruff, mypy and ESLint clean); `task security` counts are identical to the baseline (421 yarn advisories, 43 bandit issues, 94 Semgrep findings) with none in the new files.
- [x] 4.5 Update the agent docs, verify the change against its spec, archive it, and confirm `openspec list` shows no active change. Verified: every requirement and scenario maps to code and a test or a browser check, and the design decisions match the implementation.
