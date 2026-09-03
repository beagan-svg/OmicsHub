# OmicsHub project map

OmicsHub is a Django application that mirrors OCS data into PostgreSQL, builds OCS commands from workflow manifests, and submits those commands through one Celery worker.

## Application code

`apps/accounts/` owns the user model, registration, login form, and account administration.

`apps/sample_catalog/` owns the local OCS mirror. It contains fastq samples, stage statuses, the `ocs_sync.py` DynamoDB synchronization module, sync tasks, and sample API endpoints. Each app's REST API viewset lives in that app's `views.py`; the HTML pages all live in `apps/web_ui/views/`.

`apps/ocs_integration/` owns external OCS boundaries. `dynamodb.py` reads OCS DynamoDB tables, `s3.py` reads S3 metadata and contents, and `cli.py` runs the `ocs` command for submissions. Tests in this package replace those external clients.

`apps/workflow_engine/` owns workflow manifests. It parses and validates uploaded JSONC, stores manifests, selects modalities, and builds command arguments. `manifest_service.py` stores validated uploads.

`apps/submission_queue/` owns the submission queue. Models store queue entries and cart items. `queue_planning.py` plans work, `queue_entries.py` creates entries, and `queue_claiming.py` selects submissions. Tasks submit commands. API and admin modules expose queue operations.

`apps/web_ui/` owns the server-rendered dashboard, checkout flow, queue pages, exports, templates, CSS, browser behavior, and `data_location_queries.py` for Data Locations rows.
Reusable template fragments live in `apps/web_ui/templates/partials/` and use names that describe what they render, such as `status_badge.html` and `table_pager.html`.

## Django project code

`omicshub/settings/` contains shared, production, and test settings. Production settings read environment variables. Test settings use local defaults and test fakes instead of external AWS services.

`omicshub/urls.py` owns the top level URL prefixes. `omicshub/celery.py` configures Celery. `omicshub/health.py` defines the readiness endpoint. The remaining modules provide middleware, logging, exception handling, ASGI, and WSGI entry points.

`manage.py` is the Django command entry point. Docker is the supported runtime for the web process, workers, Beat, PostgreSQL, and Redis.

## Runtime and deployment files

`Dockerfile` builds the application image. It installs the locked dependencies and vendored OCS packages, copies the Django source, and runs the image as a non-root user.

`compose.yaml` defines the local Docker stack. A one-shot container runs migrations before the web process, workers, and Celery Beat start. The web container runs `collectstatic` before Gunicorn.

`.env.docker.example` documents required Docker settings. `.env.docker` is local configuration and is ignored by Git. AWS credentials are mounted into the containers from the path in `AWS_CREDENTIALS_FILE`.

`docker_tools/setup_docker.sh` is the supported setup and startup command. `docker_tools/healthcheck.py` is the web container readiness probe. `docker_tools/vendor_gcs.sh` prepares the OCS package sources used by the image build. `docker_tools/test.sh` runs the test suite locally against a throwaway Postgres container.

## Configuration and build inputs

`workflow_manifests/` contains an example workflow manifest for operators. "Manifest" names the JSONC file itself; once uploaded and stored it is a "config" (`WorkflowConfig`, the `/configs/` pages), and only a config can drive submissions.

`vendor/gcs/` contains the pinned OCS package source prepared by `docker_tools/vendor_gcs.sh`. Treat it as generated build input, not as OmicsHub application code. Do not add application logic there.

`.github/workflows/` contains CI and Docker image checks. CI validates dependency locks, Ruff, typing, migrations, production settings, tests, and a build from the pinned OCS source.

`uv.lock` contains runtime and development dependency pins. Update it with `uv lock` after changing `pyproject.toml`.

## Where new code belongs

Put a change in the app that owns its data or external boundary. Put shared Django runtime behavior in `omicshub/`. Put Docker setup in `docker_tools/` or `compose.yaml`. Put validation in the nearest app test package. Keep credentials, generated artifacts, local caches, and machine specific files out of Git.
