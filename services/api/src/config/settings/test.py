"""Test settings: both middleware stacks are available; tests pick URLconf and stack per client."""
from .backoffice import *  # noqa: F403
from .base import PUBLIC_MIDDLEWARE, env

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher", "django.contrib.auth.hashers.Argon2PasswordHasher"]
AXES_ENABLED = False
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "test"
# tests use the seeded local database and roll back (see tests/conftest.py); set LOZHKA_TEST_DB_NAME to use another
if env("LOZHKA_TEST_DB_NAME", ""):
    DATABASES["default"]["NAME"] = env("LOZHKA_TEST_DB_NAME")  # noqa: F405
STAFF_TEST_MIDDLEWARE = BACKOFFICE_MIDDLEWARE  # noqa: F405
PUBLIC_TEST_MIDDLEWARE = PUBLIC_MIDDLEWARE
