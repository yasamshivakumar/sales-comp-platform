# IncentivePro — Sales Compensation Platform

Manage compensation plans, sales participants, orders, and commission calculations with role, position, and hierarchy rules.

## Project structure

```
sales-comp-platform/
├── backend/          Django API + PostgreSQL (git repo)
├── frontend/         React UI (Create React App)
└── README.md
```

## Quick start (development)

### 1. Backend

```powershell
cd backend
python -m venv myenv
.\myenv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env: DB_PASSWORD, optional DEFAULT_ONBOARDING_PASSWORD for pilot
python manage.py migrate
python create_admin.py
python manage.py runserver
```

API: `http://localhost:8000/api/`

### 2. Frontend

```powershell
cd frontend
npm install
copy .env.example .env
npm start
```

App: `http://localhost:3000`

### 3. Demo data (optional)

```powershell
cd backend
.\myenv\Scripts\python.exe seed_demo.py
```

## Phase 4 — Production scale

| Capability | Details |
|------------|---------|
| **Multi-tenant** | `Organization` model; users/plans/orders scoped per company (default org for existing data) |
| **Async CSV imports** | Large order uploads (≥50 rows) queued via Celery + Redis; poll `GET /api/import-jobs/{id}/` |
| **SSO (OIDC)** | Set `OIDC_ENABLED=True` + IdP endpoints — login redirects to `/oidc/authenticate/` |
| **Sentry** | Set `SENTRY_DSN` for error tracking |
| **Docker worker** | `docker compose up` runs `api`, `worker`, `redis`, `db` |

```powershell
# Async imports locally
# In backend/.env: CELERY_BROKER_URL=redis://localhost:6379/0
redis-server   # or docker run -p 6379:6379 redis:7-alpine
cd backend
.\myenv\Scripts\celery.exe -A config worker -l info
```

Frontend: `REACT_APP_OIDC_ENABLED=true` shows **Sign in with SSO**.

## Phase 3 — Pilot operations (10–50 users)

| Capability | Details |
|------------|---------|
| **Health checks** | `GET /api/health/` (liveness), `GET /api/health/ready/` (DB readiness) |
| **Rate limits** | Login/signup `10/min`, CSV uploads `6/min`, API `120/min` (env-tunable) |
| **Audit log** | `GET /api/audit-logs/` — admin & finance roles; tracks login, uploads, approve, recalc |
| **Email alerts** | Set `NOTIFY_EMAILS` — order upload summary emailed to ops |
| **Finance role** | `Finance` / `Finance Viewer` — view audit log + payroll export (no approve/recalc) |
| **Docker** | `docker compose up --build` from repo root (Postgres + API) |
| **CI** | GitHub Actions runs migrations + `commissions.tests` on backend changes |

```powershell
# Docker pilot (from repo root)
copy backend\.env.example backend\.env
# Set SECRET_KEY, DB_PASSWORD=postgres for compose
docker compose up --build
```

Request tracing: every response includes `X-Request-ID` (also stored on audit rows).

## Phase 2 — Business controls

- **Plan effective dates**: Commission lookup uses `order.order_date` against each plan’s `effective_start_date` / `effective_end_date`.
- **Commission status**: New rows are `calculated`; admins approve for payroll (`approved`).
- **Protected payouts**: Re-upload / recalc skips orders with approved commissions unless you run **Recalculate period** and confirm force replace.
- **Payroll export**: `GET /api/commissions/export/?start_date=&end_date=&status=approved` (CSV).
- **Bulk approve**: `POST /api/commissions/approve/` with `{ "start_date", "end_date" }` or `{ "ids": [1,2,3] }`.
- **Bulk recalc**: `POST /api/commissions/recalculate/` with `{ "start_date", "end_date", "force": true|false }`.

In the UI: **Commissions** tab → set period dates → Approve / Export / Recalculate (admin only).

## Production checklist (Phase 1)

- [ ] Copy `backend/.env.example` → `backend/.env` with strong `SECRET_KEY`
- [ ] Set `DEBUG=False` on the server
- [ ] Set `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` to your real domain(s)
- [ ] Use HTTPS (Vercel + Render terminate TLS on your domains)
- [ ] Do **not** set `DEFAULT_ONBOARDING_PASSWORD` in production (or force password reset)
- [ ] PostgreSQL backups scheduled (daily minimum)
- [ ] Run `python manage.py collectstatic` if serving Django admin/static
- [ ] Build frontend: `npm run build` and serve `build/` behind HTTPS

## Environment variables (backend)

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Prod yes | Django secret |
| `DEBUG` | Yes | `False` in production |
| `ALLOWED_HOSTS` | Yes | Comma-separated domains |
| `DB_*` | Yes | PostgreSQL connection |
| `CORS_ALLOWED_ORIGINS` | Yes | Frontend URL(s) |
| `DEFAULT_ONBOARDING_PASSWORD` | No | Dev/pilot only; leave empty in prod |
| `TIME_ZONE` | No | Default `Asia/Kolkata` |
| `NOTIFY_EMAILS` | No | Comma-separated ops inboxes for upload alerts |
| `EMAIL_*` | No | SMTP when not using console backend |
| `THROTTLE_*` | No | DRF rate limits (login/upload/user) |

## Required fields (everything else is optional)

**User setup:** `email`, `role` (must match plan role), `employee_id` (must match orders), `name`

**Orders:** `order_id`, `order_date`, `employee_id`, `sales_amount`

**Compensation plan:** `plan_name`, `role`, `status` (= Active), `plan_basis` (= Role), `effective_start_date`, `commission_table_type` (RATE/FLAT)

Commission matching also needs plan **effective dates** to include each order’s `order_date`, and at least one **rate tier** on the plan.

## Commission rules

1. **Position plan** (if `position_name` matches)  
2. Else **role plan** (plan has role, no position)  
3. **Hierarchy**: `split_percentage` = % kept by the rep; manager gets the rest  

Re-uploading the same `order_id` **replaces** calculated commissions (no duplicates). Approved commissions are locked until an admin force-recalculates.

## Tests

```powershell
cd backend
.\myenv\Scripts\python.exe manage.py test commissions.tests
```

After pulling Phase 2:

```powershell
.\myenv\Scripts\python.exe manage.py migrate
```

## Deploy on incentra.co.in

**API + database:** Render + PostgreSQL → **[deploy/DEPLOY-VERCEL-RENDER.md](deploy/DEPLOY-VERCEL-RENDER.md)** (sections 2–3)

**Frontend (pick one):**

| Host | Guide |
|------|--------|
| **Netlify** | [deploy/DEPLOY-NETLIFY-RENDER.md](deploy/DEPLOY-NETLIFY-RENDER.md) — uses root `netlify.toml` |
| **Vercel** | [deploy/DEPLOY-VERCEL-RENDER.md](deploy/DEPLOY-VERCEL-RENDER.md) — uses `frontend/vercel.json` |

| Layer | URL |
|-------|-----|
| Frontend | https://incentra.co.in |
| API (Render) | https://api.incentra.co.in |

Env templates: `deploy/render.env.example`, `deploy/netlify.env.example`, `deploy/frontend.env.production.incentra`

## Git

Backend is versioned under `backend/.git`. Track `frontend/` in the same remote or a separate repo before production deploy.
