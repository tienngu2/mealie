# Architecture overview

Mealie is a self-hosted recipe manager and meal planner: a FastAPI backend plus a Nuxt 3 / Vue 3 frontend. In production the frontend is statically generated and served by FastAPI (`mealie/routes/spa/`); in development they run as two processes (backend :9000, frontend :3000).

## Backend (`mealie/`)

| Directory | Responsibility |
|---|---|
| `routes/` | HTTP layer, grouped by domain: `recipe`, `groups`, `households`, `users`, `auth`, `admin`, `explore`, `organizers`, `parser`, `media`, `unit_and_foods`, `comments`, `spa`, `shared`, `_base` (controller base classes and mixins) |
| `services/` | Business logic: `recipe`, `scraper`, `parser_services`, `migrations`, `exporter`, `backups_v2`, `scheduler`, `event_bus_service`, `email`, `openai`, `seeder`, and more |
| `repos/` | Data access via SQLAlchemy, obtained through `AllRepositories` / `get_repositories` |
| `db/models/` | SQLAlchemy models: `group`, `household`, `recipe`, `users`, `server` |
| `schema/` | Pydantic schemas (`*In`, `*Out`, `*Create`, `*Update`) |
| `alembic/` | Migrations |
| `core/`, `middleware/`, `pkgs/`, `lang/`, `scripts/` | Settings and security, middleware, shared packages, backend translations, scripts |

Layering: controller -> service -> repository. Controllers handle HTTP only; services hold logic; repositories are the only database access. Everything is scoped to a **group** and **household**, and repositories filter by that context automatically.

## Frontend (`frontend/`)

`pages/` (routes), `components/` (Domain/, global/, Layout/ naming rules in `AGENTS.md`), `composables/` (shared state and API logic), `lib/api/` (API clients; `lib/api/types/` is generated), `layouts/`, `middleware/`, `plugins/`, `lang/` (translations), `tests/` (shared test helpers). The recipe quality report is served by `GET /api/recipes/quality-report` (rules in `mealie/services/recipe/recipe_quality_service.py`) and shown on the page `/g/{groupSlug}/recipes/quality`.

## Code generation

`task dev:generate` (entry: `dev/code-generation/main.py`) produces TypeScript types, schema exports, locale and unit-system files, and pytest route and data-path helpers from the Pydantic schemas. Run it after any schema change.

## External dependencies at runtime

SQLite (default) or PostgreSQL; optional SMTP, LDAP/OIDC, and OpenAI-compatible providers (see upstream `docs/docs/documentation/getting-started/installation/`).
