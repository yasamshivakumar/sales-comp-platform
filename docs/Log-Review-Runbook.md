# Log Review Runbook

This runbook defines how to review production logs for Incentra.

## Log Sources

- Render backend logs for Django/Gunicorn output.
- Render deploy/build logs.
- Render PostgreSQL logs and metrics.
- Sentry issues for backend exceptions.
- Vercel deployment/build logs for frontend failures.
- Uptime monitor incident history.

## What To Review Daily

Check Render backend logs for:

- `ERROR` or unhandled exception tracebacks.
- Repeated `WARNING` messages.
- Failed email sends.
- Failed CSV import jobs.
- AI provider failures.
- Database connection errors.
- Permission denied spikes.
- Repeated 400/403/500 responses.

Check Sentry for:

- New unresolved issues.
- Regressions after deploy.
- High-frequency errors.
- Errors affecting login, commission calculation, uploads, approvals, payouts, or tenant isolation.

## What To Review Weekly

Review:

- Top 10 backend errors.
- Open Sentry issues by severity.
- Uptime monitor availability.
- Failed deploys.
- Database warnings or storage growth.
- Slow imports or recurring upload failures.
- Repeated customer support issues.

## Severity And Response

- Sev 1: app unavailable, database unavailable, tenant isolation risk, or login broken. Respond immediately and consider rollback.
- Sev 2: core workflow broken, such as commission calculation, upload, approval, or payout export. Fix same day.
- Sev 3: feature degraded with workaround. Schedule fix.
- Sev 4: cosmetic or documentation issue. Track normally.

## Retention Policy

- Keep Render logs according to the active Render plan.
- Keep Sentry issues for at least 30 days.
- Keep incident records permanently in the support/ops tracker.
- Do not copy production logs containing personal data into public tickets or chats.

## Log Review Checklist

For each review, record:

- Date and reviewer.
- New critical errors.
- Error count trend.
- Any customer-impacting issue.
- Linked Sentry issues.
- Linked incident records.
- Follow-up owner and deadline.

## Escalation

Escalate immediately when logs indicate:

- Cross-tenant data access risk.
- Authentication bypass or suspicious login behavior.
- Database corruption or migration failure.
- Commission calculations failing for many orders.
- Email invites failing across customers.
- Payment/payout export data is wrong.

## Closing A Log Issue

Before closing:

1. Confirm fix is deployed.
2. Confirm Sentry issue is resolved or ignored with a reason.
3. Confirm logs are clean for at least one normal usage cycle.
4. Add a note to the incident/support tracker.

