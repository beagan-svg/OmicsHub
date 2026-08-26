# OmicsHub maintainability and review

Use this guide for repository-wide cleanup, reviews, refactors, and changes that touch several
OmicsHub apps. Review the current diff first. Do not rewrite unrelated code or treat an old
conversation as stronger evidence than the implementation and tests.

## Review order

1. Run `git status --short` and compare the working tree with `HEAD`.
2. Read every changed file and the callers, tests, settings, templates, and routes around it.
3. Trace the real path from browser request to Django view, model or client boundary, task, and
   external service.
4. Check one responsibility at a time: performance, unnecessary abstraction, redundancy, dead
   code, API usage, and consistency.
5. Implement only findings that improve correctness, clarity, security, or measured performance.
6. Review the complete final diff and run focused checks before broader checks.

Keep review findings concrete. Include the file, line, observed behavior, and reason for the
change. Do not create parallel implementations while several people or agents review the same
diff. Have one owner reconcile findings before editing.

## Code decisions

- Put behavior in the Django app that owns its model or external boundary.
- Use Django ORM queries, transactions, constraints, forms, URL reversing, and template partials
  instead of custom equivalents.
- Keep views focused on request handling. Put OCS and AWS calls in `apps/ocs_integration` and
  queue selection in `apps/submission_queue`.
- Use Boto3 clients and documented paginators at the AWS boundary. Do not parse AWS CLI output
  inside application code.
- Catch only errors the application can handle. Preserve unexpected errors for the worker or
  application error handler.
- Remove helpers that only rename one call, one-use configuration layers, duplicate validation,
  unreachable branches, unused imports, stale comments, and substitute paths without a real
  supported failure mode.
- Use short domain names. Prefer `sample`, `stage`, `demand_id`, `file_store_id`, `log_stream`,
  and `s3_uri` over generic names such as `data`, `item`, `result`, or `thing`.
- Keep docstrings short, concrete, and action-oriented. Use terms such as fastq sample, library
  prep, alignment, post-alignment, command, manifest, demand ID, and log stream.

## Django and data safety

Use a migration for every model change. Use `select_for_update()` inside an atomic transaction
for queue claims. Keep queue uniqueness and user ownership rules in the model or query boundary,
not only in a view. Use `update_fields` when updating a known subset of model fields.

Treat PostgreSQL as OmicsHub's local mirror and application database. Do not assume it contains
every OCS record or use an empty AWS response to delete local records. Keep synchronization
idempotent and keep AWS synchronization separate from page polling.

## Frontend review

Use existing partials and browser scripts before creating a new component. Keep state that users
are editing outside HTML regions replaced by polling. Use delegated event listeners for controls
inside refreshed fragments. Guard asynchronous requests with ownership checks and ignore a
response after its row, panel, or request has been replaced or closed.

Tables must fit their container, keep column resizing predictable, and use the shared pager and
footer. A flexible table column may absorb unused width, but a narrow action column such as
Contents must remain narrow. Do not add fixed viewport spacers or page-wide overflow to hide a
layout problem.

Use semantic buttons, labels, `aria-expanded`, and accessible names. Tooltips are hover or focus
feedback, not state that remains after the pointer leaves. Test desktop and narrow viewports,
filters, pagination, column resizing, disclosures, polling, and pending requests with Playwright.

## Docker and CI review

Use the project env file when running Compose:

```bash
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up -d --build <service>
```

The production settings check must define every required production variable, including
`CACHE_URL`. Do not weaken production settings with defaults merely to make CI pass. Keep
credentials out of build contexts, image layers, workflow logs, and committed files.

Run the relevant checks after a change:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps omicshub docker_tools
uv run pytest -q
node --check <changed-javascript-file>
git diff --check
```

Report service or credential blockers instead of weakening a valid test. Do not commit or push
unless the user explicitly requests it.
