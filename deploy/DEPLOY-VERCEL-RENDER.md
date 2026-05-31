# Deploy on incentra.co.in — Vercel + Render + PostgreSQL

| Layer | Host | URL |
|-------|------|-----|
| **Frontend** | Vercel | https://incentra.co.in, https://www.incentra.co.in |
| **Backend API** | Render Web Service | https://api.incentra.co.in |
| **Database** | Render PostgreSQL (or external) | linked via `DATABASE_URL` |

---

## Architecture

```
Browser → incentra.co.in (Vercel, React build)
       → api.incentra.co.in (Render, Django + Gunicorn)
       → PostgreSQL (Render)
```

---

## 1. DNS (domain registrar for incentra.co.in)

| Type | Name | Target |
|------|------|--------|
| **CNAME** | `@` or use Vercel nameservers | Vercel docs for apex domain |
| **CNAME** | `www` | `cname.vercel-dns.com` (Vercel will show exact value) |
| **CNAME** | `api` | your Render service host, e.g. `incentivepro-api.onrender.com` |

Use **Vercel → Domains** and **Render → Settings → Custom Domains** for exact DNS values.

---

## 2. PostgreSQL on Render

1. Render Dashboard → **New +** → **PostgreSQL**
2. Name: `incentivepro-db`, region near users (e.g. Singapore for India)
3. Copy **Internal Database URL** (use on Render API service)
4. Optional: copy **External Database URL** for local `manage.py` from your PC

---

## 3. Backend on Render (Web Service)

1. **New +** → **Web Service** → connect your Git repo
2. Settings:

| Setting | Value |
|---------|--------|
| **Root Directory** | `backend` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| **Pre-Deploy Command** | `python manage.py migrate --noinput` |
| **Start Command** | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
| **Health Check Path** | `/api/health/` |

3. **Environment variables** (see `deploy/render.env.example`):

```env
DEBUG=False
SECRET_KEY=<long-random-string>
DATABASE_URL=<from Render Postgres - Internal URL>
ALLOWED_HOSTS=api.incentra.co.in,incentivepro-api.onrender.com
CORS_ALLOWED_ORIGINS=https://incentra.co.in,https://www.incentra.co.in
FRONTEND_URL=https://incentra.co.in
SECURE_SSL_REDIRECT=False
USE_X_FORWARDED_HOST=True
TIME_ZONE=Asia/Kolkata
CELERY_TASK_ALWAYS_EAGER=True
```

`CELERY_TASK_ALWAYS_EAGER=True` runs imports in-process (no Redis worker). For large CSVs, add Render **Redis** + a **Background Worker** later.

4. **Custom domain:** Settings → Custom Domains → `api.incentra.co.in` → add DNS CNAME
5. After first deploy, open **Shell** on Render:

```bash
python create_admin.py
```

6. Test: https://api.incentra.co.in/api/health/

---

## 4. Frontend on Vercel

1. Vercel → **Add Project** → import repo
2. Settings:

| Setting | Value |
|---------|--------|
| **Root Directory** | `frontend` |
| **Framework Preset** | Create React App |
| **Build Command** | `npm run build` |
| **Output Directory** | `build` |

3. **Environment variables** (Production):

```env
REACT_APP_API_HOST=https://api.incentra.co.in
REACT_APP_API_BASE_URL=https://api.incentra.co.in/api
REACT_APP_USE_HTTPS=true
REACT_APP_DEBUG=false
```

4. **Domains:** add `incentra.co.in` and `www.incentra.co.in`
5. Deploy → open https://incentra.co.in/login

`frontend/vercel.json` is included for React Router (SPA fallback).

---

## 5. Post-deploy checklist

- [ ] Login works (email + password)
- [ ] User setup → upload users CSV
- [ ] Comp plan → **Active**, dates cover your order months
- [ ] Orders upload → commissions appear
- [ ] Change default admin password (do not keep `Welcome@123`)
- [ ] `DEFAULT_ONBOARDING_PASSWORD` **not** set on Render

---

## 6. Optional: async imports (Celery)

1. Render → **Redis**
2. New **Background Worker** (same repo, root `backend`):

```bash
celery -A config worker -l info
```

3. On API service set:

```env
CELERY_BROKER_URL=<redis internal url>
CELERY_RESULT_BACKEND=<redis internal url>
CELERY_TASK_ALWAYS_EAGER=False
USE_ASYNC_IMPORTS=True
```

---

## 7. File uploads note

Render web disks are **ephemeral**. CSV uploads work; stored `ImportJob` files may not persist across redeploys. For production file retention, plan S3 later.

---

## 8. Local env templates

- Backend (Render): `deploy/render.env.example`
- Frontend (Vercel): `deploy/frontend.env.production.incentra`

---

## 9. Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS error | `CORS_ALLOWED_ORIGINS` must include exact `https://incentra.co.in` |
| 400 Disallowed Host | Add `api.incentra.co.in` and `*.onrender.com` to `ALLOWED_HOSTS` |
| API 404 on Vercel | API must be on `api.` subdomain, not Vercel |
| No commissions | Plan effective dates must include `order_date` |
| DB connection fail | Use **Internal** `DATABASE_URL` on Render, not external |

---

## Alternative: Blueprint

Repo includes `render.yaml` — in Render: **New → Blueprint** → select repo (creates API + Postgres). Then configure Vercel separately.
