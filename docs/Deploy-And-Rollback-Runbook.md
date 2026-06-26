# Deploy And Rollback Runbook

This runbook defines the production deploy and rollback process for Incentra.

## Systems

- Backend: Render service `incentra-backend`
- Database: Render PostgreSQL `incentra-db`
- Frontend: Vercel app/domain `https://incentra.co.in`
- Repository branch: `main`

## Pre-Deploy Checklist

Before deploying:

1. Confirm latest code is pushed to GitHub.
2. Confirm backend tests pass:
   ```powershell
   cd backend
   python manage.py test commissions
   ```
3. Confirm frontend build passes if frontend changed:
   ```powershell
   cd frontend
   npm run build
   ```
4. Review changed environment variables.
5. Confirm database backup availability before migrations or risky releases.
6. Confirm there is a rollback owner.

## Backend Deploy On Render

1. Open Render dashboard.
2. Select `incentra-backend`.
3. Trigger deploy from the latest `main` commit, or wait for auto-deploy.
4. Watch build logs.
5. Confirm migrations run successfully.
6. Confirm Gunicorn starts.
7. Open `/api/health/`.
8. Open `/api/health/ready/`.

## Frontend Deploy On Vercel

1. Open Vercel dashboard.
2. Select the Incentra frontend project.
3. Trigger deploy from the latest `main` commit, or wait for auto-deploy.
4. Confirm build succeeds.
5. Open `https://incentra.co.in`.
6. Confirm frontend calls the production backend API.

## Production Smoke Test

Run after every production deploy:

1. Open marketing site.
2. Log in as company admin.
3. Create or edit a participant.
4. Create or edit a compensation plan.
5. Add or edit a rate/lookup tier.
6. Upload or create a successful order.
7. Recalculate commissions.
8. Approve a commission.
9. Log in as the employee and open Incentive Details.
10. Verify dashboard totals and selected business group currency.
11. Export payroll CSV.
12. Check Render logs and Sentry for new errors.

## Rollback Decision

Rollback when:

- Login is broken.
- Commission calculation is broken.
- Order upload/import is broken.
- Tenant isolation or permissions are suspected broken.
- Backend deploy fails and cannot recover quickly.
- Frontend deploy blocks critical workflows.

## Backend Rollback

1. Open Render deploy history.
2. Select the last known good deploy.
3. Use Render rollback/redeploy previous deploy.
4. If a migration changed data or schema, review database restore needs before rolling back code.
5. Confirm `/api/health/` and `/api/health/ready/`.
6. Run the production smoke test.

## Frontend Rollback

1. Open Vercel deployments.
2. Promote the previous known good deployment.
3. Confirm `https://incentra.co.in` loads.
4. Run login and dashboard smoke checks.

## Post-Deploy Record

Record:

- Commit SHA.
- Backend deploy ID.
- Frontend deploy ID.
- Migration status.
- Smoke-test result.
- Any Sentry/Render errors.
- Rollback decision, if applicable.

