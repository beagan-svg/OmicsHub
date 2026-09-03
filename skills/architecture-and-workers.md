# OmicsHub architecture and worker rules

This file is the operating guide for Django, the OCS data mirror, Celery, Redis, and the
submission queue.

## Application boundaries

- Django serves the web UI and reads application data from local PostgreSQL through the ORM.
- PostgreSQL stores `Sample`, `StageStatus`, `QueueEntry`, workflow configuration, users, and
  cart data. OCS and PostgreSQL are not fully mirrored databases. PostgreSQL contains the
  in-scope local mirror and the app's own records.
- `apps/ocs_integration/dynamodb.py` uses Boto3, not the AWS CLI, for OCS DynamoDB reads.
  Table names are `<OCS_ENV_BASE>-fastq-metadata`, `<OCS_ENV_BASE>-fastq-history`,
  `<OCS_ENV_BASE>-demand-registry`, and `<OCS_ENV_BASE>-file-store`.
- DynamoDB scans and queries are paginated. Projection expressions limit demand and history
  reads to fields used by the mirror. Batch reads remove duplicate keys and retry unprocessed
  keys with bounded exponential backoff.
- The catalog sync worker scans the configured OCS metadata, history, and demand data, then
  writes matching samples and stage statuses to PostgreSQL. Stage status sync runs every five
  minutes by default. Metadata sync runs nightly and can run on demand.
- A successful sync updates the local sync timestamp. The UI can poll PostgreSQL for current
  local data without triggering an AWS sync.

## S3 data locations

- A stage stores a file-store ID from OCS history in `StageStatus`.
- When a user opens a data location, Django reads the local stage row, uses Boto3
  `BatchGetItem` on the OCS file-store table to resolve the ID to an `s3_uri`, and then uses
  S3 `ListObjectsV2` to list immediate folders and files.
- S3 listing uses a delimiter and continuation tokens. Downloads validate every key below the
  registered root, expand selected folders with S3 pagination, and stream objects into a ZIP.
- Do not infer an S3 location from a file name or invent a path. Use the stored file-store ID
  and the file-store record.

## Celery and Redis

- Celery Beat publishes scheduled messages to the Redis broker. It does not execute tasks.
- `catalog-sync-worker` consumes the `catalog-sync` queue. `ocs-submission-worker` consumes
  `ocs-submissions` with concurrency one. Keep one submission worker unless the queue design
  is changed with an explicit concurrency and duplicate-submission analysis.
- The web process, both workers, Beat, and the one-shot `migrate` service share one image but
  run different commands. Only `migrate` applies database migrations.
- Redis broker and Redis cache are separate services and databases. The broker carries Celery
  messages. The cache stores submission holds, worker heartbeat data, sync locks, and encrypted
  temporary log credentials. Do not use process memory for cross-worker coordination.
- Celery tasks use the existing task routes. Do not publish a submission task to the default
  queue by accident.
- Stage sync uses a Redis lock with a timeout and late acknowledgements. A lost sync task may
  be redelivered because the sync is idempotent. Do not allow overlapping full sweeps.

## Queue semantics

- A `QueueEntry` is the exact command confirmed by the user. It stores command arguments,
  rendered command text, stage, modality, owner, spacing, demand ID, and submission status.
- Valid queue states are `PENDING`, `SUBMITTING`, `SUBMITTED`, `FAILED`, and `CANCELLED`.
  A failed submission remains visible until the user deletes it or a retry succeeds.
- The queue worker claims one pending entry inside a database transaction with
  `select_for_update(skip_locked=True)`. The partial unique constraint prevents two pending
  entries for the same sample and stage.
- Claiming skips entries owned by users whose `queue_paused` value is true, then continues to
  the next user's entry. User pause affects only that user's pending entries.
- Claim order is round-robin by the user's last claimed or submitted time, with oldest entry
  order as the tie-breaker. A user does not gain priority by pausing another user's queue.
- Before claiming, the worker checks for an active capacity hold and spacing hold. It counts
  `IN_PROGRESS` alignment and post-alignment demands in the OCS demand registry before sending
  a command. When OCS is at the configured limit, it stores a Redis capacity hold.
- After a successful submission, the worker stores the demand ID, opens the configured spacing
  hold, and currently schedules one delayed copy of the queue task. Beat also publishes its
  regular one-minute queue task. The Redis hold and database claim transaction prevent either
  path from submitting during the same spacing window. Change the task and its tests together
  if the scheduler is changed to Beat-only.
- A CLI submission error marks the claimed entry `FAILED`. An unexpected error also records a
  failure and is allowed to reach Celery so the worker reports it.
- Cancelling a `QueueEntry` is conditional on it still being `PENDING`
  (`QueueEntry.objects.filter(pk=..., status=PENDING).update(...)`), so the worker cannot claim
  an entry the same moment a user cancels it. Losing that race is an ordinary outcome, not a
  client mistake: both `apps/web_ui/views/queue.py`'s cancel view and `QueueViewSet.cancel`
  return success with the entry's current status rather than raising or returning 400.
- Do not add a second submission worker, a second queue implementation, or an unbounded retry
  loop. Any change to scheduling must preserve one command per claimed entry and the configured
  spacing between OCS submissions.

## AWS credential scope

- The app identity configured through `AWS_PROFILE` or the normal Boto3 credential chain is
  used for catalog synchronization, stage status reads, S3 data-location reads, and the OCS
  submission CLI. It is not a substitute for a user's temporary log credentials.
- Monitor log credentials are supplied by the user for log access only. The log module builds
  a separate Boto3 session directly from the three submitted values. It never installs them as
  process environment variables, the default Boto3 session, or the app profile.
- Temporary credentials are validated with STS and kept only in the user's session cache,
  encrypted with the configured credential-encryption key. They are cleared when invalid or
  explicitly cleared. They must never be logged, sent to Sentry, written to PostgreSQL, or
  used for submission or catalog sync.
- Log lookup uses the temporary session for the demand registry, Step Functions execution
  history, AWS Batch job details, and CloudWatch Logs. It follows the stored execution ARN for
  normal records. Failed demands use the demand's workflow mapping to find the execution, then
  resolve nested Step Functions history to the Batch job and its container log stream.
- There is no alternate credential path. If the supplied identity lacks permission or the demand
  has no usable execution record, report that exact condition.

## Contributor rules

- Read the owning Django app, model, task route, tests, and external-client boundary before
  editing. Extend the existing boundary instead of adding a parallel helper or service.
- Use Django ORM transactions and row locks for local queue state. Use Boto3 APIs for AWS
  calls and their documented pagination tokens. Do not replace these with shell commands,
  scraped CLI output, or custom retry machinery without a concrete API limitation.
- Keep AWS sync idempotent and scoped to configured samples. Never run a destructive prune
  from an empty or missing scope.
- Keep monitor and dashboard polling separate from AWS synchronization. Page polling reads
  local PostgreSQL; the scheduled sync is the only normal path that pulls new AWS data.
- Preserve open log panels and user selections during HTML refreshes. Cancel stale requests,
  ignore responses for detached or closed panels, and avoid overlapping refresh requests.
- Use short, concrete names and docstrings. Remove dead branches, redundant substitute paths,
  wrappers with no behavior, duplicate queries, and speculative validation.
- Never commit `.env.docker`, AWS credentials, session tokens, private keys, or live sample
  access material. Use placeholders in documentation and test fakes at the AWS boundary.
