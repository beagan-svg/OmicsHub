# OmicsHub

OmicsHub loads fastq sample data from OCS, shows each sample's stage status, builds OCS
commands, and submits alignment and post-alignment jobs.

The dashboard stores fastq samples, stage statuses, workflow manifests, users, and queue
entries in PostgreSQL. Celery uses Redis for task messages. One submission worker sends
commands through the ocs CLI.

## Start the app with Docker

Docker is the supported runtime. The Docker stack starts PostgreSQL, Redis, Django, two
Celery workers, beat, and the ocs CLI from one image.

### Requirements

Install these tools on the machine that will run OmicsHub:

- Docker Desktop, or Docker Engine with the Docker Compose plugin
- AWS CLI
- An AWS profile that can read the OCS DynamoDB tables and submit OCS demands
- A local genomics-cloud-services checkout until the OCS packages become a Git submodule
  or a published package dependency

The app reads AWS credentials from an app-scoped credentials file. It does not read access
keys from .env.docker.

### Clone the repository

Clone the repository on a new machine:

~~~bash
git clone https://github.com/beagan-svg/OmicsHub.git omicshub
cd omicshub
~~~

Pull changes in an existing checkout:

~~~bash
cd omicshub
git pull
~~~

### Create the AWS credentials file

Create a credentials file for OmicsHub. This file stays outside the repository and outside
the machine-wide ~/.aws/credentials file.

~~~bash
mkdir -p ~/.omicshub
chmod 700 ~/.omicshub
AWS_SHARED_CREDENTIALS_FILE=~/.omicshub/credentials aws configure --profile omicshub
chmod 600 ~/.omicshub/credentials
~~~

The AWS profile must have access to these tables, where <env> comes from OCS_ENV_BASE:

- <env>-fastq-metadata
- <env>-fastq-history
- <env>-demand-registry

The same profile must allow the ocs CLI to submit alignment and post-alignment demands.

### Create the Docker settings

Run the setup command from the repository root:

~~~bash
scripts/setup_docker.sh
~~~

The first run copies .env.docker.example to .env.docker and stops. Open .env.docker
and set these values:

~~~dotenv
SECRET_KEY=replace-with-a-long-random-value
POSTGRES_PASSWORD=replace-with-a-database-password
AWS_CREDENTIALS_FILE=/Users/you/.omicshub/credentials
AWS_PROFILE=omicshub
OCS_ENV_BASE=prod
OCS_AWS_REGION=us-west-2
~~~

AWS_CREDENTIALS_FILE must be an absolute path. Docker Compose does not expand ~ in a
bind mount path. Keep .env.docker out of Git.

Run the setup command again:

~~~bash
scripts/setup_docker.sh
~~~

The command validates the settings, copies the OCS packages into vendor/gcs/, builds the
Docker image, and starts the stack. It waits for the dashboard container health check before it
returns.

If the genomics-cloud-services checkout is not at the default location, set GCS_SRC:

~~~bash
GCS_SRC=/path/to/genomics-cloud-services scripts/setup_docker.sh
~~~

The setup script stops with an error when any of the four OCS packages is missing:
gcs-core, gcs-api-client, gcs-docker-tools, or gcs-cli.

### Open the dashboard

Open this URL in a browser:

~~~text
http://127.0.0.1:8001/
~~~

Docker serves plain HTTP on the local port. Use the WEB_PORT value from .env.docker if
you changed the port. Local HTTPS needs a TLS proxy and a certificate, so
https://127.0.0.1:8001/ does not work with the default Docker settings.

Check the stack and view logs with these commands:

~~~bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f web_ui
docker compose --env-file .env.docker logs -f worker-submissions
curl http://127.0.0.1:8001/healthz/
~~~

Stop the containers without deleting the database volume:

~~~bash
docker compose --env-file .env.docker down
~~~

Do not run docker compose down -v unless you intend to delete the PostgreSQL volume.

## How OmicsHub reads OCS data

The app uses one OCS integration package, apps/ocs_integration.

apps/ocs_integration/dynamodb.py reads these DynamoDB tables:

| Table | Use |
|---|---|
| <env>-fastq-metadata | Load fastq sample metadata. |
| <env>-fastq-history | Load the stage history for each fastq sample. |
| <env>-demand-registry | Load demand status and count IN_PROGRESS demands. |

apps/ocs_integration/cli.py runs the ocs command for submissions. The Celery submission worker passes
the configured AWS profile to that process.

OCS_ENV_BASE=prod reads tables such as prod-fastq-metadata. Change this value before
connecting to another OCS environment.

The dashboard stores the last successful OCS sync in PostgreSQL. A status of Synced means
the last AWS status pull completed. It does not mean that OCS and PostgreSQL contain the same
rows at every moment.

## Project layout

Read docs/PROJECT_MAP.md for the ownership map. The main directories are:

| Directory | Contains |
|---|---|
| apps/accounts/ | The custom user model, login, signup, and account admin. |
| apps/sample_catalog/ | Fastq samples, stage statuses, OCS sync services, and sample API endpoints. |
| apps/ocs_integration/ | DynamoDB reads and the ocs CLI submission boundary. |
| apps/submission_queue/ | Queue models, planning, round-robin claiming, Celery tasks, and queue API endpoints. |
| apps/workflow_engine/ | Workflow manifest parsing, validation, modality selection, and command building. |
| apps/web_ui/ | Server-rendered pages, forms, templates, CSS, static assets, and browser tests. |
| omicshub/ | Django settings, URLs, Celery setup, health checks, middleware, and logging. |
| scripts/ | Docker setup, container health checks, and OCS package preparation. |
| deploy/launchd/ | Optional macOS startup files for Docker Desktop. |
| workflow_manifests/ | Example JSONC workflow manifests. |
| vendor/gcs/ | OCS package source copied in before a Docker build. This is a build input, not app code. |

## Workflow manifests

A workflow manifest tells OmicsHub how to build commands. It contains command templates,
references, chemistries, probe sets, modality settings, the OCS job limit, submission
spacing, and the status labels that mark a stage complete.

The repository example is:

~~~text
workflow_manifests/workflow_manifest.jsonc
~~~

The file is an example and a reviewable input. The database stores the active manifest. Editing
the file does not change the active manifest until a staff user uploads and activates it.

Check a manifest before activating it:

~~~bash
python manage.py check_config_coverage workflow_manifests/workflow_manifest.jsonc
~~~

The command checks whether the manifest can build commands for fastq samples in the local
mirror.

Upload and activate a manifest through the API:

~~~bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F file=@workflow_manifests/workflow_manifest.jsonc \
  http://127.0.0.1:8001/api/configs/

curl -X POST \
  -H "Authorization: Bearer <token>" \
  http://127.0.0.1:8001/api/configs/<id>/activate/
~~~

OmicsHub validates the JSONC file before storing it. The parser removes comments and expands
pipe-delimited organism keys. One manifest can be active at a time.

## Build and submit commands

Sync fastq samples before planning commands for them.

~~~http
POST /api/samples/sync/
~~~

Plan commands without writing queue entries:

~~~http
POST /api/queue/plan/
{"batch_name_from_vendor": "MTX-22068"}
~~~

The plan returns the stage due for each fastq sample and the exact command. It skips a fastq
sample when ingest is incomplete, the stage is already complete, alignment is in progress, or
the library prep has no command in the manifest.

Confirm a plan and create queue entries:

~~~http
POST /api/queue/
{"batch_name_from_vendor": "MTX-22068"}
~~~

The planner reads the vendor batch prefix to select a modality. If the prefix has no workflow,
the response lists the available modalities and the request must include one:

~~~json
{
  "batch_name_from_vendor": "ZZZ-1",
  "modality": "MTX"
}
~~~

The planner builds an ingest command only after fastq sample ingest is complete. It builds an
alignment command only after ingest is complete. It builds a post-alignment command only after
alignment is complete.

The submission form lets a user change the reference, chemistry, probe set, command options,
or command text for one fastq sample. OmicsHub plans the command again before it creates the
queue entry. It rejects invalid command input before submission.

## Dashboard pages

| URL | Action |
|---|---|
| / | Sync a vendor batch, filter fastq samples, and add samples to the cart. |
| /checkout/ | Review samples, select the manifest, and review commands. |
| /queue/ | View and cancel pending queue entries. |
| /jobs/ | View submitted, failed, and stranded jobs. |
| /settings/ | Upload and activate a workflow manifest as a staff user. |

The cart is stored in PostgreSQL. It is not session data, so a selection survives logout and
can contain fastq samples added during separate visits.

## API endpoints

| Method | Path | Action |
|---|---|---|
| GET | /api/samples/ | List and filter fastq samples. |
| POST | /api/samples/sync/ | Load a vendor batch or named fastq samples from OCS. |
| POST | /api/queue/plan/ | Return a command plan without creating queue entries. |
| POST | /api/queue/ | Create queue entries from a confirmed plan. |
| GET | /api/queue/ | Return the signed-in user's queue entries. Staff users can view all entries. |
| POST | /api/queue/{id}/cancel/ | Cancel a pending queue entry. |
| GET/POST | /api/configs/ | List or upload workflow manifests as a staff user. |
| POST | /api/configs/{id}/activate/ | Activate a workflow manifest as a staff user. |

## Celery workers and submission limits

The submission task claims one queue entry, checks the OCS in-flight demand count, sends one
ocs command, records the demand ID, and schedules the next submission.

The submissions queue must run one worker process with concurrency one. This protects the
OCS job limit and the manifest spacing value.

~~~bash
celery -A omicshub worker -Q submissions -c 1 --hostname=submissions@%h
celery -A omicshub worker -Q default -c 4
celery -A omicshub beat
~~~

The Docker Compose stack starts these processes for you. Do not scale worker-submissions.

If a worker stops after it claims a queue entry but before it records the OCS demand ID, the
entry stays in SUBMITTING. After 30 minutes, the reconcile task moves it to STRANDED.
Check OCS before moving a stranded entry back to PENDING. OmicsHub does not retry a failed or
timed-out ocs process automatically because the command may have reached OCS.

## Readiness and troubleshooting

The readiness endpoint returns 200 when these dependencies are ready:

- PostgreSQL
- Redis
- A Celery worker consuming the submissions queue
- An active workflow manifest

It returns 503 and names the missing dependency when the app cannot submit jobs.

~~~bash
curl http://127.0.0.1:8001/healthz/
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f web_ui
docker compose --env-file .env.docker logs -f worker-submissions
~~~

If the browser says it cannot reach the site, check that the dashboard container is running and use
HTTP on the configured port. If the dashboard shows an OCS error after Refresh, the last local
sync remains visible while the app reports that the AWS pull failed.

## Data and backups

The sample and stage status tables are an OCS mirror. A new sync can rebuild them. Users,
workflow manifests, cart items, and queue entries are stored only in PostgreSQL.

Create a database backup before replacing the PostgreSQL volume:

~~~bash
docker exec omicshub-postgres pg_dump -U omicshub omicshub > omicshub-$(date +%F).sql
~~~

Do not run docker compose down -v unless you intend to delete the local PostgreSQL volume.

## Expose the app through a private tunnel

The app can submit real OCS jobs. Keep any forwarded URL private.

Before using a VS Code port tunnel:

1. Add the tunnel host to ALLOWED_HOSTS in .env.docker.
2. Add the tunnel's HTTPS origin to CSRF_TRUSTED_ORIGINS.
3. Set ADMIN_URL to a path other than /admin/.
4. Use private tunnel visibility.

The tunnel must terminate HTTPS. The Docker dashboard container can continue serving HTTP on its
local port.

## Start the stack at macOS login

deploy/launchd/ contains an optional macOS LaunchAgent. It waits for Docker Desktop and then
runs Docker Compose. It does not start Django or Celery directly.

Install it from the repository root:

~~~bash
sed "s|__OMICSHUB_DIR__|$PWD|g" deploy/launchd/org.alleninstitute.omicshub.stack.plist \
  > ~/Library/LaunchAgents/org.alleninstitute.omicshub.stack.plist
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/org.alleninstitute.omicshub.stack.plist
~~~

Run or stop it manually:

~~~bash
launchctl kickstart -p gui/$UID/org.alleninstitute.omicshub.stack
launchctl bootout gui/$UID/org.alleninstitute.omicshub.stack
~~~

## Local development and tests

The production app runs in Docker. Sync the development dependencies from `uv.lock` for local checks:

~~~bash
uv sync --group dev
~~~

Run formatting, linting, type checking, and tests:

~~~bash
uv run ruff format .
uv run ruff check .
uv run mypy apps/sample_catalog/models.py apps/workflow_engine/models.py apps/submission_queue/models.py \
  apps/ocs_integration/cli.py scripts/healthcheck.py
uv run pytest -W error
~~~

The tests use PostgreSQL. They replace the DynamoDB client and ocs process with test fakes,
so the test suite does not contact AWS or submit jobs.

## Release checks

Read RELEASE.md before a release. It lists the required environment variables, the process
restart order, the queue worker limit, migration risks, backup steps, and checks after the
release.
