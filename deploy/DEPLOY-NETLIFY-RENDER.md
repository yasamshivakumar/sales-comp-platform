# Deploy on Netlify (frontend) + Render (API + PostgreSQL)

Netlify hosts the **React app** only. Django and PostgreSQL stay on **Render** (Netlify is not suited for a full Django API).

| Layer | Host | Example URL |
|-------|------|-------------|
| **Frontend** | Netlify | `https://incentra.co.in` or `https://your-app.netlify.app` |
| **API** | Render | `https://api.incentra.co.in` |
| **Database** | Render PostgreSQL | via `DATABASE_URL` on API service |

```
Browser → Netlify (React build)
       → Render (Django + Gunicorn)
       → PostgreSQL (Render)
```

Backend setup: **[DEPLOY-VERCEL-RENDER.md](./DEPLOY-VERCEL-RENDER.md)** (sections 2–3 — same Render steps).

---

## 1. Deploy API on Render (if not done)

1. Render → **Web Service** → repo root directory: `backend`
2. Env from `deploy/render.env.example`
3. Custom domain: `api.incentra.co.in`
4. Test: `https://api.incentra.co.in/api/health/`

---

## 2. Deploy frontend on Netlify

### Option A — Git (recommended)

1. Push this repo to **GitHub** / GitLab / Bitbucket.
2. [Netlify](https://app.netlify.com) → **Add new site** → **Import an existing project**.
3. Connect the repo.
4. Netlify reads **`netlify.toml`** at repo root automatically:

| Setting | Value (from `netlify.toml`) |
|---------|-----------------------------|
| Base directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Publish directory | `build` |

5. **Environment variables** (Production) — copy from `deploy/netlify.env.example`:

```env
REACT_APP_API_HOST=https://api.incentra.co.in
REACT_APP_API_BASE_URL=https://api.incentra.co.in/api
REACT_APP_USE_HTTPS=true
REACT_APP_DEBUG=false
```

6. **Deploy site**.

### Option B — Netlify CLI (from your PC)

```powershell
cd c:\Users\Admin\sales-comp-platform
npm install -g netlify-cli
netlify login
cd frontend
copy ..\\deploy\\netlify.env.example .env.production
# Edit .env.production with your API URL, then:
npm ci
npm run build
cd ..
netlify deploy --prod --dir=frontend/build
```

First time: `netlify init` to link the site.

---

## 3. CORS on Render (required)

After Netlify gives you a URL (e.g. `https://incentivepro.netlify.app`), update the **Render** API service:

```env
CORS_ALLOWED_ORIGINS=https://incentra.co.in,https://www.incentra.co.in,https://YOUR-SITE.netlify.app
FRONTEND_URL=https://YOUR-SITE.netlify.app
```

Redeploy the Render service. Without this, login/API calls fail in the browser with a CORS error.

---

## 4. Custom domain (incentra.co.in on Netlify)

1. Netlify → **Domain management** → **Add domain** → `incentra.co.in` and `www.incentra.co.in`
2. At your registrar, point DNS to Netlify (they show exact A/CNAME records).
3. Keep **`api`** subdomain on **Render** (CNAME to `*.onrender.com`), not Netlify.
4. Add `https://incentra.co.in` and `https://www.incentra.co.in` to `CORS_ALLOWED_ORIGINS` on Render.

---

## 5. Post-deploy checklist

- [ ] `https://api.incentra.co.in/api/health/` returns OK
- [ ] Netlify site loads login page
- [ ] Login works (no CORS error in browser DevTools → Network)
- [ ] `python create_admin.py` on Render if no admin yet
- [ ] Change default password after first login

---

## 6. Netlify vs Vercel

Both work for this React app. You only need **one** frontend host:

| | Netlify | Vercel |
|---|---------|--------|
| Config | `netlify.toml` (repo root) | `frontend/vercel.json` |
| API | Still on Render | Still on Render |

Do not point both Netlify and Vercel to the same domain unless you intend a cutover.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS error | Add exact Netlify URL to Render `CORS_ALLOWED_ORIGINS` |
| API 404 on Netlify | API must be on Render; set `REACT_APP_API_BASE_URL` at **build** time |
| Blank page after refresh | `netlify.toml` redirects to `index.html` (included) |
| Old API URL in build | Change env vars on Netlify → **Trigger deploy** → **Clear cache and deploy** |
