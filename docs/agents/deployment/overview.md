# Deployment

Mealie ships as a single container: the frontend is statically generated and served by FastAPI (`mealie/routes/spa/`). This fork does not change the deployment path.

- **Build from source:** `task py:package` builds the Python package (frontend generated and copied in via `py:package:copy-frontend`); `task docker:build-from-package` builds the image from `dist/` using `docker/Dockerfile`.
- **Run locally in production mode:** `task docker:prod` (compose file `docker/docker-compose.yml`). Requires a container engine.
- **Dev services:** `docker/docker-compose.dev.yml` (PostgreSQL and Mailpit) via `task dev:services`.
- **Container engine:** the three container tasks (`dev:services`, `docker:build-from-package`, `docker:prod`) run `docker` when it is installed and `podman` otherwise (Taskfile variable `CONTAINER_ENGINE`). Override per run: `task dev:services CONTAINER_ENGINE=docker`. Podman on macOS needs a running machine (`podman machine list`).
- **Release:** upstream workflows `release.yml`, `publish.yml`, `nightly.yml`, `build-package.yml` (see [CI pipeline](../validation/ci-pipeline.md)).
- **Configuration:** [environment variables](../dev-environment/environment-variables.md); upstream installation docs under `docs/docs/documentation/getting-started/installation/`.

Verified on this machine (Docker not installed, Podman 5.7.1 with a running machine): `task --dry` resolves the three container tasks to `podman`, and `podman compose config` parses both compose files. Not yet exercised: pulling images, building the production image, or starting the containers.
