# Deploy And Rollback Runbook

This runbook defines the production deploy and rollback process for Incentra.

## Systems

- Backend: Render service `incentra-backend`
- Database: Render PostgreSQL `incentra-db`
- Frontend: Vercel app/domain `https://incentra.co.in`
- Repository branch: `main`
- CI/CD: GitHub Actions workflow `.github/workflows/ci-cd.yml`

## CI-gated releases (recommended)

Goal: never ship a broken build to users.

The **CI/CD** workflow runs on every pull request and every push to `main`:

1. **Test** — Django `commissions.tests` against Postgres
2. **Build** — frontend production `npm run build`
3. **Package** — backend Docker image build + import check
4. **Deploy** — only on `main`, after the quality gate, via deploy hooks
5. **Monitor** — smoke checks for `/ping`, `/api/health/`, `/api/health/ready/`, and the frontend URL

### One-time setup

1. In GitHub → **Settings → Secrets and variables → Actions**, add:
   - `RENDER_DEPLOY_HOOK_URL` — from Render → service → Deploy Hook
   - `VERCEL_DEPLOY_HOOK_URL` — from Vercel → project → Settings → Git → Deploy Hooks
   - `BACKEND_BASE_URL` — e.g. `https://api.incentra.co.in`
   - `FRONTEND_BASE_URL` — e.g. `https://incentra.co.in`
2. Create a GitHub **Environment** named `production` (optional protection rules / reviewers).
3. **Turn off auto-deploy on `main`** in Render and Vercel so only the CI/CD workflow deploys after tests pass.
4. In GitHub → branch protection for `main`, require these checks before merge:
   - `Test (backend)`
   - `Build (frontend)`
   - `Package (Docker)`
   - `Quality gate`

Until deploy-hook secrets are set, CI still blocks broken PRs; production platforms keep their current deploy behavior.

## Pre-Deploy Checklist

Before deploying:

1. Confirm latest code is pushed to GitHub.
2. Confirm the **CI/CD** workflow is green (or run locally):
   ```powershell
   cd backend
   python manage.py test commissions
   cd ..\frontend
   npm run build
   ```
3. Review changed environment variables.
4. Confirm database backup availability before migrations or risky releases.
5. Confirm there is a rollback owner.

## CRM credential encryption (required in production)

When `DEBUG=False`, the backend **will not start** without:

- `cryptography` (pinned in `backend/requirements.txt`)
- `CREDENTIALS_ENCRYPTION_KEY` (long random string; do not reuse `SECRET_KEY` in production)

Optional:

- `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS` — comma-separated old keys for decrypt during rotation
- `SECRET_MANAGER_BACKEND` — default `encrypted_db` (AWS/Azure/Vault backends are stubs)

**First production rollout after this change:**

1. Set `CREDENTIALS_ENCRYPTION_KEY` on Render **before** deploying.
2. Deploy.
3. Run: `python manage.py reencrypt_integration_credentials`
4. Confirm CRM sync still works; API responses show only `credentials_masked` (`••••••••`).

**Key rotation:**

1. Move the current key into `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS`.
2. Set a new `CREDENTIALS_ENCRYPTION_KEY`.
3. Restart the service, then run: `python manage.py rotate_credentials_encryption_key`
4. Remove previous keys once rotation succeeds.

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

