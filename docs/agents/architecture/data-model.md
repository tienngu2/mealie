# Data model

- **ORM:** SQLAlchemy models in `mealie/db/models/` (`group`, `household`, `recipe`, `users`, `server`), registered in `_all_models.py`.
- **Databases:** SQLite by default (`dev/data/mealie*.db` in development); PostgreSQL via `task py:postgres` (needs Docker for `task dev:services`).
- **Migrations:** Alembic in `mealie/alembic/versions/` (about 55 revisions). Create one with `task py:migrate -- "description"`. `tests/unit_tests/test_alembic.py` guards the migration chain.
- **Tenancy:** Group contains households; households contain recipes, meal plans, and shopping lists. Repositories scope queries to the caller's group/household, so passing a wrong id typically yields a 404.
- **Schemas:** Pydantic models in `mealie/schema/` mirror the models; TypeScript types are generated from them (never hand-edit `frontend/app/lib/api/types/`).

Rule for changes: a new column or table needs the SQLAlchemy model, an Alembic migration, the Pydantic schemas, `task dev:generate`, and tests. Test against SQLite locally; CI also runs PostgreSQL.
