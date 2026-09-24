"""
Django settings for neuromed_v2.

See ARCHITECTURE.md for the reasoning behind each piece of this file —
in particular the "Open decisions" section (cloud host, translation vendor,
PWA vs. native) before adding config for those.
"""
from pathlib import Path
import environ
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-not-secure")
DEBUG = env.bool("DEBUG", default=False)

# Hosts: local defaults, plus Railway public domain when present.
_default_hosts = ["localhost", "127.0.0.1"]
_railway_domain = env("RAILWAY_PUBLIC_DOMAIN", default="")
if _railway_domain:
    _default_hosts.append(_railway_domain)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=_default_hosts)

_default_csrf = [
    "http://127.0.0.1:8003",
    "http://localhost:8003",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
if _railway_domain:
    _default_csrf.append(f"https://{_railway_domain}")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=_default_csrf)

# Production domain(s): always allowed, even when ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS
# are overridden by environment variables on Railway.
PRODUCTION_HOSTS = ["neuromedaiversion2-production.up.railway.app"]
for _host in PRODUCTION_HOSTS:
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)
    if f"https://{_host}" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

# Railway (and similar) terminate TLS at the proxy.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "channels",

    # Project apps — see ARCHITECTURE.md § App structure.
    # Deliberately absent: anything resembling v1's Organizational Portal
    # (triage / frontdesk / clinical / diagnostics / scribe / coding) and
    # the kiosk feature. See CLAUDE.md boundary #1 before adding one back.
    "accounts.apps.AccountsConfig",
    "chat",
    "visits",
    "safety",
    "care_circle",
    "documents",
    "billing",
    "compliance",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "neuromed_v2.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.greeting",
            ],
        },
    },
]

WSGI_APPLICATION = "neuromed_v2.wsgi.application"
ASGI_APPLICATION = "neuromed_v2.asgi.application"

# --- Database -----------------------------------------------------------
# PostgreSQL only, in every environment — see CLAUDE.md boundary #6.
# No SQLite fallback: local dev must match production so consent and
# escalation behavior is never tested against a database that can't
# actually hold what production holds.
_database_url = env("DATABASE_URL", default="")
if not _database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL is empty. Set it in .env, e.g. "
        "postgres://localhost:5432/neuromed_v2"
    )
DATABASES = {
    "default": dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        ssl_require=env.bool("DATABASE_SSL_REQUIRE", default=not DEBUG),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "accounts.validators.MixedPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Aira <no-reply@neuromedai.org>")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Compress for production, but avoid filename hashing so the PWA manifest
# and service-worker shell list keep stable /static/... URLs.
STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedStaticFilesStorage"
)
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_MANIFEST_STRICT = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- OpenAI ---------------------------------------------------------------
# Sole LLM vendor for this build — see CLAUDE.md boundary #5.
# A signed BAA must be active on this key's org before any pilot patient's
# data reaches it.
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")

# --- Patient files (documents/storage.py) ----------------------------------
# Every stored file is encrypted with DOCUMENT_ENCRYPTION_KEY before it leaves
# the app, so the storage provider only ever holds unreadable bytes. This matters
# for Iceberg: its delivery URLs are public with no private or signed option.
#   DOCUMENT_STORAGE=local    encrypted files under PRIVATE_MEDIA_ROOT (dev; Railway disk is ephemeral)
#   DOCUMENT_STORAGE=iceberg  encrypted files on cdn.katalyst-crm.com via its API
# Generate a key once:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Losing this key makes every stored file unreadable, so keep it in a password manager too.
DOCUMENT_STORAGE = env("DOCUMENT_STORAGE", default="local")
DOCUMENT_ENCRYPTION_KEY = env("DOCUMENT_ENCRYPTION_KEY", default="")
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))
ICEBERG_API_BASE = env("ICEBERG_API_BASE", default="https://dashboard.katalyst-crm.com")
ICEBERG_DELIVERY_BASE = env("ICEBERG_DELIVERY_BASE", default="https://cdn.katalyst-crm.com")
ICEBERG_TOKEN = env("ICEBERG_TOKEN", default="")
ICEBERG_KEY_PREFIX = env("ICEBERG_KEY_PREFIX", default="neuromed-aira/documents")
# Without a key in production, originals are simply not kept (text is still read);
# in DEBUG a throwaway key is derived from SECRET_KEY so local dev works out of the box.

# --- Feature flags ----------------------------------------------------------
# Follow the v1 pattern documented in ARCHITECTURE.md: new behavior ships
# behind a flag, defaulting to the safe/off state, with graceful fallback.
ENABLE_CARE_CIRCLE = env.bool("ENABLE_CARE_CIRCLE", default=False)

# --- Not yet wired — see ARCHITECTURE.md § Open decisions ------------------
# Translation vendor and durable media storage (Railway volume / S3) still
# need deliberate choices before pilot patient files or care-circle digests.
