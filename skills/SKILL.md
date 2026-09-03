---
name: omicshub
description: Maintain, test, and operate the OmicsHub Django application and its OCS, AWS, Celery, Redis, and Docker integrations.
---

# OmicsHub

Use the repository guides as the local source of truth for OmicsHub work. Read only the guide
that covers the task, then verify its claims against the current code and tests.

- [Architecture and workers](architecture-and-workers.md): Django models, PostgreSQL, OCS
  synchronization, Celery, Redis, queue claiming, and worker behavior.
- [OCS integration](ocs-integration.md): OCS commands, demand tracing, AWS resource mapping,
  data locations, and log-stream lookup.
- [Maintainability and review](maintainability-and-review.md): diff review, Django conventions,
  dead-code checks, browser state, and validation commands.
- [Security and deployment](security-and-deployment.md): credential boundaries, Docker Compose,
  image builds, environment variables, health checks, and deployment checks.
- [UI and browser quality](ui-and-browser-quality.md): shared templates, table behavior,
  polling, log panels, race conditions, and Playwright acceptance tests.

## Rules for every change

Read the owning implementation, nearby tests, configuration, and relevant guide before editing.
Use the existing Django, Boto3, Celery, Redis, Docker, and browser patterns. Make the smallest
complete change that preserves the current behavior.

Do not add a substitute credential source, wrapper, compatibility path, speculative abstraction,
or broad defensive branch. Use conditionals only for known application states or documented
external responses. Do not use temporary log-viewer credentials for synchronization,
submission, S3 browsing, or any other operation. Do not expose or persist real credentials.
Never place credentials, tokens, or copied AWS output in this directory or in tests.

Use the current code as the authority when a guide and the implementation differ. Fix the guide
in the same change. When a change affects polling, workers, credentials, or a shared UI control,
update the guide that owns that behavior and add a regression test for the user-visible result.

After editing, inspect the complete diff, run focused tests, run the applicable formatter and
linter, and report checks that could not run because of local services or credentials.

## Writing style for these guides

Use direct sentences and concrete project terms such as fastq sample, command, manifest,
alignment, post-alignment, queue entry, demand ID, file-store ID, and log stream. "Manifest"
names the JSONC file an operator uploads; once stored it is a "config" (`WorkflowConfig`, the
`/configs/` pages), which is the word users see. Describe an action and its result. Avoid
abstract claims, empty commentary, and speculative future behavior.
