# OmicsHub

OmicsHub queues and submits OCS alignment and post-alignment jobs.

Users select fastq samples. OmicsHub checks each sample's stage status, shows the exact
`ocs` command, and queues the command after confirmation. One worker submits commands
within the OCS job limit and the spacing in the manifest.

## OCS data and commands

Load fastq sample metadata from the `<env>-fastq-metadata` DynamoDB table. Join
`<env>-fastq-history` with `<env>-demand-registry` to load stage status. Count in-flight
jobs from `IN_PROGRESS` rows in the `demand_type` index of `<env>-demand-registry`. Send
alignment and post-alignment commands through the `ocs` CLI, which is the only CLI call in
the project.

### Running the `ocs` CLI from a worker

A Celery worker is not a login shell, so it inherits none of the setup that makes `ocs`
work at an interactive prompt. Two settings replace it: `OCS_CLI_PATH` names the
executable rather than relying on `PATH`, and `OCS_CLI_PYTHONPATH` carries the `src`
directories the CLI's venv resolves its packages through , the same ones the `activateocs`
shell function exports. Without the second, submissions fail on `ModuleNotFoundError`
before reaching OCS.

Check both are right without submitting anything:

```bash
python manage.py shell -c "
import subprocess; from django.conf import settings; from apps.ocs.cli import _subprocess_env
print(subprocess.run([settings.OCS_CLI_PATH, 'fastqs', 'align', '--help'],
                     env=_subprocess_env(), capture_output=True, text=True).returncode)"
```

`OCS_ENV_BASE` is the prefix on every table name, so `prod` means `prod-fastq-metadata`.

### AWS credentials

The app never reads, stores, or logs an access key. It builds a boto3 session and lets
boto3 resolve credentials.

The key lives in a credentials file belonging to this app, not the machine-wide
`~/.aws/credentials`, so it is reachable only from this process and the `ocs` subprocess it
starts. Every other tool on the machine keeps using the profiles in `~/.aws/config`.

```bash
mkdir -p ~/.omicshub && chmod 700 ~/.omicshub
AWS_SHARED_CREDENTIALS_FILE=~/.omicshub/credentials aws configure --profile omicshub
```

Then in `.env`:

```
AWS_PROFILE=omicshub
AWS_SHARED_CREDENTIALS_FILE=/Users/you/.omicshub/credentials
```

Confirm the scoping holds , the first command works, the second must fail:

```bash
python manage.py shell -c "from apps.ocs import dynamodb; print(dynamodb.count_in_progress('align'))"
aws sts get-caller-identity --profile omicshub     # expected: Unable to locate credentials
```

The `ocs` CLI resolves credentials itself, so the worker passes `AWS_PROFILE` down to it.
submissions and status reads then authenticate as the same identity.

Use a **static-key** profile, not SSO: the Celery worker and beat run unattended and cannot
refresh an expiring SSO session. In production on EC2/ECS, attach an IAM role to the host
and leave `AWS_PROFILE` unset. The instance role then supplies credentials without a key
to rotate.

Do not place `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in `.env`, settings, or any
other file in this repository. Store only the profile name when a profile is required.

## Apps

```
apps/ocs         gateway: DynamoDB reads (dynamodb.py) and the CLI submit (cli.py). No models.
apps/accounts    custom User
apps/catalog     Sample + StageStatus, the local mirror of OCS, and the sync service
apps/workflows   the uploaded config: parsing, validation, command building, modality
apps/queueing    CartItem, QueueEntry, planning, round-robin claiming, the submission worker
```

`apps/ocs` is imported by the others and imports none of them.

## Workflow manifest

The uploaded JSONC manifest defines every submission detail: command
templates per modality, references per organism, probe sets, chemistries, the job limit,
and which OCS status labels count as a finished stage. Changing the pipeline means
uploading a new config, not editing code.

```bash
curl -X POST -H "Authorization: ..." -F file=@config.jsonc  https://.../api/configs/
curl -X POST -H "Authorization: ..."                        https://.../api/configs/<id>/activate/
```

Uploads are parsed (comments stripped, pipe-delimited organism keys expanded) and
structurally validated before they are stored. Exactly one config is active at a time.

Organism keys are matched tolerantly. OCS is not consistent about separators. The mirror
holds both `macaque-nemestrina` and `harbor_porpoise`, so `references` and
`probe_sets_by_organism` are looked up ignoring `-` vs `_` and case. An exact key always
wins, so a config that spells two organisms differently keeps both entries;
the fold only applies when nothing matched exactly. Two spellings that fold together but
carry *different* references are an error rather than a coin toss, because guessing there
means aligning against the wrong genome.

`workflow_configs/config.jsonc` is the current one, kept in the repo so it can be diffed and
re-uploaded. It is a copy, not the source of truth. The database holds the active manifest,
and editing the file has no effect until it is uploaded and activated.

Validation checks the file structure. Check whether the manifest can build a command for
the fastq samples in the mirror before activating it:

```bash
python manage.py check_config_coverage workflow_configs/config.jsonc
```

## Plan and confirm a submission

```
POST /api/queue/plan/   {"batch_name_from_vendor": "MTX-22068"}
```

Return the stage due for each fastq sample and its exact command, plus a `skipped` list with
a reason per sample (`ingest_incomplete`, `already_complete`, `alignment_in_progress`,
`library_prep_unconfigured`). The preview does not write queue entries.

Infer the modality from the vendor batch name prefix. `MTX-22068` is MTX. When the prefix
has no workflow in the manifest, return those samples under
`modality_required` alongside `available_modalities`, and `POST /api/queue/` refuses them
until the request carries a `modality`. It is never guessed.

```
POST /api/queue/   {"batch_name_from_vendor": "ZZZ-1", "modality": "MTX"}
```

Return every failure in one envelope. The refusal above arrives as a 400 with
`error.message.modality_required` and `error.message.available_modalities` , enough to
prompt the user from a single payload:

```json
{"error": {"code": "HTTP400", "message": {"modality_required": ["ODD-1"],
                                          "available_modalities": ["MTX", "RFX", "RTX"]}}}
```

Other body fields: `fastq_names` (instead of a batch), `force` (`align` or `post-align`,
overriding the already-complete and in-progress rules), `batch_processing` (address RTX/RFX
commands by fastq name rather than load name), `notify_email` (defaults to your account's).

## Web pages

Render pages with Django templates and Bootstrap. The project has no frontend build step
or separate frontend deploy, and session authentication needs no tokens or CORS.
`apps/web` contains the views and templates and calls the same services as the API.

| Path | |
|---|---|
| `/` | Sync a vendor batch, filter fastq samples, select samples, and add them to the cart. |
| `/checkout/` | Review the cart, select the manifest, and submit commands. |
| `/queue/` | View and cancel your pending queue entries. |
| `/jobs/` | View submitted, failed, and stranded jobs with current stage status. |
| `/settings/` | Upload and activate the manifest as a staff user. |

### The cart and checkout

```
dashboard → add to cart → /checkout/ → submit modal → confirmation modal → queued
```

The cart is a table (`queueing.CartItem`), not session state, so a selection survives a
logout and can be built up across several visits to the dashboard. Remove a sample only
after its queue entry is created. A sample skipped because its ingest is still
running stays staged for next time.

Checkout is where the manifest supplies the submission details. For each fastq sample,
check its OCS status to find the due stage, match its library prep and organism to a command
config, and fill in the reference, chemistry, and probe set. The manifest supplies values
instead of asking the user to enter them again.

The picker on the checkout page defaults to the active config but will build against any
uploaded one, so a candidate config can be checked against real samples before it is
activated.

Each command can then be adjusted per sample in the submit modal , switch to a different
command config, change the reference or chemistry, or edit the command text directly. The
menus only offer values the config contains, and the references offered are the ones for
that sample's own organism. Every step re-plans on the server, so an edit that cannot be
parsed is refused before anything is queued.

When a modality cannot be inferred the submit modal says which samples need one and will
not let the confirm through without it.

## Endpoints

| Method | Path | |
|---|---|---|
| GET | `/api/samples/` | List fastq samples and filter by `batch_name_from_vendor`, `organism_common_name`, `library_prep_method_name`, or `fastq_name`. |
| POST | `/api/samples/sync/` | Load a vendor batch or named fastq samples from OCS. |
| POST | `/api/queue/plan/` | Return a submission plan without creating queue entries. |
| POST | `/api/queue/` | Confirm the plan and create queue entries. |
| GET | `/api/queue/` | Return the user's entries. Staff users can view all entries, and `?status=SUBMITTED` filters running jobs. |
| POST | `/api/queue/{id}/cancel/` | Cancel a pending queue entry. |
| GET/POST | `/api/configs/` | List or upload workflow manifests as a staff user. |
| POST | `/api/configs/{id}/activate/` | Activate a workflow manifest as a staff user. |

Sync fastq samples before planning commands for them.

## Submission worker

`process_next_queue_entry` submits one entry per run and schedules the next:

1. If nothing is pending, stop.
2. If OCS already has `job_settings.limit` demands in progress, submit nothing and
   re-check in `poll_interval_hours`. Queued jobs wait for capacity; they are never
   dropped.
3. Otherwise claim one entry using round-robin order. The user who has waited longest since
   their own last submission goes next, so one large batch cannot starve everyone else. Mark it
   `SUBMITTING`, run the `ocs` command, and record the demand id.
4. Schedule the next run after the command config's `spacing` seconds.

This only holds together if submissions are serialized, so the task is routed to a
`submissions` queue that must run with **one worker process**:

```bash
celery -A omicshub worker -Q submissions -c 1 --hostname=submissions@%h
celery -A omicshub worker -Q default -c 4
celery -A omicshub beat
```

Beat re-kicks the chain every minute (a no-op on an empty queue), refreshes the status of
running demands every ten minutes, and reconciles stranded submissions.

### Stranded submissions

If the worker dies between claiming an entry and recording the demand id, that entry is
left in `SUBMITTING`. Whether OCS received the command cannot be determined from here , a
demand appears in `fastq-history` only once it produces output, so a job submitted seconds
ago looks identical to one that never ran.

So `reconcile_stranded_submissions` does not guess. After 30 minutes it moves the entry to
`STRANDED` and leaves it for a person, because the two mistakes are not symmetric: a job
left unsubmitted costs a delay, while resubmitting one that is already running costs a
duplicate alignment. The admin's bulk requeue excludes `STRANDED`
action , check OCS for a demand covering that sample and stage, then either close the
entry or set it back to `PENDING` individually.

Submissions are never retried automatically, for the same reason: a `subprocess` call that
fails or times out may still have reached OCS.

## Running locally

```bash
uv venv --python 3.12
uv pip install -e .
cp .env.example .env      # then fill it in
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Postgres is required, not optional: the queue claim uses `SELECT ... FOR UPDATE SKIP
LOCKED`. Redis is the Celery broker.

```bash
docker volume create omicshub-pgdata
docker run -d --name omicshub-postgres --restart unless-stopped \
  -e POSTGRES_USER=omicshub -e POSTGRES_PASSWORD=omicshub -e POSTGRES_DB=omicshub \
  -v omicshub-pgdata:/var/lib/postgresql/data -p 5432:5432 postgres:16
docker run -d --name omicshub-redis --restart unless-stopped -p 6379:6379 redis:7-alpine
```

`--restart unless-stopped` matters on a laptop: without it neither service comes back
after a reboot, and the backend 500s until someone starts them by hand. The **named**
volume matters for the same reason a backup does , Postgres creates an anonymous one
otherwise, with a random-hash name that is easy to lose to `docker volume prune` and
awkward to reattach.

## Running it in Docker

Run the whole stack in containers: Postgres, Redis, the web process, both Celery workers,
and beat. The container setup packages the `ocs` CLI with the application. On a host,
`OCS_CLI_PATH` and
`OCS_CLI_PYTHONPATH` point at a venv and four `src` directories that exist nowhere else,
so a checkout on a second machine cannot submit anything. The image pip-installs those
four packages, so `ocs` is on the PATH and `OCS_CLI_PYTHONPATH` is not needed.

```bash
scripts/vendor_gcs.sh                      # GCS_SRC=... if the checkout is elsewhere
cp .env.docker.example .env.docker         # then fill it in
docker compose --env-file .env.docker up -d --build
```

`--env-file .env.docker` is required on **every** compose command. Compose resolves
`${...}` from the shell or from a file called `.env`, and this project's `.env` is the
host config pointing at localhost , so without the flag the substitutions are empty, and
with the wrong file they are quietly wrong.

`scripts/vendor_gcs.sh` exists because a Docker build can only read files inside its build
context, and genomics-cloud-services lives outside this repo. It copies the four packages
into `vendor/gcs/` (gitignored). Once this repo is under version control that becomes a
submodule and the Dockerfile does not change.

Check these three conditions before the first `up`:

- **The database starts empty.** The compose stack owns a new `pgdata` volume; the mirror
  in the hand-started `omicshub-postgres` container does not come with it. Samples and
  stage statuses rebuild themselves from OCS on the next sweep, but users, queue entries
  and workflow configs do not , move those with `pg_dump` (below) if you want them.
- **Ports.** `POSTGRES_PORT`, `REDIS_PORT` and `WEB_PORT` set the host side of each
  published port, so the stack can come up beside the hand-started containers already
  holding 5432 and 6379. All three bind to `127.0.0.1` only; the tunnel is what exposes
  the web port, and the database should not be reachable from the network as well.
- **Plain `http://localhost:8000` will 301 to https.** That is `SECURE_SSL_REDIRECT` in
  the prod settings doing its job. Reach it through the tunnel, which terminates TLS and
  sends `X-Forwarded-Proto: https`, or set `DJANGO_SETTINGS_MODULE=omicshub.settings.dev`
  for a local look.

Credentials are bind-mounted read-only from `AWS_CREDENTIALS_FILE` and never copied into
the image , these are long-lived keys against the production OCS account, and an image
layer holding them would be permanent and pushable. `.env` and `.env.docker` are in
`.dockerignore` for the same reason.

`worker-submissions` must stay at one replica with `--concurrency 1`. The global OCS job
limit and the config's `spacing` between submissions are only enforced because it is the
only process submitting; scaling it submits the same demand twice.

### Starting the stack at login

`restart: unless-stopped` brings the containers back if one of them dies, but nothing
brings them back after the host reboots. `deploy/launchd/` holds a LaunchAgent that does:

```bash
sed "s|__OMICSHUB_DIR__|$PWD|g" deploy/launchd/org.alleninstitute.omicshub.stack.plist \
  > ~/Library/LaunchAgents/org.alleninstitute.omicshub.stack.plist
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/org.alleninstitute.omicshub.stack.plist
```

It runs `deploy/launchd/start-stack.sh`, which waits for Docker Desktop to answer before
running `compose up -d --wait` and logs what happened to `logs/launchd-stack.log`. The
waiting is the point: at login launchd starts agents while Docker is still coming up, so
calling compose directly would fail on a socket nobody is listening to yet.

It is an agent rather than a daemon because Docker Desktop runs inside a GUI login
session, so the machine has to reach a logged-in desktop before the stack starts. That is
the real limit of running this on a Mac, and it is worth knowing before treating an
unattended reboot as recovered.

The agent starts the stack and nothing more. Supervising the four application processes is
compose's job — a second supervisor could start a second `worker-submissions`, which is
the one thing that must never happen.

```bash
launchctl kickstart -p gui/$UID/org.alleninstitute.omicshub.stack   # run it now
launchctl bootout gui/$UID/org.alleninstitute.omicshub.stack        # stop it at login
```

### Stored data

Samples and stage statuses are a mirror: delete them and a sync rebuilds them from OCS.
Queue entries, workflow configs, and users are not derivable from anywhere else , that is
the data worth backing up once real jobs are running:

```bash
docker exec omicshub-postgres pg_dump -U omicshub omicshub > omicshub-$(date +%F).sql
```

## Readiness

```
GET /healthz/    → 200 when ready, 503 with the reason when not
```

Check the four backend dependencies and name any missing dependency: the database,
the Celery broker, **a worker consuming the `submissions` queue**, and an active
workflow config. The worker check matters most. A queue with no consuming worker accepts
jobs forever and submits none of them.

The readiness endpoint needs no authentication, so it answers when login is broken.

## Exposing it through a VS Code port tunnel

The app holds AWS credentials that submit real jobs to production OCS, so treat the
forwarded URL as the front door it is.

1. **Turn `DEBUG` off.** With it on, Django's error page shows tracebacks, local
   variables, and settings to anyone who triggers an error. Set `DEBUG=False` in `.env`.
2. **Add the tunnel host** to `ALLOWED_HOSTS`, and its `https://` origin to
   `CSRF_TRUSTED_ORIGINS`, or admin logins fail as CSRF errors.
3. **Run `collectstatic`** once , with `DEBUG=False` Django stops serving static files
   itself, and whitenoise serves them from `staticfiles/` instead.
4. **Move the admin off `/admin/`.** Set `ADMIN_URL` in `.env` to something else , it is
   the page that can edit users and activate a config, and the default path is the first
   one anything scanning the URL will try. Nothing hardcodes the path, so this is the only
   change needed.
5. **Keep the tunnel private.** VS Code's private visibility requires a GitHub login to
   reach the port. Public visibility means anyone with the URL reaches an app that can
   spend OCS compute. Every endpoint requires authentication, but that is one layer, not
   two.

```bash
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
```

`runserver` is a development server. For a handful of analysts on one laptop that is
workable; if this outgrows that, move to gunicorn before adding more users, not after.

## Releasing

[`RELEASE.md`](RELEASE.md) is the deploy procedure: every environment variable and which
ones have no default, the order the five processes come back in, why the submissions
worker stays at one process, the one migration that locks a table while it runs, what can
and cannot be rolled back, what to check afterwards, and what to do with a `STRANDED`
entry.

## Tests

```bash
pytest
```

Needs the Postgres above; no AWS access and no `ocs` binary , the gateway is stubbed in
every test.
