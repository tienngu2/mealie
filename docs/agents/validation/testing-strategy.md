# Testing strategy

**Backend (`tests/`, pytest):**
- `unit_tests/`: schemas, services, repositories, config, security, alembic chain, parser, code generation, migrations.
- `integration_tests/`: API tests through the `api_client` fixture, grouped by domain (admin, recipes, users, households, groups, explore, migrations, OpenAPI, SPA).
- `multitenant_tests/`: verify group/household isolation. Required thinking for any new endpoint.
- `e2e/`: Playwright, Docker based (not part of `task validate`).
- Fixtures in `tests/fixtures/`; generated route and data-path helpers come from `task dev:generate`.
- Slow or external tests are skipped by default (9 LDAP tests need a service container; 7 recipe parser and bulk scraper tests are long-running).

**Frontend (Vitest + jsdom, config in `frontend/vitest.config.js`):** `*.test.ts` files sit next to the code, in `frontend/composables/` and `frontend/lib/`; shared helpers are in `frontend/tests/utils.ts`. Runs once with `yarn test:ci`.

**Expectations for new work**
- New endpoint: integration test, plus group/household isolation coverage if it reads or writes scoped data. The recipe quality report keeps these read-only scope cases in its integration test module because the multitenant harness is CRUD-oriented.
- New composable or utility: a Vitest test next to it.
- New schema change: migration plus `tests/unit_tests/test_alembic.py` still green.
- UI change: a browser check on the running app, in addition to automated tests.
- No coverage threshold is enforced; coverage can be generated with `task py:coverage`.
