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


# --- Security (required in production) ---
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if _env_bool("DEBUG", "True"):
        SECRET_KEY = "django-insecure-dev-only-change-in-production"
    else:
        raise ValueError("SECRET_KEY environment variable is required when DEBUG=False")

DEBUG = _env_bool("DEBUG", "True")

ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
# --- Application ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "commissions",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
]

MIDDLEWARE = [
    "commissions.middleware.RequestIdMiddleware",
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
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": os.getenv("THROTTLE_USER", "120/min"),
        "anon": os.getenv("THROTTLE_ANON", "30/min"),
        "login": os.getenv("THROTTLE_LOGIN", "10/min"),
        "upload": os.getenv("THROTTLE_UPLOAD", "6/min"),
    },
}

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

    DATABASES["default"] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        ssl_require=not DEBUG,
    )

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
    frontend = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    if frontend and frontend not in origins:
        origins.append(frontend)
    if frontend.startswith("https://") and "://www." not in frontend:
        www = frontend.replace("https://", "https://www.", 1)
        if www not in origins:
            origins.append(www)
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
CORS_EXPOSE_HEADERS = ["X-Request-ID"]
CORS_PREFLIGHT_MAX_AGE = 86400

# Required if any cookie/session flows cross-origin (safe to mirror CORS origins)
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# --- Production HTTPS hardening ---
if not DEBUG:
    # Behind nginx/Caddy: terminate TLS at proxy, pass X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = _env_bool("USE_X_FORWARDED_HOST", "True")
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
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "commissions": {
            "handlers": ["console", "file"],
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
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@incentra.local")
NOTIFY_EMAILS = _env_list("NOTIFY_EMAILS", "")

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
