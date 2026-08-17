# OmicsHub project map

OmicsHub is a Django application that mirrors OCS data into Postgres, builds OCS commands from workflow manifests, and submits those commands through one Celery worker.

## Application code

`apps/accounts/` owns the user model, registration, login form, and account administration.

`apps/sample_catalog/` owns the local OCS mirror. It contains fastq samples, stage statuses, DynamoDB sync services, sync tasks, and sample API endpoints.

`apps/ocs_integration/` owns external OCS boundaries. `dynamodb.py` reads OCS DynamoDB tables. `cli.py` runs the `ocs` command for submissions. Tests in this package replace those external clients.

`apps/workflow_engine/` owns workflow manifests. It parses and validates uploaded JSONC, stores manifests, selects modalities, and builds command arguments.

`apps/submission_queue/` owns the submission queue. Models store queue entries and cart items. Services plan and enqueue work. Tasks claim entries and submit commands. API and admin modules expose queue operations.

`apps/web_ui/` owns the server rendered dashboard, checkout flow, queue pages, exports, templates, CSS, and browser behavior.

## Django project code

`omicshub/settings/` contains shared, production, and test settings. Production settings read environment variables. Test settings use local test services and do not read Docker credentials.

`omicshub/urls.py` owns the top level URL prefixes. `omicshub/celery.py` configures Celery. `omicshub/health.py` defines the readiness endpoint. The remaining modules provide middleware, logging, exception handling, ASGI, and WSGI entry points.

`manage.py` is the Django command entry point. Docker is the supported runtime for the web process, workers, beat, Postgres, and Redis.

## Runtime and deployment files

`Dockerfile` builds the application image. It installs the project and the vendored OCS packages, then runs the image as a non-root user.

`compose.yaml` defines the local Docker stack. The web container runs migrations and collectstatic before Gunicorn. The other application containers run the submission worker, default worker, and beat scheduler.

`.env.docker.example` documents required Docker settings. `.env.docker` is local configuration and is ignored by Git. AWS credentials are mounted into the containers from the path in `AWS_CREDENTIALS_FILE`.

`scripts/setup_docker.sh` is the supported setup and startup command. `scripts/healthcheck.py` is the web container readiness probe. `scripts/vendor_gcs.sh` prepares the OCS package sources used by the image build.

`deploy/launchd/` contains an optional macOS LaunchAgent. It starts Docker Compose after Docker Desktop is available. It does not start Django or Celery directly.

## Configuration and build inputs

`workflow_manifests/` contains example workflow manifests used by operators and tests. A manifest is uploaded and stored in `WorkflowConfig` before it can drive submissions.

`vendor/gcs/` contains the OCS package source required by the Docker build. Treat it as a build input, not as OmicsHub application code. Do not add application logic there.

`.github/workflows/` contains CI and Docker image checks. CI validates `uv.lock`, Ruff, migrations, production settings, and tests.

CI type checks the stable model, OCS CLI, and container health boundaries. The manifest and view layers contain untyped JSON and request data, so they are being added to the type check in stages.

`uv.lock` contains runtime and development dependency pins. Update it with `uv lock` after changing `pyproject.toml`.

## Where new code belongs

Put a change in the app that owns its data or external boundary. Put shared Django runtime behavior in `omicshub/`. Put Docker setup in `scripts/` or `compose.yaml`. Put host startup automation in `deploy/launchd/`. Put validation in the nearest app test package. Keep credentials, generated artifacts, local caches, and machine specific files out of Git.
