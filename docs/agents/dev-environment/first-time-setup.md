# First-time setup

Prerequisites: [uv](https://docs.astral.sh/uv/) (it installs Python 3.14 on demand), [Node 24](https://nodejs.org/) (recommended via [mise](https://mise.jdx.dev/); `mise.toml` and `.node-version` pin it), [pnpm](https://pnpm.io/), and [task](https://taskfile.dev/). Docker is optional (only for PostgreSQL and Mailpit via `task dev:services`).

```bash
brew install go-task pnpm mise      # macOS example
unset VIRTUAL_ENV                    # see common-issues.md if a parent folder has a .venv
task setup                           # uv sync (+ pre-commit install) and pnpm install
task validate                        # confirms the toolchain works: should exit 0
```

Notes:

- The Taskfile sets `UV_FROZEN=1`, so `uv` installs from `uv.lock` and never re-resolves.
- `task setup:py` installs the pre-commit hooks (ruff). That sets `core.hooksPath` for the clone; this fork is its own repository, so that is intended.
- Optional for the security task: `brew install semgrep`.
- Skills for agents: `apm install` (see [APM management](../conventions/apm-management.md)).
