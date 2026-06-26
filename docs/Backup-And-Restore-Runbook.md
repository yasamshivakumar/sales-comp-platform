# Backup And Restore Runbook

This runbook covers Incentra production database backups and restore checks for Render PostgreSQL.

## Scope

- Backend: Render Django service
- Database: Render PostgreSQL
- Frontend: Vercel React app, no customer data stored in the frontend

## Backup Policy

- Enable Render PostgreSQL automated backups for the production database.
- Keep at least 7 daily restore points for normal operations.
- Before major releases or data migrations, create a manual backup/snapshot if the Render plan supports it.
- Store database credentials only in Render environment variables. Do not export production data to local machines unless required for an incident.

## Enable Automated Backups In Render

1. Open Render dashboard.
2. Select the production PostgreSQL database, for example `incentra-db`.
3. Confirm the database is on a plan that supports backups.
4. Open the Backups or Snapshots section.
5. Confirm automatic backups are enabled.
6. Record the retention period and last successful backup time.

## Restore Decision Checklist

Only restore production after confirming:

- The issue is data loss, destructive import, failed migration, or corrupted production data.
- The latest safe restore point is known.
- The customer/admin impact is documented.
- The app owner approves the restore.
- A maintenance window is announced if users are active.

## Restore Process

1. Put the backend in maintenance mode if available, or pause user writes by temporarily disabling the backend service.
2. In Render, select the backup/restore point.
3. Restore into a new database first when possible.
4. Validate the restored database:
   - Can Django connect?
   - Does `python manage.py migrate --check` pass?
   - Can an admin log in?
   - Are organizations, users, plans, orders, and commissions present?
5. Point the backend `DATABASE_URL` to the restored database.
6. Redeploy the backend.
7. Run the production deploy smoke test in `docs/Production-Readiness-Checklist.md`.
8. Monitor Render logs and Sentry for errors.

## Post-Restore Verification

Verify these workflows:

1. Admin login.
2. User Setup loads expected participants.
3. Compensation Plans load expected plans and tiers.
4. Orders load expected recent orders.
5. Dashboard totals are reasonable for one known business group.
6. Employee Incentive Details loads for one known rep.
7. Payroll export works for a small date range.

## Incident Record

For every restore, record:

- Date/time of incident.
- Restore point used.
- Reason for restore.
- Approver.
- Expected data loss window, if any.
- Smoke-test results.
- Follow-up action to prevent recurrence.

