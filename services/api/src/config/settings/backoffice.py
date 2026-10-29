"""Staff console process (lozhka-backoffice, port 8011): own secret, cookies, host name, lock-out."""
from .base import *  # noqa: F403
from .base import BACKOFFICE_MIDDLEWARE, IS_LOCAL, env, env_list

SECRET_KEY = env("BACKOFFICE_SECRET_KEY", "dev-only-staff-secret-key" if IS_LOCAL else None)
if not SECRET_KEY:
    raise RuntimeError("BACKOFFICE_SECRET_KEY is required outside local development")

ROOT_URLCONF = "config.urls_backoffice"
MIDDLEWARE = BACKOFFICE_MIDDLEWARE
ALLOWED_HOSTS = env_list(
    "BACKOFFICE_ALLOWED_HOSTS", "office.localhost,localhost,127.0.0.1" if IS_LOCAL else ""
)
CSRF_TRUSTED_ORIGINS = env_list(
    "BACKOFFICE_CSRF_TRUSTED_ORIGINS", "http://office.localhost:8011" if IS_LOCAL else ""
)
SESSION_COOKIE_NAME = env("BACKOFFICE_SESSION_COOKIE_NAME", "lozhka_staff_sid")
CSRF_COOKIE_NAME = env("BACKOFFICE_CSRF_COOKIE_NAME", "lozhka_staff_csrf")
SESSION_COOKIE_AGE = int(env("STAFF_SESSION_MINUTES", "60")) * 60  # ends after inactivity (SC01)
SESSION_SAVE_EVERY_REQUEST = True  # sliding expiry: the timeout counts from the last request
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # repeated failures lock the account (docs 06 7.1 item 2)
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = int(env("STAFF_LOGIN_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = 0.1  # hours: "a few minutes"
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ADMIN = False

TEMPLATES = [{**base_template, "OPTIONS": {"context_processors": [*base_template["OPTIONS"]["context_processors"], "lozhka_backoffice.context.staff"]}}
             for base_template in TEMPLATES]  # noqa: F405
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
PROCESS = "backoffice"
