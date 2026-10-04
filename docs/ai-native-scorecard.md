# AI-Native Scorecard

## Repository

- **Name:** mealie
- **GitHub org:** mealie-recipes
- **Date assessed:** 2026-10-03
- **Assessed by (model):** Claude Sonnet 5.5 (GitHub Copilot in VS Code)
- **Detected stack:** Python 3.12 (FastAPI, SQLAlchemy, Alembic; uv) and TypeScript (Nuxt 3, Vue 3, Vuetify; Node 22, yarn 1); SQLite and PostgreSQL; Task as the command runner
- **Spec-Driven Development system:** OpenSpec (`openspec/`; 2 archived changes, 2 main specs)
- **AI IDE / agent surface:** Vendor-neutral (`AGENTS.md`, `.agents/skills/`), Claude Code, Cursor, VS Code/GitHub Copilot

## Summary

- **Overall score:** 3.41 / 4.00
- **Tier:** Established
- **Agentic legibility sub-score:** 3.08 / 4.00
- **Agentic legibility tier:** Established
- **Sub-metrics below 3:** 5 of 38 (MCP servers 0; Type checking 2; Context proximity 2; Business logic explainability 2; Drift detection 2)

## Tier Definitions

| Composite Score | Tier | Description |
| --- | --- | --- |
| 0.0 - 0.9 | **Unaware** | No AI-native infrastructure exists. Agents would be flying blind. |
| 1.0 - 1.9 | **Nascent** | Fragments exist. AI use is opportunistic, not systematic. |
| 2.0 - 2.9 | **Structured** | Core primitives are in place. Agents can operate with some friction. |
| 3.0 - 3.5 | **Established** | AI workflow is reliable and actively used. Agents can operate effectively. |
| 3.6 - 4.0 | **Exemplary** | Model AI-native repo. Full infrastructure, actively maintained, intentionally curated. |

## Category Scores

| Category | Weight | Score (0-4) | Tier |
| --- | --- | --- | --- |
| Spec-Driven Development | 20% | 4.00 | Exemplary |
| Deterministic Checks | 25% | 3.14 | Established |
| AI Tooling & Skills | 15% | 3.33 | Established |
| Documentation Tree | 15% | 4.00 | Exemplary |
| AI IDE Configuration | 10% | 2.67 | Structured |
| Agentic Legibility | 15% | 3.08 | Established |
| **Overall** | **100%** | **3.41** | **Established** |

<!-- IMPORTANT: Never include actual secret values (passwords, tokens, API keys, connection strings) in any field of this scorecard. When documenting hardcoded credentials, reference only the file path, line number, and type of secret (e.g., "hardcoded MongoDB password in config/db.js:25"). Use <redacted> or generic descriptions instead of literal values. -->

## Detailed Scores

### Spec-Driven Development

- **Detected system:** OpenSpec (`openspec/config.yaml`, `openspec/specs/`, `openspec/changes/archive/`)

| Sub-metric | Score (0-4) | Evidence |
| --- | --- | --- |
| System and artifacts | 4 | Two complete work items, each with a proposal, design, spec delta and a fully checked task list, both archived: `2026-10-03-add-recipe-quality-report` (16 of 16 tasks) and `2026-10-03-add-recipe-comparison` (8 of 8 tasks). Their specs live in `openspec/specs/recipe-quality-report/` and `openspec/specs/recipe-comparison/`. Activity is recent (archives and commits dated 2026-10-03). `openspec validate --all --json` passes for both specs. Workflow guidance is documented in `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `.github/copilot-instructions.md` and `.cursor/rules/mealie.mdc`. |
| Workflow commands | 4 | 12 OpenSpec skills in `.agents/skills/` and `.claude/skills/` (propose, apply, verify, archive and others) plus 12 `opsx-*` commands in each of `.github/prompts/`, `.claude/commands/opsx/` and `.cursor/commands/`. `CONTRIBUTING.md` section 3 maps every step to the command of each tool, and `AGENTS.md` lists the loop. |
| Documentation | 4 | `CONTRIBUTING.md` (specify step with a command table and `openspec validate <name> --strict`), `AGENTS.md` (spec-driven workflow section), `docs/agents/workflow-overview.md` (the loop), `openspec/config.yaml` (per-artifact rules), and two worked examples under `openspec/changes/archive/`. |

### Deterministic Checks

| Sub-metric | Score (0-4) | Evidence |
| --- | --- | --- |
| Linting | 4 | Ruff (`[tool.ruff.lint]` with a `select` list, `ignore = ["F403", "TID252", "B008"]`, per-file ignores and mccabe) runs in CI as `ruff format . --check` and `task py:lint` (`test-backend.yml`). ESLint runs in CI with `--max-warnings=0` (`test-frontend.yml`). Both are part of `task validate`, and ruff hooks are in `.pre-commit-config.yaml`. |
| Type checking | 2 | mypy runs cleanly (415 source files) in CI (`task py:mypy`) and in `task validate`, but the configuration is loose (`follow_imports = "skip"`, `ignore_missing_imports = true`, no `strict`) and `# type: ignore` appears in 37 of 415 Python files (8.9 percent, 61 suppressions), above the 5 percent limit for a 3. There is no frontend type check: `vue-tsc` is not installed (`docs/agents/tech-debt.md`, item 5). |
| Testing | 3 | pytest (1,408 passed, 18 skipped; unit, integration, multitenant and e2e suites) and Vitest (112 tests, next to the code) are configured, pass, and run in CI on pull requests (`test-backend.yml` on SQLite and PostgreSQL, `test-frontend.yml`). Focused runs work (`task py:test -- <path>`, `yarn vitest run <path>`). No coverage threshold is enforced and coverage of 90 percent or more is not demonstrated (`docs/agents/validation/testing-strategy.md`). |
| SAST / Security scanning | 3 | CodeQL runs in CI on pull requests, on pushes to `mealie-next` and weekly (`codeql.yml`, called from `pull-requests.yml`). Locally, `task security` runs bandit and Semgrep (43 bandit issues and 94 Semgrep findings are baselined in `docs/agents/tech-debt.md`). Neither blocks: the local task is report-only by design and nothing shows CodeQL failing a build, so this is not a 4. |
| Dependency / Vulnerability audit | 3 | Automated in CI: Trivy scans the built container image on every pull request (`partial-trivy-container-scanning.yml`, SARIF upload) and Renovate opens dependency updates (`renovate.json`). `task security` also runs `yarn audit` locally (421 advisories baselined). There is no blocking severity threshold or allowlist, so this is not a 4. |
| Build verification | 4 | `build-package.yml` builds the frontend and the Python package in PR CI, nightly and release workflows by calling `task py:package`, the same Task target used locally. The Docker image is also built in PR CI (`partial-trivy-container-scanning.yml`, `e2e.yml`) and locally with `task docker:build-from-package`. |
| Local validation path | 3 | `task validate` is one enforced command: Node guard, `ruff format --check`, ruff, mypy, `nuxt prepare`, ESLint with zero warnings, Vitest, then pytest in UTC. It exited 0 on 2026-10-03 (1,408 pytest and 112 Vitest tests) and is documented in `AGENTS.md`, `CONTRIBUTING.md` and `docs/agents/validation/local-validation-workflow.md`. It does not mirror CI exactly: no PostgreSQL or LDAP run, and the security scans and the package build are separate tasks. |

### AI Tooling & Skills

| Sub-metric | Score (0-4) | Evidence |
| --- | --- | --- |
| Workflow skills | 4 | 24 skills in `.agents/skills/`, deployed from the curated manifest `apm.yml` (4 APM dependencies, locked in `apm.lock.yaml`) plus OpenSpec: `code-review`, `commit-and-push-changes`, `create-pull-request-with-reviewers`, `gh-pr-comment-resolution`, `pr-follow-up`, `reflect-on-changes`, 12 OpenSpec skills, `ai-harness-setup` and `ai-native-assessment`. The inventory and the rules for managing it are documented in `docs/agents/conventions/apm-management.md` and referenced from `AGENTS.md`. |
| Security review skills | 3 | `codeguard` (default rule set in `.agents/skills/codeguard/rules/`, for example `codeguard-0-authentication-mfa.md` and `codeguard-0-api-web-services.md`) and `security-review` are deployed to the vendor-neutral `.agents/skills/` and to `.claude/skills/`, which are the only two roots `apm.lock.yaml` records for the APM skills. `.cursor/skills/` and `.github/skills/` hold only the OpenSpec skills, and `apm targets` reports `codex` as inactive because there is no `.codex/` directory. The score treats the vendor-neutral surface as covering the remaining tools; deployment to every target directory would be a stricter reading. The rules are the stock set and are not tailored to this repository: the repository-specific security rules (tenancy scoping, raw SQL, `v-html`) are written in `docs/agents/security/security.md` and `AGENTS.md`, not in the skill. |
| Skill relevance | 3 | The skills match the Python and TypeScript stack (`python-best-practices`, `accelint-ts-best-practices`, code and security review, OpenSpec). `accelint-ts-best-practices` is only loosely relevant to a Vue and Nuxt frontend and the `docs/agents/conventions/apm-management.md` page says so. No skill is specific to FastAPI, SQLAlchemy, Nuxt or Vuetify, so this is not a 4. |

### Documentation Tree

| Sub-metric | Score (0-4) | Evidence |
| --- | --- | --- |
| AGENTS.md | 4 | 63 lines, so a lean routing file. It has a repository map, a command table (`task validate` enforced, `task security` report-only), eight numbered rules that are easy to get wrong, the spec-driven loop and a "Where to look next" table into `docs/agents/`. All relative links in the agent docs resolve (45 checked, 0 broken) and the commands and files it names exist. `CLAUDE.md` mirrors it. |
| CONTRIBUTING.md | 4 | 58 lines covering setup, branching (`feat/<change-name>`), specifying with OpenSpec, implementing, validating (`task validate`, `task security`), commit and review expectations (Conventional Commits, `.github/pull_request_template.md`, reviewer checklist), remotes and a docs map. |
| docs/ structure | 4 | `docs/agents/` holds 16 files in dedicated sections: `architecture/`, `conventions/`, `deployment/`, `dev-environment/`, `security/`, `validation/`, plus `workflow-overview.md` and `tech-debt.md`. Alongside it is the upstream MkDocs site in `docs/docs/`. The sections are cross-linked from `AGENTS.md`, `CONTRIBUTING.md` and each other. |
| Content quality | 4 | Every file is grounded in this repository and has no placeholder text. For example `architecture/overview.md` lists real `mealie/` directories and layering, `data-model.md` cites the 43 Alembic revisions and `tests/unit_tests/test_alembic.py` (the count was checked), `common-issues.md` records real failures with causes and fixes, and `tech-debt.md` holds measured security baselines. Docs were last updated on 2026-10-03, the same day as the code. |

### AI IDE Configuration

- **Detected surface:** Vendor-neutral (`AGENTS.md`, `.agents/skills/`), Claude Code (`CLAUDE.md`, `.claude/`), Cursor (`.cursor/rules/mealie.mdc`, `.cursor/commands/`, `.cursor/skills/`), VS Code/GitHub Copilot (`.github/copilot-instructions.md`, `.github/prompts/`, `.github/skills/`)

| Sub-metric | Score (0-4) | Evidence |
| --- | --- | --- |
| Config exists | 4 | The configuration covers validation commands, coding conventions, and routing to docs, skills and specs, and it states explicit boundaries: never hand-edit generated files (`frontend/lib/api/types/`, `mealie/schema/*/__init__.py`), edit only the `en-US` locale, do not commit or push unless asked, and ask before destructive commands such as `task dev:clean`. `AGENTS.md`, `.cursor/rules/mealie.mdc` (`alwaysApply: true`) and `.github/copilot-instructions.md` all carry the key rules. |
| Commands / Skills | 4 | 12 OpenSpec commands are registered for each of Claude Code (`.claude/commands/opsx/`), Cursor (`.cursor/commands/`) and Copilot (`.github/prompts/`), covering the whole loop (propose, apply, verify, archive). The skills are deployed under `.agents/skills/` and `.claude/skills/`. `CONTRIBUTING.md` documents the command surface per tool. |
| MCP servers | 0 | No MCP servers are configured: `apm.yml` has `mcp: []` and there is no `.mcp.json`, `.cursor/mcp.json`, `.claude/mcp.json`, `.vscode/mcp.json` or `.codex/mcp.json`. The registry offers `microsoft/playwright-mcp`, which would fit the Playwright e2e suite and UI checks (`apm mcp search playwright`), but it was deliberately not added. |

### Agentic Legibility

- **Sub-assessment score:** 3.08
- **Sub-assessment tier:** Established

| Dimension | Metric | Score (0-4) | Notes | Evidence |
| --- | --- | --- | --- | --- |
| Repository Orientation | Agent repo map | 4 | A concise map with responsibilities for backend and frontend directories and the layering rule. | `AGENTS.md` repository map; `docs/agents/architecture/overview.md` (directory table, layering, code generation, runtime dependencies). |
| Repository Orientation | Entry point clarity | 3 | Start commands, test entry points and CI entry points are documented. The application entry file `mealie/app.py` is not named in any agent doc. | `AGENTS.md` command table and "Code entry points" line; `docs/agents/dev-environment/running-the-app.md`; `docs/agents/validation/ci-pipeline.md`. |
| Information Findability | Context proximity | 2 | Almost all context sits in the top-level `docs/agents/` tree. Only 3 READMEs exist near source (`mealie/alembic/README`, `frontend/components/README.md`, `frontend/store/README.md`) and only 3 of 287 backend modules have a module docstring; docstrings cover 21 percent of functions. The new quality-report module has a good header docstring, but upstream code does not. | `mealie/services/recipe/recipe_quality_service.py` (header docstring); AST scan of `mealie/`. |
| Information Findability | Change-relevant discoverability | 3 | Rules for common cross-cutting changes are written down: schema change implies model, migration, schemas, `task dev:generate` and tests; a new data endpoint needs an isolation test; a new locale string goes to `en-US` only. Downstream impact outside these cases must be found by reading imports. | `docs/agents/architecture/data-model.md` ("Rule for changes"); `AGENTS.md` rules 1 to 3; `docs/agents/validation/testing-strategy.md`. |
| Codebase Navigability | Naming and path semantics | 3 | Descriptive, domain-grouped names (`routes/recipe`, `services/recipe`, `repos`, `schema/recipe`) and documented suffix conventions (`*In`, `*Out`, `*Create`, `*Update`). Some indirection through base controller mixins and a generated `schema/*/__init__.py`. | `mealie/routes/_base/base_controllers.py`; `mealie/services/recipe/recipe_service.py`; `docs/agents/conventions/coding-standards.md`. |
| Codebase Navigability | Locality of concern | 3 | Vitest files sit next to the code they test (for example `frontend/composables/recipes/use-recipe-compare.test.ts`) and backend tests mirror the package layout. A backend feature spans route, service, repository and schema directories, which is documented but not colocated. | `docs/agents/validation/testing-strategy.md`; `tests/unit_tests/`, `tests/integration_tests/`. |
| Task Executability | Setup reproducibility | 3 | `task setup` bootstraps both stacks, versions are pinned (`mise.toml`, `.node-version`, `uv.lock`, `frontend/yarn.lock`), the default dev login is documented and a preflight check catches mismatched `node_modules`. Setup still needs `task`, `mise`, `uv` and corepack installed first and is not a single script from a bare machine. | `docs/agents/dev-environment/first-time-setup.md`; `CONTRIBUTING.md` section 1. |
| Task Executability | Task runbooks | 3 | The OpenSpec loop, task usage and a common-issues table with causes and fixes cover frequent work. There are no step-by-step runbooks for tasks such as adding an endpoint or a page. | `docs/agents/workflow-overview.md`; `docs/agents/conventions/task-usage.md`; `docs/agents/dev-environment/common-issues.md`. |
| Verification Legibility | Test discoverability | 3 | Test files follow source names, focused runs are documented for both stacks, and the test suites are explained. There is no map from a source module to its tests. | `docs/agents/validation/testing-strategy.md`; `AGENTS.md` (`task py:test -- <path>`, `task ui:test:ci`). |
| Verification Legibility | Verification path clarity | 4 | One enforced command with its ordered steps, expected counts and runtime, the CI equivalence table and the differences, the browser check for UI changes, and the report-only security baseline. | `docs/agents/validation/local-validation-workflow.md`; `docs/agents/validation/ci-pipeline.md`; `CONTRIBUTING.md` section 5. |
| Intent and Invariants | Business logic explainability | 2 | Product intent lives mostly in the OpenSpec specs for the two added features. In the upstream code, rules are in conditionals with few explanations (9 rationale-style comments across services and repositories) and there are no decision records outside OpenSpec. | `openspec/specs/recipe-quality-report/spec.md`; `openspec/specs/recipe-comparison/spec.md`; `openspec/changes/archive/*/design.md`. |
| Intent and Invariants | Invariant visibility | 3 | The main invariants are stated: group and household scoping with isolation tests (`tests/multitenant_tests/`), the layering rule, never hand-editing generated files and the migration chain test. Compatibility and performance constraints are not documented. | `AGENTS.md` rules 1 to 2; `docs/agents/security/security.md`; `docs/agents/architecture/data-model.md`. |
| Safety Boundaries | Generated vs editable boundaries | 4 | Generated paths are named in `AGENTS.md`, `CLAUDE.md` and the Cursor rule, the generator and its command are documented, and the generated files carry banners ("This file was automatically generated from pydantic models", "auto-generated by gen_schema_exports.py"). | `AGENTS.md` rule 1; `frontend/lib/api/types/recipe.ts`; `mealie/schema/recipe/__init__.py`; `.cursor/rules/mealie.mdc`. |
| Safety Boundaries | Risk surface annotation | 3 | Security rules for tenancy, auth, raw SQL and `v-html` are written down, with a security baseline and a rule to ask before destructive commands (`task dev:clean`). Auth, migrations and secrets have no per-area review requirement. | `docs/agents/security/security.md`; `AGENTS.md` rule 8; `docs/agents/tech-debt.md`. |
| Machine-Friendliness | Explicit conventions | 4 | Written, repository-specific conventions with anti-patterns: layering, dependency injection (`get_repositories`, `get_current_user`), `uv run` only, component naming by role, `en-US` only, Conventional Commits. | `docs/agents/conventions/coding-standards.md`; `AGENTS.md` rules 1 to 8. |
| Machine-Friendliness | Structured metadata | 3 | Machine-readable artifacts exist: `apm.yml` and `apm.lock.yaml`, `openspec/config.yaml`, `renovate.json`, `.pre-commit-config.yaml`, `Taskfile.yml`, `.github/pull_request_template.md`. There is no `CODEOWNERS` file and no module manifest. | `apm.yml`; `openspec/config.yaml`; `Taskfile.yml`. |
| Freshness and Trustworthiness | Documentation freshness | 4 | Agent docs were written and last updated on 2026-10-03 with the code, 45 of 45 relative links resolve, the documented files and tasks exist and the documented counts match (43 Alembic revisions, 1,408 tests). The upstream `docs/docs/` site is a separate project. | `git log -- docs/agents AGENTS.md CONTRIBUTING.md`; `docs/agents/validation/local-validation-workflow.md`. |
| Freshness and Trustworthiness | Drift detection | 2 | `openspec validate` and the link and count checks run only on demand. No CI job validates the specs, links in the agent docs or the APM lockfile (documented as a deliberate decision in `docs/agents/validation/ci-pipeline.md`). The generated-code step is guarded only by `task dev:generate` and `locale-sync.yml`. | `.github/workflows/`; `docs/agents/validation/ci-pipeline.md` ("Not wired (by decision)"). |

#### Agentic Legibility Strengths

- A lean routing file (`AGENTS.md`, 63 lines) with a repository map and a verified link tree into 16 repository-specific docs.
- One enforced validation command with documented steps, counts and CI equivalence, plus a measured security baseline that changes must not worsen.
- Clear safety boundaries: generated files are named and bannered, translations are restricted to `en-US`, and destructive commands require asking.
- Explicit, repository-specific conventions and a complete spec-driven loop with worked examples (two archived changes).

#### Agentic Legibility Gaps

- Little context near the code: 3 READMEs and 3 of 287 backend modules with a module docstring.
- Business rules in the existing code are rarely explained, and decisions outside OpenSpec have no records.
- No automated drift detection for specs, agent docs or the APM lockfile.
- No `CODEOWNERS`, no source-to-test map and no runbooks for common change types.

#### Highest-Leverage Legibility Improvements

1. Add short module docstrings and READMEs for the core packages (`mealie/services/recipe/`, `mealie/repos/`, `frontend/composables/`) that state purpose, boundaries and the tests that cover them.
2. Add a CI job (or a Task target run by `task validate`) that runs `openspec validate --all` and checks agent doc links, and document the decision records in `docs/agents/`.
3. Add runbooks for adding an endpoint and a page, and a `CODEOWNERS` file for sensitive areas (auth, migrations, `mealie/repos/`).

#### Agentic Legibility Final Judgment

An autonomous coding agent can safely understand the repository, make a scoped change, run the right validation and avoid the main high-risk mistakes: the map, conventions, enforced `task validate` and the generated-file and tenancy rules are explicit and current. Two features were added this way (spec, implementation, validation and archive). The main blockers are not safety issues but efficiency ones: little context sits next to the upstream code, business rules there must be inferred, and nothing automatically catches drift in specs or agent docs.

## Key Strengths

- **A spec-driven lifecycle that is actually used.** Two OpenSpec changes (`add-recipe-quality-report`, `add-recipe-comparison`) each have a proposal, design, spec delta and a fully checked task list, are archived into `openspec/specs/`, and pass `openspec validate --all`. The workflow is documented in `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `.github/copilot-instructions.md` and `.cursor/rules/mealie.mdc`, with 12 workflow commands for each of three tools.
- **One enforced validation command that mirrors CI.** `task validate` runs ruff format and lint, mypy, `nuxt prepare`, ESLint with `--max-warnings=0`, Vitest and pytest, and exited 0 with 1,408 pytest and 112 Vitest tests. CI runs the same checks on pull requests (`test-backend.yml`, `test-frontend.yml`) and builds the package through the same Task target (`build-package.yml`).
- **A lean, verified documentation tree.** `AGENTS.md` is 63 lines and routes to 16 repository-specific files under `docs/agents/` with no placeholders and no broken relative links (45 checked), next to a 58-line `CONTRIBUTING.md` that covers setup, branching, specifying, validating and review.
- **Clear safety boundaries.** Generated files are named and bannered, only `en-US` strings may be edited, group and household isolation tests are required for new data endpoints, destructive commands require asking, and the security baseline (421 advisories, 43 bandit issues, 94 Semgrep findings) is recorded in `docs/agents/tech-debt.md`.
- **Consistent agent surfaces.** Claude Code, Cursor, GitHub Copilot and the vendor-neutral `.agents/skills/` carry the same rules and the same command set.

## Key Gaps

- **No MCP servers.** `apm.yml` has `mcp: []` and no tool-specific MCP file exists, so AI IDE Configuration scores 2.67 (the only category in the Structured tier).
- **Loose type checking.** mypy runs with `follow_imports = "skip"` and `ignore_missing_imports = true`, with `# type: ignore` in 37 of 415 Python files (8.9 percent). The frontend has no type check (`vue-tsc` is not installed, `docs/agents/tech-debt.md` item 5).
- **Security scanning does not gate.** CodeQL and Trivy run in CI and `task security` runs bandit, Semgrep and `yarn audit` locally, but none of them blocks a merge or a commit, and there is no severity threshold or allowlist. No coverage threshold is enforced either.
- **Little context next to the upstream code.** 3 READMEs and 3 of 287 backend modules with a module docstring, 21 percent of functions with a docstring, 9 rationale-style comments across services and repositories, and no source-to-test map.
- **No drift detection and no ownership file.** Specs, agent doc links and the APM lockfile are not checked in CI, and there is no `CODEOWNERS`.
- **Security skill not tailored.** `codeguard` and `security-review` use stock rules and are deployed to `.agents/skills/` and `.claude/skills/` only.

## Recommended Actions

| Priority | Action | Category | Sub-metric | Current | Target | Impact |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Add `microsoft/playwright-mcp` under `dependencies.mcp` in `apm.yml`, preview with `apm install --dry-run`, review the file list on a clean branch, then run `apm install --only=mcp` and describe it in `docs/agents/conventions/apm-management.md`. It fits the Playwright e2e suite and the browser checks required for UI changes. | AI IDE Configuration | MCP servers | 0 | 3 | 0.0750 |
| 2 | Tighten mypy: drop `follow_imports = "skip"`, enable `disallow_untyped_defs` and `disallow_incomplete_defs` through `[[tool.mypy.overrides]]` for new and changed modules, reduce `# type: ignore` from 37 files to 20 or fewer (5 percent of 415), and add `vue-tsc` for the frontend (tech debt item 5). | Deterministic Checks | Type checking | 2 | 3 | 0.0625 |
| 3 | Add short module docstrings and READMEs to the core packages (`mealie/services/recipe/`, `mealie/repos/`, `frontend/composables/`) stating purpose, boundaries and the tests that cover them. | Agentic Legibility | Context proximity | 2 | 3 | 0.0375 |
| 4 | Record the reasons for core business rules (recipe scoping, import and parsing behavior) as comments or short decision records, starting with the `design.md` format already used in `openspec/changes/archive/`. | Agentic Legibility | Business logic explainability | 2 | 3 | 0.0375 |
| 5 | Add a CI job, or a Task target called by `task validate`, that runs `openspec validate --all` and checks relative links in `AGENTS.md`, `CONTRIBUTING.md` and `docs/agents/`, and record the result in `docs/agents/validation/ci-pipeline.md`. | Agentic Legibility | Drift detection | 2 | 3 | 0.0375 |
