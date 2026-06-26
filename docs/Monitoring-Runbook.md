# Monitoring Runbook

This runbook defines production uptime and health monitoring for Incentra.

## Systems To Monitor

- Frontend marketing/app URL: `https://incentra.co.in`
- Backend health endpoint: `/api/health/`
- Backend readiness endpoint: `/api/health/ready/`
- Render backend service status
- Render PostgreSQL status
- Sentry project for backend errors

## Recommended Checks

Use an uptime tool such as Better Stack, UptimeRobot, Pingdom, or a similar monitor.

### Frontend

- URL: `https://incentra.co.in`
- Expected status: `200`
- Frequency: every 5 minutes
- Alert after: 2 failed checks

### Backend Liveness

- URL: `https://<render-backend-domain>/api/health/`
- Expected status: `200`
- Expected response contains: `"status":"ok"`
- Frequency: every 5 minutes
- Alert after: 2 failed checks

### Backend Readiness

- URL: `https://<render-backend-domain>/api/health/ready/`
- Expected status: `200`
- Frequency: every 5 minutes
- Alert after: 2 failed checks

Readiness should fail when the app cannot reach required dependencies such as the database.

## Alert Routing

Send alerts to:

- Primary owner: product/engineering owner
- Backup owner: operations/support owner
- Optional: customer support inbox if customers are impacted

Every alert should include:

- Failed URL
- Status code or timeout
- First failure time
- Last successful check time
- Link to Render logs
- Link to Sentry issue list

## Triage Steps

1. Check whether the frontend, backend health, or backend readiness monitor failed.
2. If frontend failed but backend is healthy:
   - Check Vercel deployment status.
   - Check domain/DNS status.
   - Check recent frontend deployment.
3. If backend health failed:
   - Check Render service status.
   - Check Render logs for crash loops.
   - Confirm environment variables are present.
4. If backend readiness failed but health passed:
   - Check Render PostgreSQL status.
   - Check `DATABASE_URL`.
   - Check database connection errors in Render logs and Sentry.
5. If Sentry shows new errors:
   - Assign owner.
   - Link the issue to the incident record.
   - Fix or rollback depending on severity.

## Severity Levels

- Sev 1: production app unavailable for all customers.
- Sev 2: one major workflow broken, such as login, commission calculation, order upload, or approvals.
- Sev 3: degraded feature with workaround available.
- Sev 4: cosmetic issue or documentation gap.

## Weekly Review

Review once per week:

- Uptime percentage.
- Number of incidents.
- Sentry unresolved issues.
- Slow or flaky endpoints.
- Repeated alerts.
- Follow-up actions from prior incidents.

