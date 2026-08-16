# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two populations with very different fluency, sharing one interface:

- **Pipeline operators:** a small group who work in OmicsHub daily, at a desk on a wide
  monitor. They know the vocabulary cold (modality, chemistry, demand, stage) and are
  slowed down by anything that spends screen space explaining it.
- **Lab scientists:** a larger group who submit a batch every few weeks. They do not
  remember the flow between visits, and every visit starts with re-orienting: which samples
  are mine, what stage are they at, what happens if I press this.

Use one interface for both groups: keep the operator view dense and fast, and provide
clear labels and explanations for occasional submitters.

## Product Purpose

OmicsHub queues and submits OCS alignment and post-alignment jobs. Users select fastq
samples. The backend checks each sample's stage status, shows the exact `ocs` command, and
queues the command after confirmation. One worker submits commands within the OCS job
limit and the spacing in the manifest.

Success is a submission that runs the right command against the right samples, once.

## Positioning

Show the exact command before queueing it. Re-plan each step from the manifest and current
stage status so a stage that finished while the user was reading is not submitted twice.

## Operating Context

- Sample metadata mirrors the `<env>-fastq-metadata` DynamoDB table; stage status joins
  `<env>-fastq-history` to `<env>-demand-registry`.
- Submission happens through the `ocs` CLI , the only CLI call in the project , run from a
  Celery worker.
- Work arrives in **vendor batches** (RTX/RFX/MTX prefixes) of tens to hundreds of samples.
  Users select vendor batches, and OmicsHub submits one fastq sample at a time.
- A **manifest** (uploaded JSON) supplies the reference, chemistry, and command for each
  sample's modality and library prep method. One manifest is active at a time.
- Stages run in order: ingest → alignment → post-alignment. A fastq sample can run only the
  stage its OCS history says is due.
- A wrong submission consumes compute time and money and cannot be undone through this app.

## Capabilities and Constraints

- Use Django 5, server-rendered templates, Postgres, Celery, and Redis. Keep the internal
  tool operable without a frontend build step.
- Column-configurable sample table: 24 available columns, 10 shown by default, stored per
  user.
- Cart model: samples are staged on the dashboard, then submitted from checkout against a
  chosen config.
- Two-step submission: a plan review (what will run, what will not, what the config could
  not answer) then a command confirmation.
- Per-sample command overrides: command config, reference, chemistry, or raw command text.
  Every override is re-planned server-side; an unparseable edit is rejected before queueing.
- Job monitor auto-refreshes on a 60s cadence, gated on tab visibility and user idleness.
- Statuses: PENDING, SUBMITTING, SUBMITTED, IN_PROGRESS, COMPLETED, ARCHIVED, FAILED,
  ABORTED, ABANDONED, STRANDED, CANCELLED, AWAITING_TRIGGER, INGEST_COMPLETE.
- **STRANDED** is a distinct and dangerous state: the worker stopped mid-submission and it
  is unknown whether OCS received the command. Retry is disabled for stranded jobs.
- Staff-only surfaces: manifest upload and activation, plus Django admin.

## Brand Commitments

Name: **OmicsHub**. No logo, wordmark, brand palette or typeface has been established ,
the current blue is Bootstrap's default primary, not a chosen color.

## Evidence on Hand

- Real sample data in the mirror (vendor batch names, FASTQ names, study sets, organisms,
  library prep methods) , the interface can be designed against real content.
- Real `ocs` commands produced by the command builder.
- No user research, usage analytics, testimonials, or benchmarks exist. Do not fabricate
  them.

## Product Principles

1. **Show every command.** Display the exact command before queueing it, as the main
   submission detail.
2. **Re-plan, never replay.** Every step recomputes from the config and current stage
   status. State that went stale while the user was reading is caught, not submitted.
3. **Group by vendor batch.** Fastq samples arrive, move, and fail in vendor batches, so
   show the batch while users review sample rows.
4. **Explain each state.** Describe STRANDED, ABANDONED, and AWAITING_TRIGGER so users do
   not create a duplicate job or abandon a fastq sample.
5. **One interface, two fluencies.** Density is the default; explanation is available
   without being in the way.

## Accessibility & Inclusion

WCAG 2.1 AA is the floor. The incumbent implementation already invests here (skip link,
table captions, `aria-current`, per-row action labels, `:focus-visible` rings, a
reduced-motion path that preserves state feedback) , this is a standard to keep, not a
box to check.
