# Coding standards

Observed conventions; `AGENTS.md` is the authoritative short version.

**Python**
- Ruff for format and lint (`line-length = 120`, target `py314`, rule sets in `pyproject.toml`); mypy over `mealie/`.
- Type hints on all functions; handle `Optional` explicitly.
- Use `uv run ...` for Python commands, never bare `python`/`pip`.
- Dependency injection for repos and the current user (`Depends(get_repositories)`, `Depends(get_current_user)`); never create sessions by hand (use `generate_session` or `session_context()`).
- Settings via `get_app_settings()`, directories via `get_app_dirs()`; never instantiate `AppSettings()`.
- Schema suffixes: `*In`, `*Out`, `*Create`, `*Update`.

**Frontend**
- TypeScript strict; ESLint with `--max-warnings=0`.
- Component prefixes: Domain components by domain, global primitives `Base*`, layout `App*`/`The*`.
- API access through `useUserApi()` and the clients in `frontend/app/lib/api/`; shared logic in `composables/`.
- New user-visible strings go in `en-US` only.

**Process**
- Conventional Commits for commits and PR titles (checked by `.github/workflows/pull-request-lint.yml`).
- Pre-commit hooks (ruff, YAML/JSON/TOML checks, whitespace) run if installed via `task setup:py`.
