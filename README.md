# Incentra — Sales Compensation Platform

Manage compensation plans, sales participants, orders, and commission calculations with role, position, and hierarchy rules.

## Project structure

```
sales-comp-platform/
├── backend/          Django API (manage.py, config/, commissions/)
├── frontend/         React UI (Create React App)
└── README.md
```

**Note:** All Django code lives under `backend/` only.

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

## Optional features

| Capability | Details |
|------------|---------|
| **Multi-tenant** | `Organization` model; users/plans/orders scoped per company |
| **Async CSV imports** | Large order uploads (≥50 rows) via Celery + Redis; poll `GET /api/import-jobs/{id}/` |
| **SSO (OIDC)** | Set `OIDC_ENABLED=True` + IdP endpoints |
| **Health checks** | `GET /api/health/`, `GET /api/health/ready/` |
| **Audit log** | `GET /api/audit-logs/` — admin & finance roles |

```powershell
# Async imports locally
# In backend/.env: CELERY_BROKER_URL=redis://localhost:6379/0
redis-server
cd backend
.\myenv\Scripts\celery.exe -A config worker -l info
```

## Business controls

- **Plan effective dates**: Commission lookup uses `order.order_date` against each plan’s effective dates.
- **Order status**: Commission is calculated only when `order_status` is **Success**.
- **Commission status**: New rows are `calculated`; admins approve for payroll.
- **Protected payouts**: Re-upload / recalc skips approved commissions unless force recalc.
- **Payroll export**: `GET /api/commissions/export/?start_date=&end_date=&status=approved`

## Environment variables

See `backend/.env.example` and `frontend/.env.example`.

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret (required in production) |
| `DEBUG` | `True` for local dev |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `DB_*` | PostgreSQL connection |
| `CORS_ALLOWED_ORIGINS` | Frontend URL(s) |
| `DATABASE_URL` | Optional Postgres URL (overrides `DB_*`) |

## Deploy: Render Backend + Vercel Frontend

### Render (Django API)

Use the root `render.yaml` blueprint. It creates:

- `incentra-backend` web service from `backend/`
- `incentra-db` PostgreSQL database

After Render creates the backend URL, set these backend env vars:

```text
DEBUG=False
ALLOWED_HOSTS=your-render-service.onrender.com,.onrender.com
FRONTEND_URL=https://your-vercel-app.vercel.app
CORS_ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-vercel-app.vercel.app
```

The Render start command runs migrations and starts Gunicorn.

### Vercel (React UI)

Use the root `vercel.json`. Set this Vercel env var before deploying:

```text
REACT_APP_API_BASE_URL=https://your-render-service.onrender.com/api
```

Then redeploy the Vercel project so the React build includes the Render API URL.

## User guide

**[docs/Incentra-User-Guide.md](docs/Incentra-User-Guide.md)** (also at `/Incentra-User-Guide-Full.md` in the frontend public folder)

## Production readiness

Use **[docs/Production-Readiness-Checklist.md](docs/Production-Readiness-Checklist.md)** to move Incentra from MVP to a commercial SaaS product step by step.

Operational runbooks:

- **[docs/Backup-And-Restore-Runbook.md](docs/Backup-And-Restore-Runbook.md)**

## Required fields

**User setup:** `email`, `role`, `employee_id`, `name`

**Orders:** `order_id`, `order_date`, `employee_id`, `sales_amount`

**Compensation plan:** `plan_name`, `role`, `status` (= Active), `effective_start_date`, `commission_table_type` (RATE/FLAT/LOOKUP)

## Commission rules

1. **Position plan** (if `position_name` matches)
2. Else **role plan**
3. **Hierarchy**: `split_percentage` = % kept by the rep; manager gets the rest

## Tests

```powershell
cd backend
.\myenv\Scripts\python.exe manage.py test commissions.tests
```
