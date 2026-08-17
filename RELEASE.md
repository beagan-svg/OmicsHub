# Releasing OmicsHub

A release updates five processes: the web process, the `submissions` worker, the `default`
worker, beat, and the migration process. All five use the same Postgres database, Redis
instance, and settings module. A missing setting stops all five processes. Restart them in
the order below because they hold different parts of an in-flight submission.

Use these steps for the Compose stack. Run every application process in Docker.

## Environment

The app reads the variables listed below from `env(...)` calls in `omicshub/settings/`.

These have **no default**. `django-environ` raises `ImproperlyConfigured` at import, so a
missing one is not a degraded service. The web process, both workers, and beat all exit
before they log anything about starting up.

| Variable | Read in | |
|---|---|---|
| `SECRET_KEY` | base | rotating it signs every user out |
| `DATABASE_URL` | base | full URL, e.g. `postgres://user:pw@host:5432/omicshub` |
| `OCS_ENV_BASE` | base | prefixes every DynamoDB table name; `prod` means the real account |
| `OCS_AWS_REGION` | base | |
| `CELERY_BROKER_URL` | base | |
| `ALLOWED_HOSTS` | prod | comma-separated; no default in prod, unlike dev |
| `CSRF_TRUSTED_ORIGINS` | prod | with scheme, or every POST from the tunnel fails CSRF |

These have defaults, but four of the defaults are wrong for anything but a laptop:

| Variable | Default | |
|---|---|---|
| `CACHE_URL` | `redis://localhost:6379/1` | **localhost**. Point this at the real Redis, or the submission worker's capacity hold is kept in an isolated cache. |
| `OCS_CLI_PATH` | `ocs` | the executable used for alignment and post-alignment submissions |
| `AWS_PROFILE` | empty | empty means boto3 falls back to environment variables and then the instance role, which is what you want on EC2/ECS and not what you want on a host |
| `AWS_SHARED_CREDENTIALS_FILE` | empty | the app-scoped credentials file; see the README |
| `OCS_CLI_TIMEOUT` | `300` | seconds for one `ocs` call |
| `CONN_MAX_AGE` | `60` | seconds a database connection is reused |
| `STAGE_STATUS_SYNC_SECONDS` | `300` | how often the stage-status sweep runs |
| `ADMIN_URL` | `admin` | the path the Django admin is mounted at , see below |
| `DEBUG` | `False` | production settings keep debug pages off |

Compose reads `.env.docker` only when `--env-file .env.docker` is passed. That file carries
`POSTGRES_PASSWORD`, `AWS_CREDENTIALS_FILE`, and the host-side port numbers. Compose sets
`DATABASE_URL`, `CELERY_BROKER_URL`, `CACHE_URL`, and the container's `OCS_CLI_PATH`.

`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are not on either list and must not be
added. The app resolves credentials through boto3 from a profile.

### The admin path

The admin can edit users, read every queue entry, and activate a manifest. `/admin/` is
the first path anything scanning the host will try. `ADMIN_URL` moves it:

```
ADMIN_URL=bicore-ops
```

Keep the default `admin/` for local development. The nav link and tests use
`reverse("admin:index")`, so set `ADMIN_URL` without changing code. A wrong value produces
a 404 for the admin path.

## Deploying

Before starting, check that no entry is mid-submission. An `ocs` call killed by a restart is
exactly how an entry becomes `STRANDED`, and a stranded entry costs a person twenty
minutes of checking OCS by hand:

```bash
docker compose --env-file .env.docker exec web python manage.py shell -c "
from apps.submission_queue.models import QueueEntry
print(QueueEntry.objects.filter(status='SUBMITTING').count())"
```

The command prints zero when no submission is in flight. If it is not zero, wait. A submission takes
seconds, and the next entry is only claimed after the previous one's `spacing`.

Then run the setup command. It prepares the OCS packages, validates the environment, and
starts the full stack.

```bash
scripts/setup_docker.sh
```

The compose `web` service runs `migrate` and then `collectstatic` before gunicorn binds,
from one container, so nothing races to apply the same migration. Off compose, run them
yourself, in this order, from one host:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Then restart, in this order:

1. **web** , it serves the pages and the API.
2. **`worker-default`** , the sweeps and the reconciler. Restarting it mid-sweep is safe;
   the sweep is idempotent and the next tick redoes it.
3. **`worker-submissions`** , one process, `--concurrency 1`. Last, and only once the
   `SUBMITTING` count above is zero.
4. **beat** , last, and *always* when `CELERY_BEAT_SCHEDULE` has changed. Beat keeps its
   own schedule file; an unrestarted beat goes on firing the old schedule and will not
   pick up a new task or a changed interval.

Workers do not reload code. Restart both workers after a task changes, or they continue
running the old task code.

### The submissions worker stays at one process

```
worker-submissions   replicas: 1   --concurrency 1
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

`apps/sample_catalog/migrations/0009_stagestatus_catalog_sta_stage_c0b808_idx.py` adds an index to
`catalog_stagestatus` with a plain `AddIndex`. Postgres takes an **ACCESS EXCLUSIVE lock on
the table for the whole time the index builds** , not a moment, the whole build. On this
table (roughly four rows per sample, so well into six figures) that is seconds to tens of
seconds, during which every read and write of `catalog_stagestatus` blocks: the dashboard,
the jobs page, and the stage-status sweep all wait, and the sweep will hit its time limit
if it waits long enough.

Run it in a quiet window. `AddIndexConcurrently` would avoid the lock but needs
`django.contrib.postgres` in `INSTALLED_APPS`, which this project does not have.

Everything else in `sample_catalog/` and `submission_queue/` to date is column additions and index
changes on small tables. Check any new migration against the same question before
shipping it: does it rewrite or lock a table the sweep writes to every five minutes?

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

Roll back code freely. Review migrations before rolling them back, and never roll back the
`queueing_queueentry` table on its own.

## After the deploy

Four checks, in this order. They are ordered so that the first one to fail tells you the
most.

1. **Readiness.**

   ```bash
   curl -fsS http://127.0.0.1:8001/healthz/
   ```

   Expect `{"status": "ok", ...}`. A 503 names the failing check: `database`, `cache`,
   `broker`, or `submissions_worker` (`workflow_config` is reported but does not gate
   readiness). `submissions_worker` is the check most likely to fail after a deploy because
   it reads a heartbeat the submission task refreshes on every run. The heartbeat goes stale
   if beat is down, the broker is not delivering, or nothing is consuming `submissions`.
   These failures queue jobs that never reach OCS while every page still
   renders.

   Give it a minute. No tick has landed immediately after a restart, so the first probe
   reports `no submission run in the last 5 minutes` and readiness is false until beat
   fires. That is why the container healthcheck has a start period.

2. **A sweep completing in the worker log.** Within `STAGE_STATUS_SYNC_SECONDS` (five
   minutes by default) of the restart:

   ```bash
   docker compose --env-file .env.docker logs --since 10m worker-default \
     | grep sync_all_stage_statuses
   ```

   Expect a `succeeded` line. `Stage-status sweep still running; skipping this tick`
   repeated every tick means a previous sweep is stuck holding the lock. No output means
   beat is not firing. Restart it.

3. **The dashboard staleness indicator.** Open `/`. The stage-status timestamp should be
   under three sweep intervals old and not flagged stale. This is the end-to-end check
   that the worker, the cache and OCS all work together, which the health endpoint cannot
   tell you.

4. **The queue page.** Open `/queue/` and `/jobs/`. Both render, and any entry queued
   before the deploy is still in the list with the status it had. An empty `/jobs/` page
   after a deploy that was not supposed to change anything is worth stopping for.

## Starting after a host reboot

Compose restarts a container that dies; it does not survive the host restarting. Install
the LaunchAgent in `deploy/launchd/` so a reboot brings the stack back. The README's
*Starting the stack at login* section has the two commands and the caveat that it needs a
GUI login before Docker Desktop, and therefore the stack, can start.

After any unattended reboot, run the four checks above rather than assuming recovery.

## When an entry goes STRANDED

`STRANDED` is the state this app cannot resolve without a person, and the only one that requires
paging. It means the worker claimed an entry, started an `ocs` submission, and died before
recording a demand id. Nobody knows whether OCS received the command.
`reconcile_stranded_submissions` marks it after 30 minutes and stops there. A
job left unsubmitted costs a delay, while resubmitting a running one costs a duplicate
alignment.

Handle it the way any production incident is handled here, adapting the usual sequence:

1. **Say something before doing anything.** Post in the team channel that entries are
   stranded and that you are looking. Someone else may already be resubmitting by hand.
2. **Find out what happened before acting.** Stranded entries almost always follow
   something: a restart during a submission, the submissions worker being OOM-killed, or
   an `ocs` call hitting `OCS_CLI_TIMEOUT`. Check the worker log around the entry's
   `claimed_at`. `Submission outcome unknown for ...` is the line the worker writes when
   it cannot tell.
3. **Stabilise before fixing.** If the stranding was caused by the release, roll the code
   back first and work out why afterwards. A worker that is still dying will strand the
   next entry too.
4. **Resolve each entry by hand, one at a time.** For each one, search OCS for a demand
   covering that sample and stage. If there is one, the job is running: move the entry to
   `SUBMITTED`. If there is not, set it back to `PENDING` and the worker picks it up on
   the next tick. Do this from the entry's change page in the admin. The bulk requeue
   action excludes `STRANDED` because "requeue all" would create the duplicate job
   that duplicates a job. `demand_id` is read-only in the admin, so an entry closed this
   way keeps a blank one; note the id in the incident write-up instead.
5. **Watch the next few submissions** after the queue restarts, rather than assuming the
   first success means it is over.
6. **Write down why it happened,** blamelessly, and what would have prevented it. The
   useful output is usually one of: something should have drained the worker before the
   restart, or the timeout was too short for the job that was submitted.
