# OmicsHub

OmicsHub mirrors OCS Fastq metadata and stage status from DynamoDB into PostgreSQL. It lets
authorized users browse the catalog, locate data in S3, build OCS commands, and submit
alignment and post-alignment work.

The active workflow configuration defines the batch prefixes included in the catalog and the
commands that can be planned and submitted.

## Choose an environment

| Environment | Purpose | Command |
| --- | --- | --- |
| Test | Isolated Django and browser tests | `docker_tools/test.sh` |
| Staging | Production-equivalent deployment before release | `docker_tools/setup_docker.sh staging` |
| Production | Live deployment | `docker_tools/setup_docker.sh production` |

## First-time setup

### Requirements

Install the following on the machine where you will run OmicsHub:

- Docker Desktop, or Docker Engine with the Compose plugin
- Git
- AWS CLI, for staging and production only
- [uv](https://docs.astral.sh/uv/), for tests and code checks only

You also need an AWS profile that can read the OCS DynamoDB tables, read registered S3 data
locations, and submit OCS demands. The test suite does not use your AWS account.

### Clone

```bash
git clone https://github.com/beagan-svg/OmicsHub.git omicshub
cd omicshub
```

### Create an OmicsHub AWS profile

Skip this section when running tests. For staging or production, store the application profile
outside the repository:

```bash
mkdir -p ~/.omicshub
chmod 700 ~/.omicshub
AWS_SHARED_CREDENTIALS_FILE=~/.omicshub/credentials aws configure --profile omicshub
```

The AWS CLI creates the credentials file with owner-only access. The directory permission keeps
the credential file private. Use temporary credentials or an approved role where your AWS setup
supports them.

The profile needs access to these DynamoDB tables, using the value of `OCS_ENV_BASE` as the
prefix:

- `<env>-fastq-metadata`
- `<env>-fastq-history`
- `<env>-demand-registry`
- `<env>-file-store`

It also needs `dynamodb:BatchGetItem`, `s3:ListBucket`, and `s3:GetObject` for registered data
locations, plus the permissions required by the `ocs` CLI to submit demands.

## Test

From the repository root, run:

```bash
docker_tools/test.sh
```

This single command installs the locked development dependencies, installs Chromium, starts a
temporary PostgreSQL 16 container, runs the Django and browser tests, then removes the temporary
container. Django creates and drops its own test database inside that PostgreSQL container. Test
settings use fake OCS clients and an in-memory Celery broker, so the suite cannot read staging or
production data or submit OCS jobs.

To run the static checks used in CI:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy apps omicshub docker_tools
```

## Deploy staging or production

Run deployments from a separate staging or production host. Each environment must have its own
`.env.docker`, PostgreSQL volume, Redis services, AWS profile, and OCS environment.

1. Run the setup command once. It creates `.env.docker` from `.env.docker.example` and stops.

   ```bash
   docker_tools/setup_docker.sh staging
   # or
   docker_tools/setup_docker.sh production
   ```

2. Edit `.env.docker`. At minimum, set these values:

   ```dotenv
   SECRET_KEY=replace-with-a-long-random-value
   POSTGRES_PASSWORD=replace-with-a-database-password
   CREDENTIAL_ENCRYPTION_KEY=replace-with-a-fernet-key
   AWS_CREDENTIALS_FILE=/absolute/path/to/.omicshub/credentials
   AWS_PROFILE=omicshub
   OCS_ENV_BASE=prod
   OCS_AWS_REGION=us-west-2
   ALLOWED_HOSTS=localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=
   ```

   Use an absolute `AWS_CREDENTIALS_FILE` path. Docker Compose does not expand `~` in bind-mount
   paths. Generate `CREDENTIAL_ENCRYPTION_KEY` with the command in `.env.docker.example`.

3. Run the same setup command again. It prepares the pinned OCS packages, validates the Compose
   configuration, builds the image, applies migrations, and starts the stack.

4. Upload and activate a workflow configuration from `/configs/`, then populate the configured
   catalog immediately instead of waiting for the nightly metadata sync:

   ```bash
   docker compose --env-file .env.docker exec -T catalog-sync-worker \
     python manage.py sync_all_samples
   ```

   Catalog synchronization reads Fastq metadata for the active configuration's batch prefixes.
   It removes samples that are outside that scope unless they have queue history.

The catalog worker refreshes stage status every five minutes and runs the full metadata sync at
03:00 daily. An active workflow configuration is required for catalog synchronization, command
planning, and submission.

### Production ingress

Compose binds PostgreSQL, Redis, and the web application to loopback addresses. Put a public
production deployment behind an HTTPS reverse proxy or WAF. Before exposing it, set real
`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, change `ADMIN_URL`, and set these values to `True`:

```dotenv
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

The proxy must remove client-supplied forwarded headers and set `X-Forwarded-Proto` itself.
OmicsHub submits real OCS jobs, so do not expose a deployment through a public development tunnel.

## Use the running application

Open the local deployment at:

```text
http://127.0.0.1:8001/
```

Use the `WEB_PORT` value from `.env.docker` if you changed the default port.

| Page | Purpose |
| --- | --- |
| `/` | Browse and filter the catalog, then add samples to the cart. |
| `/checkout/` | Review samples, select a workflow configuration, and review commands. |
| `/queue/` | View and cancel pending submissions. |
| `/data-locations/` | Browse registered S3 locations and download selected files. |
| `/monitor/` | View running and recently finished OCS work. |
| `/timeline/` | View catalog stages by week, month, or year. |
| `/failed/` | Retry or delete your failed submissions. |
| `/configs/` | Staff-only workflow configuration upload and activation. |

Workflow configurations contain command templates, references, library-prep matches, OCS job
limits, and submission spacing. Upload and activate them from `/configs/`. The repository
example at `workflow_manifests/workflow_manifest.jsonc` is a starting point only. Editing that
file does not change the active database configuration.

## Operations

Check the application:

```bash
docker compose --env-file .env.docker ps
curl -fsS http://127.0.0.1:8001/healthz/
```

The health endpoint checks PostgreSQL, the cache, the Celery broker, and the submission-worker
heartbeat. It reports missing workflow configuration without marking the application unhealthy.

View logs:

```bash
docker compose --env-file .env.docker logs -f web-ui
docker compose --env-file .env.docker logs -f catalog-sync-worker
docker compose --env-file .env.docker logs -f ocs-submission-worker
```

Stop the stack while retaining PostgreSQL data:

```bash
docker compose --env-file .env.docker down
```

Restart or redeploy the stack from [RELEASE.md](RELEASE.md#deploying). It covers the
pre-restart check for an in-flight OCS submission, the restart order, and the health checks to
run afterward.

Do not add a second `ocs-submission-worker` or increase its concurrency. One worker with
concurrency one is required to respect OCS capacity and configured submission spacing.

## Back up PostgreSQL

The catalog can be refreshed from OCS, but users, workflow configurations, carts, and queue
entries exist only in PostgreSQL. Back up the database before replacing its volume:

```bash
docker compose --env-file .env.docker exec -T postgres \
  pg_dump -U omicshub -d omicshub > omicshub-$(date +%F).sql
```

Do not run `docker compose down -v` unless you intend to delete the PostgreSQL volume.

## Project layout

| Directory | Responsibility |
| --- | --- |
| `apps/sample_catalog/` | Catalog models and OCS metadata/status synchronization. |
| `apps/ocs_integration/` | DynamoDB, S3, and OCS CLI boundaries. |
| `apps/submission_queue/` | Command planning, queueing, and submission tasks. |
| `apps/workflow_engine/` | Workflow configuration parsing, validation, and command building. |
| `apps/web_ui/` | Server-rendered pages, templates, static assets, and browser tests. |
| `omicshub/` | Django settings, URLs, Celery setup, health checks, middleware, and logging. |
| `docker_tools/` | Test and deployment scripts, health checks, and OCS package preparation. |

Read [RELEASE.md](RELEASE.md) before a release. It covers deployment order, queue safety,
migration risks, backups, and post-deployment checks.
