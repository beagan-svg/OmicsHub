# Database Schema Documentation

The database schema (all models, fields, relationships, and the job/queue
lifecycle) is documented in a single canonical place:

➡️ **[`ocs/docs/models.md`](../ocs/docs/models.md)**

This file used to hold a second, hand-maintained copy of the schema that drifted
out of sync with `ocs/models.py`. To avoid that drift, keep `ocs/docs/models.md`
as the one source of truth and update it whenever the models change.
