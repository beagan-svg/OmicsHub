# OmicsHub developer skills

Read these guides before changing OmicsHub. They record the current architecture, user expectations, and failure cases that have caused regressions.

## Guides

- [OmicsHub skill](SKILL.md) is the entry point for an AI coding agent working in this repository.
- [Architecture and workers](architecture-and-workers.md) explains the Django apps, PostgreSQL records, AWS mirrors, Celery workers, Beat, Redis, queue rules, and sync flow.
- [OCS integration](ocs-integration.md) explains OCS command discovery, demand tracing, AWS resource mapping, and the separate log-credential path.
- [Maintainability and review](maintainability-and-review.md) explains how to review diffs, remove dead code, preserve Django boundaries, and validate changes.
- [UI and browser quality](ui-and-browser-quality.md) explains the dashboard layout, shared controls, live polling, monitor log panels, refresh races, and Playwright checks.
- [Security and deployment](security-and-deployment.md) explains AWS identity boundaries, temporary log-viewer credentials, Docker services, secrets, rebuilds, and release checks.

## Working rules

Keep behavior simple and visible. Extend an existing component or boundary when it already owns the behavior. Do not add a substitute path, wrapper, compatibility path, or generic helper without a concrete requirement. Use conditionals only for known application states or documented external responses.

Keep the app's AWS identity separate from credentials a user supplies for log viewing. Never place credentials, tokens, or copied AWS output in this directory or in tests.

When a change affects polling, workers, credentials, or a shared UI control, update the guide that owns that behavior and add a regression test for the user-visible result.

Use the current code as the authority when a guide and implementation differ. Fix the guide in the same change, then run the checks listed in the affected guide.

## Writing style

Use direct sentences and concrete project terms such as fastq sample, command, manifest, alignment, post-alignment, queue entry, demand ID, file-store ID, and log stream. Describe an action and its result. Avoid abstract claims, empty commentary, and speculative future behavior.
