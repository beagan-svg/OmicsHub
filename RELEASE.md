# Releasing OmicsHub

A release updates the web process, two Celery workers, and Celery Beat. They use one PostgreSQL
database and separate Redis broker and cache services. A one-shot container applies migrations
before the application processes start. The web process runs `collectstatic` before Gunicorn.

Use these steps for the Compose stack. Run every application process in Docker.

## Environment

The app reads the variables listed below from `env(...)` calls in `omicshub/settings/`.

These have no default in the production settings. `django-environ` raises
`ImproperlyConfigured` when a required value is missing, so the web process and workers
cannot start with an incomplete environment.

| Variable | Source | Meaning |
|---|---|---|
| `SECRET_KEY` | base | rotating it signs every user out |
| `DATABASE_URL` | base | full URL, e.g. `postgres://user:pw@host:5432/omicshub` |
| `OCS_ENV_BASE` | base | prefixes every DynamoDB table name; `prod` means the real account |
| `OCS_AWS_REGION` | base | |
| `CELERY_BROKER_URL` | base | |
| `CACHE_URL` | prod | Redis endpoint for application cache data |
| `CREDENTIAL_ENCRYPTION_KEY` | base | Fernet key for temporary log-viewer credentials |
| `ALLOWED_HOSTS` | prod | comma-separated; no default in prod, unlike dev |
| `CSRF_TRUSTED_ORIGINS` | prod | with scheme, or every POST from the tunnel fails CSRF |

These settings have defaults:

| Variable | Default | Meaning |
|---|---|---|
| `CACHE_KEY_PREFIX` | `omicshub` | Prefix for keys written by this deployment. |
| `CACHE_TIMEOUT` | `300` | Default cache lifetime in seconds. |
| `OCS_CLI_PATH` | `ocs` | the executable used for alignment and post-alignment submissions |
| `AWS_PROFILE` | empty | boto3 uses its normal credential chain when no profile is set |
| `AWS_SHARED_CREDENTIALS_FILE` | empty | the app-scoped credentials file; see the README |
| `OCS_CLI_TIMEOUT` | `300` | seconds for one `ocs` call |
| `CONN_MAX_AGE` | `60` | seconds a database connection is reused |
| `LOG_VIEWER_CREDENTIAL_TTL_SECONDS` | `18000` | maximum cache lifetime for temporary log credentials |
| `SENTRY_DSN` | empty | enables Sentry when set |
| `SENTRY_RELEASE` | `GIT_SHA` or empty | source revision reported to Sentry |
| `ENVIRONMENT` | `production` | deployment name reported to Sentry |
| `STAGE_STATUS_SYNC_SECONDS` | `300` | how often the stage-status sweep runs |
| `ADMIN_URL` | `admin` | the path where Django mounts the admin |
| `DEBUG` | `False` | production settings keep debug pages off |

Compose reads `.env.docker` only when `--env-file .env.docker` is passed. That file carries
`POSTGRES_PASSWORD`, `AWS_CREDENTIALS_FILE`, and the host-side port numbers. Compose sets
`DATABASE_URL`, `CELERY_BROKER_URL`, `CACHE_URL`, and the container's `OCS_CLI_PATH`.
Compose keeps the broker and cache on separate Redis services. The host ports are only
bound to loopback for local inspection and should not be opened on a public host.

`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are not on either list and must not be
added. The app resolves credentials through boto3 from a profile.

### The admin path

The admin can edit users, read every queue entry, and activate a manifest. Set `ADMIN_URL`
to mount the admin at another path:

```
ADMIN_URL=bicore-ops
```

Keep the default `admin/` for local development. The navigation link and tests use
`reverse("admin:index")`, so set `ADMIN_URL` without changing code. A wrong value produces
a 404 for the admin path.

## Deploying

Before restarting, check that no entry is mid-submission. A restart during an `ocs` call can
leave the local entry in `SUBMITTING`, so stop the submission worker only after the current
call finishes:

```bash
docker compose --env-file .env.docker exec web-ui python manage.py shell -c "
from apps.submission_queue.models import QueueEntry
print(QueueEntry.objects.filter(status='SUBMITTING').count())"
```

The command prints zero when no submission is in flight. If it is not zero, wait for the
current `ocs` call to finish. The next entry is claimed only after the previous entry's
spacing period.

Then run the setup command. It prepares the OCS packages, validates the environment, and
starts the full stack.

```bash
docker_tools/setup_docker.sh
```

The Compose migration service exits successfully before the web process, workers, or Beat
start. The web process then runs `collectstatic` before Gunicorn binds. Outside Compose, run
these commands in order from one host:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Then restart the application processes. Compose enforces the migration dependency.

1. **`web-ui`**: serves the pages and API.
2. **`catalog-sync-worker`**: runs the scheduled synchronization tasks. Restarting it mid-sweep is safe;
   the sweep is idempotent and the next tick redoes it.
3. **`ocs-submission-worker`**: one process with `--concurrency 1`, after the
   `SUBMITTING` count above is zero.
4. **`celery-scheduler`**: restart it whenever `CELERY_BEAT_SCHEDULE` changes. Beat keeps its
   own schedule file; an unrestarted beat goes on firing the old schedule and will not
   pick up a new task or a changed interval.

Workers do not reload code. Restart both workers after a task changes, or they continue
running the old task code.

### The submissions worker stays at one process

```
ocs-submission-worker   replicas: 1   --concurrency 1
```

Keep this as a fixed deployment setting. The OCS job limit and the `spacing` between submissions
are enforced by the worker being the only thing submitting: it checks the in-flight count,
claims one entry, submits it, and schedules the next run. Two processes, or one process
with two threads, both pass that check at the same moment with the same answer.

Running two submission processes creates two `ocs` demands for the same sample and stage.
That duplicates the alignment, burns production compute, and creates two output sets. The database constraint
(`one_pending_entry_per_sample_stage`) does not save you: it covers `PENDING` entries, and
both copies have already moved theirs to `SUBMITTING`.

If the queue is too slow, lower `spacing` in the config. Do not scale the worker.

## Migrations that need care

`apps/sample_catalog/migrations/0009_stagestatus_catalog_sta_stage_c0b808_idx.py` adds an
index to `catalog_stagestatus` with a regular `AddIndex`. Review the lock time for this
operation before applying it to a large production table.

Review future migrations for table rewrites and locks on tables written by the scheduled
status synchronization.

## Rolling back

Roll back code first when a release causes the incident described below.

Rolling a **migration** back is a separate decision and usually the wrong one. Reversing
`0009` drops an index, which is harmless; reversing a column addition drops the column and
everything in it. Check what `migrate <app> <previous>` intends to do before running it.

Do not roll back a submission. The queue holds demands that have already reached OCS: a
`SUBMITTED` entry means a job is running in production, and
reverting this app to yesterday's code, or restoring yesterday's database, does not recall
it. Restoring a database backup causes a second problem because it reinstates entries as
`PENDING` that OCS has already accepted, and the worker will submit them again.

Review migrations before rolling them back. Do not roll back the queue table without first
checking the OCS demand state.

## After the deploy

### Session cleanup and public ingress

Run Django's standard session cleanup command once a day:

```bash
docker compose --env-file .env.docker exec -T web-ui python manage.py clearsessions
```

Schedule this from the host or cloud scheduler. Do not create a second application task for
it. Public traffic should reach `web-ui` through an HTTPS reverse proxy or WAF. Apply login
and signup rate limits there, keep PostgreSQL and both Redis services private, and allow only
ports 80 and 443 from the internet.

Set `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, and the real HTTPS origins in
the production environment. `SECURE_PROXY_SSL_HEADER` is valid only when the reverse proxy
removes untrusted forwarded headers and sets `X-Forwarded-Proto` itself.

Run these checks after the stack starts.

1. **Readiness.**

   ```bash
   curl -fsS http://127.0.0.1:8001/healthz/
   ```

   Expect `{"status": "ok", ...}`. A 503 names the failing check: `database`, `cache`,
   `broker`, or `submissions_worker` (`workflow_config` is reported but does not gate
   readiness). `submissions_worker` is the check most likely to fail after a deploy because
   it reads a heartbeat the submission task refreshes on every run. The heartbeat goes stale
   if the scheduler is down, the broker is not delivering, or nothing is consuming `ocs-submissions`.
   These failures queue jobs that never reach OCS while every page still
   renders.

   A newly restarted stack may need one scheduler tick before the OCS submission worker heartbeat
   is fresh. The Compose healthcheck has a start period for this startup window.

2. **A sweep completing in the worker log.** Within `STAGE_STATUS_SYNC_SECONDS` seconds of
   the restart, five minutes by default:

   ```bash
   docker compose --env-file .env.docker logs --since 10m catalog-sync-worker \
     | grep sync_all_stage_statuses
   ```

   Expect a `succeeded` line. `Stage-status sweep still running; skipping this tick`
   repeated every tick means a previous sweep is stuck holding the lock. No output means
   beat is not firing. Restart it.

3. **The dashboard staleness indicator.** Open `/`. The stage-status timestamp should be
   under three sweep intervals old and not flagged stale. This is the end-to-end check
   that the worker, the cache and OCS all work together, which the health endpoint cannot
   tell you.

4. **The queue and monitor pages.** Open `/queue/`, `/jobs/`, and `/failed/`. Confirm that
   they render and that existing entries retain their states.

## When a submission fails

The worker records a submission as `SUBMITTED` only when `ocs` returns a successful response
with a demand id. A non-zero exit, timeout, unreadable response, or missing executable marks
the entry `FAILED` and preserves the error for retry from the Failures page. A submission
that reaches OCS and later fails is read from the demand registry and appears in the
running-failures section with its demand ID.

If a worker is restarted while an `ocs` call is still running, inspect the worker log and OCS
before retrying the local `SUBMITTING` entry. The command may have reached OCS even though the
process did not return a demand id. Do not submit it again blindly because that can duplicate
the alignment. Once the outcome is known, update or retry the entry through the normal queue
workflow.
