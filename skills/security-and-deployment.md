# OmicsHub security and deployment boundaries

## Scope

Use this file when changing or reviewing:

- temporary AWS credentials used by the Monitor log viewer;
- the AWS identity used by OmicsHub for synchronization, S3 access, and OCS submission;
- credential validation, expiration, cache lifetime, and status messages;
- DynamoDB, S3, Step Functions, Batch, and CloudWatch Logs access;
- Docker Compose services, mounts, secrets, health checks, and startup behavior;
- image rebuilds, local deployment, and production exposure.

Do not use this file as a general Django, UI, queue, or data-model guide.

## Two separate AWS identities

OmicsHub has two deliberately separate credential paths.

### The application AWS identity

The application identity is configured by `AWS_PROFILE` and the AWS credential chain. In
Docker Compose, the profile reads the host file mounted at `/run/aws/credentials` by the
web service and both AWS workers. The mount is read-only. The scheduler does not receive the
credential-file mount because it only publishes Celery tasks and does not call AWS.

The application identity is used for:

- scheduled OCS synchronization;
- DynamoDB reads for fastq metadata, fastq history, demand registry, and file-store data;
- S3 listing and downloads for data locations;
- the `ocs` CLI used to submit commands;
- server-side application operations that use the normal boto3 credential chain.

The application identity is not a credential fallback for the log viewer. A failed log-viewer
credential validation or log request must fail for that session. It must not retry with
`AWS_PROFILE`, the container role, environment credentials, a local profile, or any other
identity.

### User-supplied temporary log credentials

The Monitor log viewer accepts the three values from a user’s short-lived AWS session:

- access key ID;
- secret access key;
- session token.

The browser parses the pasted values and sends them only to the credential-validation endpoint.
The server builds a dedicated boto3 session from those three values. It must not call
`boto3.setup_default_session()`, set process-wide AWS environment variables, select a profile,
or replace the application’s boto3 session.

After STS validation, the server stores the values encrypted with
`CREDENTIAL_ENCRYPTION_KEY` in the session-scoped cache entry. The cache entry is keyed by the
Django session, not by user input or demand ID. The credentials never belong in:

- source files;
- `.env.docker.example` with real values;
- Docker build arguments;
- image layers;
- logs;
- HTML responses;
- browser local storage or cookies;
- database models;
- a global boto3 session;
- another user’s session.

The cache lifetime is a safety limit for unused credentials. It is not a claimed AWS expiration
time. STS `GetCallerIdentity` does not provide the session expiration used by the UI. The UI
must say that expiration cannot be determined automatically unless a later AWS request proves
the credentials expired.

## Log-viewer AWS allowlist

The temporary session is only for the log lookup path. Its AWS operations are limited to the
operations required to resolve one visible demand to its Batch log stream:

1. `sts:GetCallerIdentity` validates the pasted credentials.
2. For a failed demand without a stored execution ARN, DynamoDB `GetItem` reads the demand’s
   workflow name from the demand registry.
3. Step Functions `ListExecutions` finds the execution for that failed demand.
4. Step Functions `GetExecutionHistory` follows nested executions and finds the Batch job ID.
5. Batch `DescribeJobs` reads the container log stream name.
6. CloudWatch Logs `GetLogEvents` reads the log events from `/aws/batch/job`.

The request must first prove that the demand is visible in OmicsHub’s Monitor data. A demand ID
from an arbitrary request must not become a general AWS lookup endpoint. The server must use
the local stage record and its stored execution ARN for running or completed stages when one is
available. Failed demands can use the temporary-session demand-registry and Step Functions
lookup described above.

When AWS rejects the temporary credentials, remove the encrypted cache entry immediately. Do
not expose raw botocore errors, request details, account data that is not needed by the UI, or
secret values. Report only the redacted state the UI needs:

- `Credentials valid` after STS validation succeeds;
- `Credentials expired` when AWS explicitly reports an expired token;
- `Credentials failed` for another rejection, including missing permission or an invalid
  signature;
- `Credentials required` when this session has no usable cached credentials.

An unreachable server or AWS service is not an expiration result. Keep the credentials state
separate from the request error and do not silently substitute the application identity.

The Clear action must delete this session’s cache entry, cancel active log requests, and disable
the row log buttons. It must not change the application AWS profile or any other user’s cache.

## DynamoDB, S3, and workflow data boundaries

The normal application identity reads the OCS tables through boto3. Table names are built from
`OCS_ENV_BASE`, such as `prod-fastq-history` and `prod-demand-registry`. The app does not query
these tables through the AWS CLI or an HTTP workaround.

The local PostgreSQL database is the app’s mirror and authorization boundary for the dashboard.
AWS synchronization writes known OCS records to PostgreSQL. A page request normally reads the
local mirror. Data-location contents and downloads resolve the local file-store ID through the
application’s DynamoDB client and then use the application identity’s S3 client to list or
stream objects.

The log viewer is different: it uses only the session-specific temporary boto3 session. Do not
route a log request through the normal DynamoDB or S3 client, and do not let a temporary
credential alter data synchronization, S3 data-location access, OCS submission, or Celery.

Use explicit AWS regions from `OCS_AWS_REGION`, currently `us-west-2` in the example
configuration. Do not infer a region from an arbitrary default session when the project setting
already defines it.

## Docker Compose services and boundaries

The Compose stack contains seven services:

- `postgres` stores the local Django database on the `pgdata` named volume;
- `redis-broker` carries Celery messages;
- `redis-cache` stores Django cache data, including encrypted log credentials and queue holds;
- `web-ui` runs migrations, collects static files, and serves Gunicorn on port 8000;
- `ocs-submission-worker` consumes the `ocs-submissions` queue with concurrency 1;
- `catalog-sync-worker` consumes the `catalog-sync` queue;
- `celery-scheduler` publishes scheduled tasks.

The list contains seven names because the first line describes the three supporting services
and the four application processes. Do not add a second submission-worker replica or increase
its concurrency. The single submission worker is part of the queue’s correctness guarantee.

Compose service discovery uses `postgres`, `redis-broker`, and `redis-cache` as host names inside
the network. Application containers must not use `localhost` to reach another Compose service.
Health-based `depends_on` waits for PostgreSQL and both Redis services before starting the app
processes. This controls startup order only. It does not replace application error handling or
make a running service healthy forever.

The web health check calls `/healthz/`. It covers the database, cache, broker, workflow config,
and submission-worker health. A failed health check does not automatically restart a container;
`restart: unless-stopped` responds to process exit, not an unhealthy status. Production
monitoring must alert on unhealthy state instead of assuming Docker will repair it.

## Secrets and image construction

Use `.env.docker` only as a deployment-time file. It contains database credentials, Django
secrets, profile settings, encryption keys, and host paths. It is excluded by `.dockerignore`.
Only `.env.docker.example` may be committed, and it must contain placeholders or safe example
values.

The AWS credential file is a host bind mount with read-only mode. It must not be copied into the
build context, passed as a build argument, copied into the image, written by startup scripts,
or printed by diagnostics. The Dockerfile must continue to build without access to production
credentials.

The runtime image runs as the non-root `app` user. Static files are collected at web startup
into the image’s writable `/app/staticfiles` directory. This is not a secret store and must not
be used for credentials.

Keep database, Redis, and web port publishing bound to `127.0.0.1` unless a deliberate reverse
proxy or private network design changes the exposure. Never publish PostgreSQL or Redis directly
to the public internet.

## Rebuild and deployment rules

The Compose setup copies application code into the image. It does not bind-mount the repository
source into `web-ui`. A source change therefore requires a new image and a recreated container:

```bash
docker compose --env-file .env.docker up -d --build web-ui
docker compose --env-file .env.docker up -d --force-recreate web-ui
```

Use the second command when Compose built a new image but kept the existing container. Verify
the running container, not only the build output:

```bash
docker compose --env-file .env.docker ps
curl -fsS http://127.0.0.1:8001/healthz/
docker compose --env-file .env.docker logs --tail=100 web-ui
```

For a public deployment, place HTTPS and authentication in front of the web service. Set
`ALLOWED_HOSTS` to the real host names, set `CSRF_TRUSTED_ORIGINS` to the exact HTTPS origins,
enable secure cookies, and keep `DEBUG=False`. Do not expose the development HTTP port or a
VS Code tunnel as the production security boundary.

## Forbidden changes

Do not:

- use the application AWS identity as a log-viewer fallback;
- use pasted temporary credentials for submission, synchronization, S3 data downloads, or any
  request other than an authorized log lookup;
- store credentials in PostgreSQL, source control, image layers, static files, logs, local
  storage, or cookies;
- pass credentials through Docker build arguments or `RUN` commands;
- mount the credential file into the scheduler without a concrete AWS operation it must perform;
- expose raw AWS exceptions or credential material to the browser;
- make demand-log lookup accept arbitrary demand IDs without local Monitor authorization;
- publish PostgreSQL or Redis on a public interface;
- run more than one submission worker or use submission-worker concurrency greater than one;
- assume a rebuild changed a running container without checking its image and health;
- claim that a temporary credential’s expiry is known when AWS did not report it;
- add a fallback profile, default session, region, or credential source to make a failed AWS
  operation appear to work.

## Required checks for security or deployment changes

Before merging a change in this scope:

1. Inspect the complete diff for credential values, broad AWS access, and unintended mounts.
2. Run the focused credential and AWS-client tests.
3. Run `python manage.py check` in the application environment.
4. Validate the Compose file with the deployment’s real env file without printing it.
5. Rebuild and recreate the affected service when code is copied into the image.
6. Check `/healthz/` and `docker compose ps` after recreation.
7. Confirm that the running container contains the changed code and that no credential file was
   added to the image.
8. For production exposure, verify HTTPS, host validation, CSRF origins, secure cookies, and
   private database and Redis networking before sharing the URL.
