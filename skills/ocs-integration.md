# OCS integration guide

Use this guide for OCS commands, demand investigation, AWS resource lookup, OCS failures, and
questions about how OmicsHub obtains metadata, statuses, file locations, or logs.

## Source order

Use `/Users/beagannguy/Desktop/ocs_assets/genomics-cloud-services` as the OCS source of truth
when it is available. Inspect the relevant CLI command, runner, API client model, Lambda route,
and infrastructure policy before inventing a command or AWS call. Use `--help` on the installed
CLI to confirm current syntax.

Use this order to identify the correct operation and its owning boundary:

1. Inspect the existing OCS CLI command.
2. Inspect the existing repository helper or client.
3. Use read-only Boto3 or AWS CLI inspection when the OCS source maps the resource.
4. Perform a mutation only when the user explicitly requests it and the target is unambiguous.

Keep the AWS account/profile and OCS environment separate. Verify both independently. Set the
region explicitly when the shell does not provide one. Never copy access keys, secret keys,
session tokens, SSO data, or credential-file contents into this guide, tests, logs, or replies.

## OmicsHub data flow

The app reads the local PostgreSQL mirror through the Django ORM for normal page requests. The
catalog worker reads OCS DynamoDB tables with Boto3 and writes selected metadata and stage
status records to PostgreSQL. The two databases are not full mirrors.

The relevant OCS table names are built from `OCS_ENV_BASE`:

- `<base>-fastq-metadata`
- `<base>-fastq-history`
- `<base>-demand-registry`
- `<base>-file-store`

DynamoDB scans and batch reads are paginated. Projection expressions select only fields needed
by the sync. Batch reads must remove duplicate keys and retry unprocessed keys with a bounded
attempt count. Keep sync writes idempotent and do not prune local records from an empty AWS
response.

## Demand and log tracing

A demand is an OCS record, not an AWS resource. Keep these identifiers distinct:

```text
demand ID -> Step Functions execution ARN -> nested execution ARN -> Batch job ID -> log stream
```

Use the OCS demand command first:

```bash
ocs core gwo demand get-status --demand-id <demand-id> --format json
ocs core gwo demand get-logs --demand-id <demand-id> --format json
```

If the OCS response does not contain a usable execution ARN, use the demand workflow mapping
to list matching Step Functions executions, inspect execution history, find the Batch job ID,
and then read the `container.logStreamName` from `batch:DescribeJobs`. A missing log stream can
mean the job has not reached container startup, failed during setup, or used another execution.
It does not prove that the demand never ran.

Use `logs:GetLogEvents` with pagination and `startFromHead` for chronological output. Do not
assume the newest page is the beginning of the container log. Use the log group and stream
returned by Batch or the execution history instead of guessing a stream name.

## Credential boundaries

The normal application AWS identity handles catalog synchronization, OCS submission, S3 data
locations, and the file-store lookup. The Monitor log viewer uses a separate session-specific
Boto3 session built from user-supplied temporary credentials. It must not call
`boto3.setup_default_session()`, set process-wide AWS variables, select the app profile, or
handle application AWS calls.

The log session may validate with STS, resolve a visible demand through the required DynamoDB
and Step Functions calls, describe its Batch job, and read its CloudWatch stream. Store its
values only encrypted in the current Django session cache. Clear them on explicit clear or an
invalid AWS response. Never place them in PostgreSQL, cookies, browser storage, Docker layers,
HTML, JavaScript, tests, or logs.

## OCS workflow terms

- A demand records requested work.
- A Step Functions execution runs the workflow state machine.
- A Batch job runs a workflow task, often in an ECS task on shared compute capacity.
- An input or output data-sync job is separate from the custom workflow container.
- A file-store ID identifies registered output files. It is not a demand ID.
- An S3 URI comes from the OCS file-store record. Do not infer it from a fastq name.

For Data Locations, Django reads the local `StageStatus.file_store_id`, resolves that ID through
the application Boto3 file-store client, and lists S3 contents with `ListObjectsV2`, a delimiter,
and continuation tokens. Downloads must keep every object below the registered root, expand
selected folders page by page, and stream objects into a ZIP without loading all file contents
into memory.

## Failure diagnosis

Classify the failure before changing code: shell setup, Python environment, AWS identity, OCS
environment, CLI parsing, API behavior, infrastructure state, or missing data. Preserve the
first concrete error and redact secrets. Verify account, region, environment, workflow, image
digest, execution, Batch job, and log stream independently.

Do not switch accounts, change OCS environments, or use another identity to bypass an error. If
OCS cannot provide an execution record, report that condition and use the mapped AWS lookup only
when the temporary log credentials have the required permissions.

## Verification

For code changes, run the focused Django tests and Boto3 boundary tests, JavaScript syntax
checks, `git diff --check`, and the relevant Playwright tests. For AWS operations, run a
read-only identity or status check first. For Docker changes, validate Compose with the real env
file, rebuild the affected service, check `/healthz/`, and inspect container status without
printing secrets.
