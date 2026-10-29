"""Public API process (lozhka-api, port 8010): customers, web shop and app. No staff access."""
from .base import *  # noqa: F403
from .base import INSTALLED_APPS as _ALL_APPS
from .base import IS_LOCAL, PUBLIC_MIDDLEWARE, env, env_list

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-public-secret-key" if IS_LOCAL else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY is required outside local development")

# the public process has no staff console: no admin, no axes, no backoffice app
INSTALLED_APPS = [a for a in _ALL_APPS if a not in ("django.contrib.admin", "django.contrib.messages", "axes", "lozhka_backoffice")]
ROOT_URLCONF = "config.urls_public"
MIDDLEWARE = PUBLIC_MIDDLEWARE
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api.localhost,shop.localhost" if IS_LOCAL else ""
)
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://shop.localhost:3010,http://localhost:3010" if IS_LOCAL else ""
)
SESSION_COOKIE_NAME = env("PUBLIC_SESSION_COOKIE_NAME", "lozhka_sid")
CSRF_COOKIE_NAME = env("PUBLIC_CSRF_COOKIE_NAME", "lozhka_csrf")
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # "remember me" is handled per login
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
PROCESS = "public"
