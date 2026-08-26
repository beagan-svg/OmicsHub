# OmicsHub

OmicsHub loads fastq sample data from OCS, shows each sample's stage status, builds OCS
commands, and sends alignment and post-alignment commands.

The dashboard stores fastq samples, stage statuses, workflow manifests, users, and queue
entries in PostgreSQL. Celery sends task messages through Redis. One submission worker sends
commands through the ocs CLI.

## Start the app with Docker

Docker starts PostgreSQL, Redis, Django, two Celery workers, Celery Beat, and the ocs CLI
from one OmicsHub image.

### Requirements

Install these tools on the machine that will run OmicsHub:

- Docker Desktop, or Docker Engine with the Docker Compose plugin
- Git
- AWS CLI
- An AWS profile that can read the OCS DynamoDB tables and submit OCS demands

The app reads AWS credentials from the credentials file you specify. It does not read access
keys from .env.docker. Compose runs separate Redis containers for task messages and cache data.

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

Create a credentials file for OmicsHub. Store it outside the repository and outside the
machine-wide ~/.aws/credentials file.

~~~bash
mkdir -p ~/.omicshub
chmod 700 ~/.omicshub
AWS_SHARED_CREDENTIALS_FILE=~/.omicshub/credentials aws configure --profile omicshub
chmod 600 ~/.omicshub/credentials
~~~

Give the AWS profile access to these tables. The `<env>` value comes from `OCS_ENV_BASE`:

- <env>-fastq-metadata
- <env>-fastq-history
- <env>-demand-registry
- <env>-file-store

Give the same profile permission to send alignment and post-alignment demands through the
`ocs` CLI.

### Create the Docker settings

Run the setup command from the repository root:

~~~bash
docker_tools/setup_docker.sh
~~~

The first run copies `.env.docker.example` to `.env.docker` and stops. Open `.env.docker`
and set these values:

~~~dotenv
SECRET_KEY=replace-with-a-long-random-value
POSTGRES_PASSWORD=replace-with-a-database-password
CREDENTIAL_ENCRYPTION_KEY=replace-with-a-fernet-key
AWS_CREDENTIALS_FILE=/Users/you/.omicshub/credentials
AWS_PROFILE=omicshub
OCS_ENV_BASE=prod
OCS_AWS_REGION=us-west-2
~~~

Set `AWS_CREDENTIALS_FILE` to an absolute path. Docker Compose does not expand `~` in a
bind-mount path. Keep `.env.docker` out of Git.

Run the setup command again:

~~~bash
docker_tools/setup_docker.sh
~~~

The script checks the settings, downloads the pinned genomics-cloud-services revision into
vendor/gcs/, builds the Docker image, and starts the stack. It waits for the dashboard health
check before it exits.

Set GCS_SRC to reuse a local genomics-cloud-services Git checkout that contains the pinned
revision:

~~~bash
GCS_SRC=/path/to/genomics-cloud-services docker_tools/setup_docker.sh
~~~

The script exports gcs-core, gcs-api-client, gcs-docker-tools, and gcs-cli from the pinned
revision. Local edits in the external checkout are not copied into the image.

### Open the dashboard

Open this URL in a browser:

~~~text
http://127.0.0.1:8001/
~~~

Docker serves plain HTTP on the local port. Use the `WEB_PORT` value from `.env.docker` if
you changed the port. Local HTTPS needs a TLS proxy and certificate, so
https://127.0.0.1:8001/ does not work with the default Docker settings.

Check the stack and view logs with these commands:

~~~bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f web-ui
docker compose --env-file .env.docker logs -f ocs-submission-worker
curl http://127.0.0.1:8001/healthz/
~~~

Stop the containers without deleting the database volume:

~~~bash
docker compose --env-file .env.docker down
~~~

Do not run docker compose down -v unless you intend to delete the PostgreSQL volume.

## Docker containers and data flow

Docker Compose starts eight containers: five from the OmicsHub image, one PostgreSQL
container, and two Redis containers. The migration container exits after applying migrations.

~~~text
                           Docker Compose
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
   PostgreSQL              Redis broker              Redis cache
    pgdata volume           Celery tasks              Holds and cache
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                │
                            migration
                                │
               ┌────────────────┼────────────────┐
               │                │                │
            web-ui          Celery Beat        workers
         Django/Gunicorn   Scheduled tasks   sync and submission
~~~

The browser connects to the web container through the host port:

~~~text
Browser → http://127.0.0.1:8001 → web-ui:8000 → PostgreSQL
                                      │
                                      ├── redis-broker
                                      └── redis-cache
~~~

The `WEB_PORT` value in `.env.docker` sets the host port. The container listens on port 8000.

### Image build

`Dockerfile` builds `omicshub:local` in two stages. The build stage installs the locked Python
dependencies and the OCS packages from `vendor/gcs/`. The second stage copies the virtual
environment and application into a smaller Python image and runs as the non-root `app` user.

The image does not contain `.env.docker` or AWS credentials. `.dockerignore` removes those files
from the build context. Compose mounts the host credentials file read-only at
`/run/aws/credentials` in the web and AWS worker containers.

### Container startup

The migration and web containers run these commands in order:

~~~text
migration: python manage.py migrate
        ↓
web-ui: python manage.py collectstatic
        ↓
web-ui: gunicorn omicshub.wsgi:application
~~~

`collectstatic` copies CSS and JavaScript from the app static directories into
`/app/staticfiles/`. Gunicorn serves the application from the web container.

Compose starts PostgreSQL and both Redis services first. The migration container runs after
those services pass their health checks. The web process, workers, and Celery Beat start only
after migrations succeed. The web health check then checks PostgreSQL, the cache, the Celery
broker, the submission-worker heartbeat, and the active workflow manifest.

### Data flows

Catalog data follows this path:

~~~text
Celery Beat → Redis broker → catalog-sync-worker
                                  │
                                  ├── reads OCS DynamoDB
                                  └── writes PostgreSQL
                                             │
                                             ▼
                                          web-ui
~~~

Submission data follows this path:

~~~text
User confirms a command
        ↓
web-ui writes QueueEntry to PostgreSQL
        ↓
Celery task → Redis broker → ocs-submission-worker
                                      │
                                      ├── runs the ocs CLI
                                      ├── receives a demand ID
                                      └── saves the result in PostgreSQL
~~~

The dashboard reads sample and queue data from PostgreSQL. Celery workers pull AWS data on the
schedule in the Celery settings. When a user opens a Data Locations entry, OmicsHub reads its
file-store record and lists the S3 contents.

Celery Beat publishes the regular queue task. After a successful submission, the submission
worker schedules another task after the manifest spacing value. Redis stores spacing and
capacity holds, so a task returns without sending a command when another task arrives too soon.

## How OmicsHub reads OCS data

The app keeps OCS access in `apps/ocs_integration/`.

`apps/ocs_integration/dynamodb.py` reads these DynamoDB tables:

| Table | Use |
|---|---|
| <env>-fastq-metadata | Load fastq sample metadata. |
| <env>-fastq-history | Load the stage history for each fastq sample. |
| <env>-demand-registry | Load demand status and count IN_PROGRESS demands. |
| <env>-file-store | Resolve a file-store ID to its current S3 location. |

`apps/ocs_integration/cli.py` runs the `ocs` command for submissions. The Celery submission
worker passes the AWS profile from the environment to that process.

The application AWS profile also needs `dynamodb:BatchGetItem` for the file-store table and
`s3:ListBucket` and `s3:GetObject` for the registered file-store buckets.

Set `OCS_ENV_BASE=prod` to read tables such as `prod-fastq-metadata`. Change this value before
connecting to another OCS environment.

The dashboard stores the last successful OCS sync time in PostgreSQL. A `Synced` label means
the last AWS status pull completed. OCS and PostgreSQL can still differ until the next sync.

## Project layout

Read docs/PROJECT_MAP.md for the directory ownership map:

| Directory | Contains |
|---|---|
| apps/accounts/ | Custom user model, login, signup, and account admin. |
| apps/sample_catalog/ | Fastq samples, stage statuses, OCS synchronization, and sample API endpoints. |
| apps/ocs_integration/ | DynamoDB reads and the ocs CLI submission code. |
| apps/submission_queue/ | Queue models, planning, round-robin claiming, Celery tasks, and queue API endpoints. |
| apps/workflow_engine/ | Workflow manifest parsing, validation, modality selection, and command building. |
| apps/web_ui/ | Server-rendered pages, forms, templates, CSS, static assets, Data Locations queries, and browser tests. |
| omicshub/ | Django settings, URLs, Celery setup, health checks, middleware, and logging. |
| docker_tools/ | Docker setup, container health checks, and OCS package preparation. |
| deploy/launchd/ | Optional macOS startup files for Docker Desktop. |
| workflow_manifests/ | Example JSONC workflow manifests. |
| vendor/gcs/ | Pinned OCS package source prepared before a Docker build. It is generated build input, not app code. |

## Workflow manifests

A workflow manifest tells OmicsHub how to build commands. It contains command templates,
references, chemistries, probe sets, modality settings, the OCS job limit, submission
spacing, and the status labels that mark a stage complete.

The repository example is:

~~~text
workflow_manifests/workflow_manifest.jsonc
~~~

Use the file as an example. The database stores the manifest used to build commands. Editing the
file does not change that manifest until a staff user uploads and activates it.

Check a manifest before activating it:

~~~bash
docker compose --env-file .env.docker exec web-ui \
  python manage.py check_config_coverage workflow_manifests/workflow_manifest.jsonc
~~~

The command checks whether the manifest can build commands for fastq samples in PostgreSQL.

Staff users upload and activate manifests from `/configs/`. The API uses Django session
authentication and CSRF protection. It does not accept bearer tokens.

OmicsHub checks the JSONC file before storing it. The parser removes comments and expands
pipe-delimited organism keys. The database uses one active manifest at a time.

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

The plan returns the next stage and exact command for each fastq sample. It skips a fastq
sample when ingest is incomplete, the stage is complete, alignment is already running, or the
library prep has no command in the manifest.

Confirm a plan and create queue entries:

~~~http
POST /api/queue/
{"batch_name_from_vendor": "MTX-22068"}
~~~

The planner reads the vendor batch prefix to select a modality. If the prefix has no workflow,
the response lists the available modalities, and the request must include one:

~~~json
{
  "batch_name_from_vendor": "ZZZ-1",
  "modality": "MTX"
}
~~~

The planner builds an alignment command only after fastq sample ingest is complete. It builds a
post-alignment command only after alignment is complete.

The submission form lets a user change the reference, chemistry, probe set, command options,
or command text for one fastq sample. OmicsHub plans the command again before it creates the
queue entry. It rejects invalid command input before sending the command.

## Dashboard pages

| URL | Action |
|---|---|
| / | Sync a vendor batch, filter fastq samples, and add samples to the cart. |
| /checkout/ | Review samples, select the manifest, and review commands. |
| /queue/ | View and cancel pending queue entries. |
| /data-locations/ | View file-store and S3 locations and download selected files. |
| /jobs/ | View running and recently finished jobs. |
| /failed/ | Retry or delete this user's failed submissions and running failures. |
| /configs/ | Upload and activate a workflow manifest as a staff user. |

The cart is stored in PostgreSQL. A selection survives logout and can contain fastq samples
added during separate visits.

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
`ocs` command, records the demand ID, and schedules the next submission.

Run one worker process with concurrency one for the submissions queue. This keeps submissions
within the OCS job limit and the manifest spacing value.

~~~bash
celery -A omicshub worker -Q ocs-submissions -c 1 --hostname=ocs-submissions@%h
celery -A omicshub worker -Q catalog-sync -c 4 --hostname=catalog-sync@%h
celery -A omicshub beat
~~~

The Docker Compose stack starts these processes for you. Do not scale ocs-submission-worker.

If the `ocs` command does not return `SUBMITTED` with a demand ID, OmicsHub records the entry as
FAILED. A user can retry it from the Failures page.

## Readiness and troubleshooting

The readiness endpoint checks these services and records:

- PostgreSQL
- Redis
- A Celery worker consuming the ocs-submissions queue
- An active workflow manifest, reported as `workflow_config`

It returns 503 when PostgreSQL, Redis, the broker, or the submissions-worker heartbeat is
unavailable. It reports a missing workflow manifest without returning 503.

~~~bash
curl http://127.0.0.1:8001/healthz/
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f web-ui
docker compose --env-file .env.docker logs -f ocs-submission-worker
~~~

If the browser cannot reach the site, check that the web container is running and use HTTP on
the port in `.env.docker`. If an AWS sync fails, the page keeps showing the last local data and
reports the sync error.

## Data and backups

The sample and stage status tables mirror OCS data. A new sync can rebuild those tables. Users,
workflow manifests, cart items, and queue entries exist only in PostgreSQL.

Create a database backup before replacing the PostgreSQL volume:

~~~bash
docker compose --env-file .env.docker exec -T postgres \
  pg_dump -U omicshub -d omicshub > omicshub-$(date +%F).sql
~~~

Do not run docker compose down -v unless you intend to delete the local PostgreSQL volume.

## Expose the app through a private tunnel

The app can submit real OCS jobs. Keep the forwarded URL private.

Before using a VS Code port tunnel:

1. Add the tunnel host to ALLOWED_HOSTS in .env.docker.
2. Add the tunnel's HTTPS origin to CSRF_TRUSTED_ORIGINS.
3. Set ADMIN_URL to a path other than /admin/.
4. Use private tunnel visibility.

The tunnel must terminate HTTPS. The Docker dashboard container can keep serving HTTP on its
local port.

## Start the stack at macOS login

`deploy/launchd/` contains an optional macOS LaunchAgent. It waits for Docker Desktop and then
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

The production app runs in Docker. Sync the development dependencies and install Chromium
for local checks:

~~~bash
uv sync --group dev
uv run playwright install chromium
~~~

Start an isolated PostgreSQL test database and point Django at it:

~~~bash
docker run -d --rm --name omicshub-test-postgres \
  -e POSTGRES_USER=omicshub -e POSTGRES_PASSWORD=omicshub -e POSTGRES_DB=omicshub \
  -p 127.0.0.1:55432:5432 postgres:16
export DATABASE_URL=postgres://omicshub:omicshub@127.0.0.1:55432/omicshub
~~~

Run formatting, linting, type checking, and tests:

~~~bash
uv run --group dev ruff format .
uv run --group dev ruff check .
uv run --group dev mypy apps omicshub docker_tools
uv run --group dev pytest -q --ignore=apps/web_ui/tests/playwright
DJANGO_ALLOW_ASYNC_UNSAFE=true uv run --group dev pytest -q apps/web_ui/tests/playwright
~~~

The tests use PostgreSQL. They replace the DynamoDB client and ocs process with test fakes,
so the test suite does not contact AWS or submit jobs.

Stop the test database after the checks finish:

~~~bash
docker stop omicshub-test-postgres
~~~

## Release checks

Read RELEASE.md before a release. It lists the required environment variables, the process
restart order, the queue worker limit, migration risks, backup steps, and checks after the
release.
