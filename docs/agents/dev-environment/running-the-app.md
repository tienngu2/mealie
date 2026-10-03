# Running the app

Two processes, each in its own terminal:

```bash
task py     # backend  -> http://localhost:9000  (API docs at /docs)
task ui     # frontend -> http://localhost:3000
```

Health check: `curl -s localhost:9000/api/app/about` returns JSON with `"version":"develop"`.

- Open http://localhost:3000 and log in. Dev data is stored under `dev/data/` (SQLite, recipes, users). Reset it with `task dev:clean` (**destroys all dev data**).
- The backend reloads on changes under `mealie/`; Nuxt hot-reloads the frontend.
- Environment for development is set in the `env:` block of `Taskfile.yml` (SMTP points at Mailpit, `BASE_URL`, `API_PORT`). Local overrides go in an untracked `.env` or `.dev.env`.
- For agents running servers in the background, redirect logs to a file (for example `task py > /tmp/mealie-backend.log 2>&1 &`) and read them with `tail`.
- Nuxt may ask to opt in to anonymous telemetry on first start; set `NUXT_TELEMETRY_DISABLED=1` to avoid it.
