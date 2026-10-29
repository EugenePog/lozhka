"""Settings shared by the public API and the staff console.

Both processes are the same Django project with different settings modules (docs 06 section 7.1):
own secret key, own session cookie, own host names, own database role.
Both install the SAME apps, so `migrate` produces one schema whichever module runs it.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # services/api/src
REPO_ROOT = BASE_DIR.parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in (env(name, default) or "").split(",") if item.strip()]


LOZHKA_ENV = env("LOZHKA_ENV", "local")  # local | staging | production
IS_LOCAL = LOZHKA_ENV == "local"
DEBUG = env_bool("DJANGO_DEBUG", IS_LOCAL)

# --- database: one role per process (LOZHKA_DATABASE_URL), the owner role for migrations --------------------

def database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or 5432),
        # app tables live in the app schema (docs 02 section 3); gold/ops are always schema-qualified
        "OPTIONS": {"options": "-c search_path=app,public"},
        "CONN_MAX_AGE": 60,
    }


DATABASES = {
    "default": database_from_url(
        env("LOZHKA_DATABASE_URL")
        or env("LOZHKA_DATABASE_URL_OWNER")
        or "postgresql://lozhka_owner:change-me@localhost:5432/lozhka"
    )
}

# --- apps ------------------------------------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "axes",
    "ninja",
    "lozhka_api.core",
    "lozhka_api.catalog",
    "lozhka_api.customers",
    "lozhka_api.procurement",
    "lozhka_api.sales",
    "lozhka_backoffice",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- i18n and time ---------------------------------------------------------------------------------------------
LANGUAGES = [("nl", "Nederlands"), ("en", "English"), ("ru", "Русский")]
LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Amsterdam"  # stored as UTC, shown and bucketed in local time (docs 01 section 6)
USE_I18N = True
USE_TZ = True

# --- security --------------------------------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# never set SESSION_COOKIE_DOMAIN: cookies stay host-only so customer and staff sessions cannot meet
SESSION_COOKIE_SECURE = not IS_LOCAL
CSRF_COOKIE_SECURE = not IS_LOCAL
SECURE_HSTS_SECONDS = 0 if IS_LOCAL else 31536000

SUPPLIER_SECRET_PUBLIC_KEY = env("SUPPLIER_SECRET_PUBLIC_KEY", "")  # PEM, used to WRITE credentials only

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
            ]
        },
    }
]

STATIC_URL = "/static/"
SEEDS_DIR = Path(os.environ.get("LOZHKA_SEEDS_DIR", REPO_ROOT / "db" / "seeds"))
STATIC_ROOT = REPO_ROOT / ".static"
MEDIA_URL = "/media/"
MEDIA_ROOT = REPO_ROOT / ".media"

# Order / checkout rules default here; the live values are in app.setting (docs 02 section 4.5)
DEFAULT_MIN_ORDER_CENTS = 5000

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

PUBLIC_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

BACKOFFICE_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "axes.middleware.AxesMiddleware",
    "lozhka_backoffice.middleware.StaffAccessMiddleware",
]
MIDDLEWARE = PUBLIC_MIDDLEWARE
