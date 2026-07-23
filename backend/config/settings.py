"""
Django settings for Incentra / sales-comp-platform.
Load secrets from backend/.env (see .env.example).
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from backend directory when present
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        pass


def _env_bool(name, default="False"):
    return os.getenv(name, default).lower() in ("true", "1", "yes")


def _env_list(name, default):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_render_database_url(url):
    """
    Render internal URLs use short hosts like dpg-xxx-a on private DNS.
    Keep that URL when running on Render (same-region services). Outside Render,
    expand to the regional external hostname for tools that cannot resolve the short name.
    """
    if os.getenv("RENDER"):
        return url

    import re
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not re.fullmatch(r"dpg-.+-a", host):
        return url
    suffix = os.getenv("RENDER_PG_HOST_SUFFIX", ".oregon-postgres.render.com")
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    full_host = f"{host}{suffix}"
    port = f":{parsed.port}" if parsed.port else ""
    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"
    return urlunparse(parsed._replace(netloc=f"{userinfo}{full_host}{port}"))


def _sanitize_database_url(url):
    """Drop Neon params that break psycopg2 on some hosts; keep sslmode=require."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "channel_binding":
            continue
        query.append((key, value))
    if not any(k == "sslmode" for k, _ in query) and parsed.hostname and (
        str(parsed.hostname).endswith(".neon.tech")
        or str(parsed.hostname).endswith(".postgres.render.com")
    ):
        query.append(("sslmode", "require"))
    return urlunparse(parsed._replace(query=urlencode(query)))


# --- Security (required in production) ---
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if _env_bool("DEBUG", "True"):
        SECRET_KEY = "django-insecure-dev-only-change-in-production"
    else:
        raise ValueError("SECRET_KEY environment variable is required when DEBUG=False")

DEBUG = _env_bool("DEBUG", "True")

# CRM credential encryption (Fernet). Required when DEBUG=False.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(48))"
CREDENTIALS_ENCRYPTION_KEY = os.getenv("CREDENTIALS_ENCRYPTION_KEY", "").strip()
CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS = [
    item.strip()
    for item in os.getenv("CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS", "").split(",")
    if item.strip()
]
# encrypted_db | aws_secrets_manager | azure_key_vault | hashicorp_vault
SECRET_MANAGER_BACKEND = os.getenv("SECRET_MANAGER_BACKEND", "encrypted_db").strip().lower()

# Do NOT hard-fail here: Render build runs collectstatic with DEBUG=False before
# runtime env is fully validated. AppConfig.ready() enforces the key at boot.

ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
if not DEBUG:
    SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    for _host in (
        "api.incentra.co.in",
        "incentra-backend.onrender.com",
        ".onrender.com",
    ):
        if _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)
    _render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if _render_hostname and _render_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_render_hostname)

# --- Error monitoring (optional) ---
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_ENVIRONMENT = os.getenv(
    "SENTRY_ENVIRONMENT",
    "development" if DEBUG else "production",
)
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
SENTRY_SEND_DEFAULT_PII = _env_bool("SENTRY_SEND_DEFAULT_PII", "False")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=SENTRY_SEND_DEFAULT_PII,
        release=os.getenv("SENTRY_RELEASE") or os.getenv("RENDER_GIT_COMMIT") or None,
    )

# --- Application ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "commissions.apps.CommissionsConfig",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
]

MIDDLEWARE = [
    "commissions.middleware.DeployErrorMiddleware",
    "commissions.middleware.LivenessMiddleware",
    "commissions.middleware.RequestIdMiddleware",
    "commissions.middleware.SecurityHeadersMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "commissions.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --- OIDC / SSO (optional) ---
OIDC_ENABLED = _env_bool("OIDC_ENABLED", "False")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

if OIDC_ENABLED:
    INSTALLED_APPS += ["mozilla_django_oidc"]
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
    ]
    OIDC_RP_CLIENT_ID = os.environ["OIDC_RP_CLIENT_ID"]
    OIDC_RP_CLIENT_SECRET = os.environ["OIDC_RP_CLIENT_SECRET"]
    OIDC_OP_AUTHORIZATION_ENDPOINT = os.environ["OIDC_OP_AUTHORIZATION_ENDPOINT"]
    OIDC_OP_TOKEN_ENDPOINT = os.environ["OIDC_OP_TOKEN_ENDPOINT"]
    OIDC_OP_USER_ENDPOINT = os.environ["OIDC_OP_USER_ENDPOINT"]
    OIDC_OP_JWKS_ENDPOINT = os.environ.get("OIDC_OP_JWKS_ENDPOINT", "")
    OIDC_RP_SIGN_ALGO = os.getenv("OIDC_RP_SIGN_ALGO", "RS256")
    OIDC_RP_SCOPES = os.getenv("OIDC_RP_SCOPES", "openid email profile")
    OIDC_CALLBACK_CLASS = "commissions.oidc_views.TokenOIDCCallbackView"
    ALLOWED_REDIRECT_URI_SCHEMES = ["http", "https"]
    LOGIN_REDIRECT_URL = FRONTEND_URL
else:
    AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "commissions.authentication.TenantTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "commissions.permissions.IsAuthenticatedAndPasswordCurrent",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": os.getenv("THROTTLE_USER", "120/min"),
        "anon": os.getenv("THROTTLE_ANON", "30/min"),
        "login": os.getenv("THROTTLE_LOGIN", "10/min"),
        "oidc_exchange": os.getenv("THROTTLE_OIDC_EXCHANGE", "10/min"),
        "upload": os.getenv("THROTTLE_UPLOAD", "6/min"),
        "ai": os.getenv("THROTTLE_AI", "20/hour"),
        "demo": os.getenv("THROTTLE_DEMO", "5/min"),
        "webhook": os.getenv("THROTTLE_WEBHOOK", "60/min"),
    },
}

# Reject integration webhook URLs whose secret is shorter than this (defense in depth).
WEBHOOK_SECRET_MIN_LENGTH = int(os.getenv("WEBHOOK_SECRET_MIN_LENGTH", "24"))

TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "60"))
MFA_TOTP_ISSUER = os.getenv("MFA_TOTP_ISSUER", "Incentra")

# --- Upload limits (CSV imports) ---
MAX_IMPORT_FILE_BYTES = int(os.getenv("MAX_IMPORT_FILE_BYTES", str(10 * 1024 * 1024)))
MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "50000"))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(12 * 1024 * 1024))
)

# --- Login lockout (brute-force protection) ---
LOGIN_LOCKOUT_THRESHOLD = int(os.getenv("LOGIN_LOCKOUT_THRESHOLD", "8"))
LOGIN_LOCKOUT_WINDOW_SECONDS = int(os.getenv("LOGIN_LOCKOUT_WINDOW_SECONDS", "900"))
LOGIN_LOCKOUT_DURATION_SECONDS = int(os.getenv("LOGIN_LOCKOUT_DURATION_SECONDS", "900"))

# --- SSRF guard for CRM integrations ---
# Local dev may point connectors at localhost mocks; production must not.
INTEGRATIONS_ALLOW_PRIVATE_URLS = _env_bool(
    "INTEGRATIONS_ALLOW_PRIVATE_URLS", "True" if _env_bool("DEBUG", "True") else "False"
)

# Modern referrer policy (Django default is same-origin; set explicitly).
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---
_db_password = os.getenv("DB_PASSWORD")
_placeholder_passwords = {"", "your-db-password", "change-me"}
if DEBUG and (_db_password is None or _db_password in _placeholder_passwords):
    _db_password = "1234"  # local dev fallback; set real DB_PASSWORD in .env for production

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.getenv("DB_NAME", "sales_comp_db"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": _db_password or "",
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Render / Heroku style DATABASE_URL (optional; takes precedence when set)
_database_url = os.getenv("DATABASE_URL")
if _database_url:
    try:
        import dj_database_url
    except ImportError as exc:
        raise ImportError(
            "DATABASE_URL is set but dj-database-url is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    import re
    from urllib.parse import urlparse

    _database_url = _sanitize_database_url(
        _normalize_render_database_url(_database_url)
    )
    _db_host = urlparse(_database_url).hostname or ""
    _render_internal = bool(re.fullmatch(r"dpg-.+-a", _db_host))
    _render_external = _db_host.endswith(".postgres.render.com")
    _neon_host = _db_host.endswith(".neon.tech")

    DATABASES["default"] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        # Internal Render Postgres (short host) does not use SSL; external does.
        ssl_require=not DEBUG and not _render_internal,
    )
    if not DEBUG and (_render_external or _neon_host):
        DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"

# --- Auth ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Onboarding: only set when explicitly provided (never use a hardcoded default in prod)
DEFAULT_ONBOARDING_PASSWORD = os.getenv("DEFAULT_ONBOARDING_PASSWORD", "")

# --- i18n ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Celery (async CSV imports) ---
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = _env_bool(
    "CELERY_TASK_ALWAYS_EAGER",
    "True" if not CELERY_BROKER_URL else "False",
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BEAT_SCHEDULE = {
    "run-due-auto-integration-syncs": {
        "task": "commissions.tasks.run_due_auto_integration_syncs_task",
        "schedule": 300.0,
    },
}
USE_ASYNC_IMPORTS = _env_bool("USE_ASYNC_IMPORTS", "True")
ASYNC_IMPORT_MIN_ROWS = int(os.getenv("ASYNC_IMPORT_MIN_ROWS", "50"))

# --- Sentry (optional) ---
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
    )

# --- CORS ---
def _cors_allowed_origins():
    origins = _env_list(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )

    def add_origin(origin):
        if origin and origin not in origins:
            origins.append(origin)

    frontend = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    add_origin(frontend)
    if frontend.startswith("https://") and "://www." not in frontend:
        add_origin(frontend.replace("https://", "https://www.", 1))
    if frontend.startswith("https://www."):
        add_origin(frontend.replace("https://www.", "https://", 1))
    return origins


CORS_ALLOWED_ORIGINS = _cors_allowed_origins()
CORS_ALLOWED_ORIGIN_REGEXES = []
if DEBUG:
    CORS_ALLOWED_ORIGIN_REGEXES += [
        r"^http://localhost:\d+$",
        r"^http://127\.0\.0\.1:\d+$",
    ]
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-request-id",
]
CORS_EXPOSE_HEADERS = ["X-Request-ID", "X-Session-Expires-At"]
CORS_PREFLIGHT_MAX_AGE = 86400

# Required if any cookie/session flows cross-origin (safe to mirror CORS origins)
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# --- Production HTTPS hardening ---
if not DEBUG:
    # Behind nginx/Caddy: terminate TLS at proxy, pass X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Render/custom domains: prefer the Host header unless you explicitly enable forwarded host.
    USE_X_FORWARDED_HOST = _env_bool("USE_X_FORWARDED_HOST", "False")
    # Set SECURE_SSL_REDIRECT=False when the reverse proxy already redirects HTTP→HTTPS
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", "False")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True")
    SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", "True")

# --- Logging ---
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

_LOG_HANDLERS = ["console"]
if not os.getenv("RENDER"):
    _LOG_HANDLERS.append("file")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": _LOG_HANDLERS,
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": _LOG_HANDLERS,
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "commissions": {
            "handlers": _LOG_HANDLERS,
            "level": os.getenv("COMMISSIONS_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

# --- Email (pilot notifications) ---
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", "True")
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", "False")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@incentra.local")
NOTIFY_EMAILS = _env_list("NOTIFY_EMAILS", "")
DEMO_REQUEST_EMAIL = os.getenv("DEMO_REQUEST_EMAIL", "shivakumar@incentra.co.in")
INVITE_TOKEN_TTL_HOURS = int(os.getenv("INVITE_TOKEN_TTL_HOURS", "72"))

# --- Commission AI assistant (OpenAI-compatible API) ---
COMMISSION_AI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("COMMISSION_AI_API_KEY", "")
COMMISSION_AI_BASE_URL = os.getenv("COMMISSION_AI_BASE_URL", "https://api.openai.com/v1")
COMMISSION_AI_MODEL = os.getenv("COMMISSION_AI_MODEL", "gpt-4o-mini")
COMMISSION_AI_TIMEOUT = int(os.getenv("COMMISSION_AI_TIMEOUT", "45"))
# openai | ollama | auto — auto uses OpenAI when a key is set, else local Ollama
COMMISSION_AI_PROVIDER = os.getenv("COMMISSION_AI_PROVIDER", "auto").lower()
COMMISSION_AI_OLLAMA_URL = os.getenv("COMMISSION_AI_OLLAMA_URL", "http://localhost:11434/v1")
COMMISSION_AI_OLLAMA_MODEL = os.getenv("COMMISSION_AI_OLLAMA_MODEL", "llama3.2")
COMMISSION_AI_ENABLED = _env_bool(
    "COMMISSION_AI_ENABLED",
    "True",
)
AI_PLAN_BUILDER_ENABLED = _env_bool("AI_PLAN_BUILDER_ENABLED", "True")
AI_DASHBOARD_INSIGHTS_ENABLED = _env_bool("AI_DASHBOARD_INSIGHTS_ENABLED", "True")
COMMISSION_AI_MAX_PROMPT_CHARS = int(os.getenv("COMMISSION_AI_MAX_PROMPT_CHARS", "24000"))
COMMISSION_AI_MAX_RESPONSE_CHARS = int(os.getenv("COMMISSION_AI_MAX_RESPONSE_CHARS", "48000"))
