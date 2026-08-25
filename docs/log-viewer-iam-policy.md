# IAM policy for the Job Monitor log viewer

The Job Monitor page lets a signed-in user paste their own temporary AWS credentials to
view a demand's container logs. This document is **advisory, not enforced**: the app
only ever calls the six AWS operations listed below (see
`apps/ocs_integration/log_credentials.py`), but it has no way to shrink the IAM
permissions actually attached to whatever credentials a user pastes in. If a user pastes
credentials with broad permissions, those permissions exist regardless of what this app
does with them. Mint credentials for this feature from a role scoped to the policy below,
not from a broader one, if you want the advisory and the reality to match.

## Minimum policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": "sts:GetCallerIdentity", "Resource": "*"},
    {"Effect": "Allow", "Action": "dynamodb:GetItem", "Resource": "*"},
    {"Effect": "Allow", "Action": "states:ListExecutions", "Resource": "*"},
    {"Effect": "Allow", "Action": "states:GetExecutionHistory", "Resource": "*"},
    {"Effect": "Allow", "Action": "batch:DescribeJobs", "Resource": "*"},
    {
      "Effect": "Allow",
      "Action": "logs:GetLogEvents",
      "Resource": "arn:aws:logs:*:*:log-group:/aws/batch/job:*"
    }
  ]
}
```

## Why each one

- `sts:GetCallerIdentity` — validates the pasted credentials and shows the account/role
  they belong to. Cannot be scoped further; AWS requires `Resource: "*"` for this action.
- `states:GetExecutionHistory` — walks a demand's Step Functions execution to find the
  AWS Batch job it submitted. Discovered necessary during implementation, not part of
  the original three-operation sketch: a demand's own execution starts smaller nested
  executions before the one that submits the container job, and only this call can find
  the `JobId` (there is no direct demand-id-to-job-id lookup). `states:DescribeExecution`
  is never called — only the history is read.
- `dynamodb:GetItem` — reads the failed demand's workflow name from the demand registry so
  the app can locate that demand's Step Functions execution. This lookup runs only with
  the temporary credentials supplied for log viewing.
- `states:ListExecutions` — matches the failed demand id to its execution name before the
  existing execution-history traversal finds the Batch job.
- `batch:DescribeJobs` — resolves a Batch job id to its CloudWatch log stream name.
- `logs:GetLogEvents` — reads the log lines from the start of the selected stream, scoped
  to the one log group this organization's Batch jobs write to.

## What is deliberately absent

- No `logs:*`, no `batch:*`, no `states:*` wildcard action.
- No `stepfunctions:StartExecution`, no `batch:SubmitJob`, no `batch:TerminateJob` — this
  feature only ever reads, never starts or stops anything.
- No S3 permission or any permission this app's own long-lived identity
  (`settings.AWS_PROFILE`, used by `apps/ocs_integration/dynamodb.py` and `s3.py`) has.
  The two are entirely separate boto3 sessions; a user's pasted credentials are never
  used for data sync, job submission, or any S3 read/write this app performs elsewhere.
- No CloudWatch metrics permission (`cloudwatch:GetMetricData`). Checked directly against
  the account this app targets before deciding: `containerInsights` is disabled on every
  Batch-backed ECS cluster, and both the `ECS/ContainerInsights` and `AWS/Batch`
  CloudWatch namespaces return zero metrics. Real CPU/memory utilization is not available
  through any AWS API for this account today, so the log viewer says exactly that rather
  than requesting a permission that would return nothing.
