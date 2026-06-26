# Incentra Production Readiness Checklist

Use this checklist to move Incentra from MVP to a commercial SaaS product. Work through it in order; each item should be verified before relying on it for paying customers.

## 1. Core Product Stability

Goal: the main compensation workflow must work reliably before adding more product surface.

- [x] User setup supports tenant-scoped participants.
- [x] Invite-based employee registration is implemented.
- [x] Compensation plans support monthly effective periods.
- [x] Orders can be created/uploaded and scoped to an organization.
- [x] Commission calculation aggregates employee orders by month before calculating incentives.
- [x] Commission approval and payout status are tracked.
- [x] Employee incentive details reconcile generated commissions.
- [x] Disputes can be raised, resolved, acknowledged, and deleted.
- [x] Backend regression tests cover commission logic, tenant isolation, invite flow, disputes, order status transitions, and aggregate calculations.
- [ ] Add frontend regression tests for compensation plan edit/rate edit workflows.
- [x] Add a smoke-test checklist for every production deploy.

## 2. Production Operations

Goal: production failures should be visible, recoverable, and easy to diagnose.

- [x] Health check endpoint exists: `/api/health/`.
- [x] Readiness endpoint exists: `/api/health/ready/`.
- [x] Audit logs exist for sensitive actions.
- [x] Enable automated PostgreSQL backups in Render.
- [x] Document database restore steps.
- [x] Add application error monitoring, for example Sentry.
- [x] Add uptime monitoring for frontend, backend health, and readiness.
- [x] Document deploy and rollback steps.
- [ ] Define production log retention and review process.

## 3. Enterprise Security

Goal: customer data remains isolated and access-controlled.

- [x] Organization-based tenant isolation exists.
- [x] Tenant isolation API tests exist.
- [x] Public employee signup is disabled.
- [x] Employee login uses invite-based activation.
- [x] Role checks exist for admin, finance, manager, and rep workflows.
- [x] Token expiry is configured.
- [ ] Add a security checklist for every release.
- [ ] Add documented secret rotation process.
- [ ] Add periodic access review process for admins and finance users.
- [ ] Confirm production `DEBUG=False`, strict `ALLOWED_HOSTS`, and correct CORS origins.

## 4. Integrations

Goal: customer systems can feed Incentra without manual effort.

- [x] CSV import is supported.
- [x] Async order import path exists for larger uploads.
- [x] Generic external integration models and sync logs exist.
- [x] Salesforce/generic REST integration modules exist.
- [x] Webhook endpoints exist for integrations.
- [ ] Complete end-to-end integration setup guide.
- [ ] Add integration retry/backoff policy.
- [ ] Add customer-facing field mapping documentation.
- [ ] Add integration monitoring alerts for failed syncs.

## 5. Customer Readiness

Goal: customers can onboard, understand the product, and get help.

- [x] User guide exists: `docs/Incentra-User-Guide.md`.
- [x] Marketing site exists.
- [ ] Add admin onboarding checklist.
- [ ] Add support process: email, SLA targets, triage workflow.
- [ ] Add pricing/package assumptions.
- [ ] Add privacy policy and terms of service.
- [ ] Add sample demo company data and walkthrough.

## Production Deploy Smoke Test

Run this after each production deploy:

1. Open the marketing site.
2. Log in as a company admin.
3. Create or edit a participant.
4. Create or edit a compensation plan.
5. Add or edit a rate/lookup tier.
6. Upload or create a successful order.
7. Recalculate commissions.
8. Approve a commission.
9. Log in as the employee and open Incentive Details.
10. Verify dashboard totals and currency for the selected business group.
11. Export payroll CSV.
12. Check Render logs for new errors.

## Sentry Error Monitoring Setup

Backend Sentry monitoring is optional and only runs when `SENTRY_DSN` is set.

Render backend env vars:

```text
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.0
SENTRY_SEND_DEFAULT_PII=False
```

After adding these variables, redeploy the Render backend and confirm new server errors appear in the Sentry project.

## Current Verification Commands

Backend:

```powershell
cd backend
python manage.py test commissions
```

Frontend:

```powershell
cd frontend
npm run build
```

