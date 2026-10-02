# Environment variables

The full list of runtime variables is documented upstream in `docs/docs/documentation/getting-started/installation/backend-config.md` (general, security, SMTP, LDAP/OIDC, AI providers). Do not duplicate it here.

Development defaults live in the `env:` block at the top of `Taskfile.yml`:

| Variable | Dev value | Purpose |
|---|---|---|
| `UV_FROZEN` | `1` | install strictly from `uv.lock` (needed because of the `exclude-newer` window in `pyproject.toml`) |
| `API_PORT` | `9000` | backend port |
| `BASE_URL` | `http://localhost:3000` | frontend URL used in links |
| `DEFAULT_GROUP` / `DEFAULT_HOUSEHOLD` | `Home` / `Family` | seed names |
| `TOKEN_TIME` | `256` (hours) | auth token lifetime |
| `SMTP_*` | Mailpit on `localhost:1025` | dev email (`task dev:services`) |
| `PRODUCTION` | `false` | development mode |

Overrides: `.env` and `.dev.env` (both loaded by the Taskfile, `.dev.env` is gitignored). Never commit secrets. A `WARNING Secrets directory '/run/secrets' does not exist` log line at backend start is harmless in development.
