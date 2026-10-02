# Deployment

Mealie ships as a single container: the frontend is statically generated and served by FastAPI (`mealie/routes/spa/`). This fork does not change the deployment path.

- **Build from source:** `task py:package` builds the Python package (frontend generated and copied in via `py:package:copy-frontend`); `task docker:build-from-package` builds the image from `dist/` using `docker/Dockerfile`.
- **Run locally in production mode:** `task docker:prod` (compose file `docker/docker-compose.yml`). Requires Docker.
- **Dev services:** `docker/docker-compose.dev.yml` (PostgreSQL and Mailpit) via `task dev:services`.
- **Release:** upstream workflows `release.yml`, `publish.yml`, `nightly.yml`, `build-package.yml` (see [CI pipeline](../validation/ci-pipeline.md)).
- **Configuration:** [environment variables](../dev-environment/environment-variables.md); upstream installation docs under `docs/docs/documentation/getting-started/installation/`.

Docker is not installed on the current dev machine, so these paths are documented from the Taskfile and workflows but were not exercised here.
