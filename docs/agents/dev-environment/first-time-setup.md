# First-time setup

Prerequisites: [uv](https://docs.astral.sh/uv/) (it installs the Python 3.12 that `pyproject.toml` requires), [Node 22](https://nodejs.org/) (recommended via [mise](https://mise.jdx.dev/); `mise.toml` and `.node-version` pin it), [yarn 1](https://classic.yarnpkg.com/) (via corepack), and [task](https://taskfile.dev/). Docker or Podman is optional (only for PostgreSQL and Mailpit via `task dev:services`).

```bash
brew install go-task mise            # macOS example (yarn via corepack)
unset VIRTUAL_ENV                    # see common-issues.md if a parent folder has a .venv
task setup                           # uv sync (+ pre-commit install) and yarn install
task validate                        # confirms the toolchain works: should exit 0
```

Notes:

- Install the frontend with `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 yarn install --frozen-lockfile` so versions follow `frontend/yarn.lock` exactly.
- **Preflight after installing:** the `version` in `frontend/node_modules/nuxt/package.json` must equal the `nuxt@` entry in `frontend/yarn.lock`, `frontend/node_modules/.yarn-integrity` must exist, and `frontend/node_modules/.pnpm` must not. A `.pnpm` folder means `node_modules` came from another checkout: delete `frontend/node_modules` and reinstall.
- Start from a clean clone when switching base commits. Ignored folders (`node_modules`, `.venv`, `dev/data`) survive a checkout and silently mix versions.
- `task setup:py` installs the pre-commit hooks (ruff). That sets `core.hooksPath` for the clone, which is intended.
- Optional for the security task: `brew install semgrep`.
- Skills for agents: `apm install` (see [APM management](../conventions/apm-management.md)).
