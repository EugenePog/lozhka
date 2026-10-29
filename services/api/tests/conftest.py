"""Tests run against the SEEDED local database and roll back after every test (nothing is committed).
Prepare once:  make db-up db-migrate api-migrate db-gold-views seed-demo
The test settings module refuses to run against anything that is not a local database."""
import os

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")


@pytest.fixture(scope="session")
def django_db_setup():
    from django.conf import settings

    host = settings.DATABASES["default"].get("HOST", "")
    if host not in ("", "localhost", "127.0.0.1", "db"):
        raise RuntimeError(f"refusing to run tests against database host {host!r}")


@pytest.fixture(autouse=True)
def _allowed_hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.AXES_ENABLED = False


class ScopedClient:
    """A browser for one of the two processes: its own URLconf and middleware stack, like a separate host in production."""

    def __new__(cls, urlconf: str, middleware: list[str], **kwargs):
        from django.test import Client
        from django.test.utils import override_settings

        class _Client(Client):
            def request(self, **request):
                with override_settings(ROOT_URLCONF=urlconf, MIDDLEWARE=middleware):
                    return super().request(**request)

        return _Client(**kwargs)


@pytest.fixture
def public_client(settings, db):
    """A browser talking to the public API: CSRF enforced like in production."""
    client = ScopedClient("config.urls_public", settings.PUBLIC_TEST_MIDDLEWARE, enforce_csrf_checks=True)
    client.token = client.get("/api/v1/auth/csrf").json()["csrf"]
    return client


def post_json(client, url, body=None, method="post"):
    import json

    return getattr(client, method)(url, json.dumps(body or {}), content_type="application/json", HTTP_X_CSRFTOKEN=client.token)


@pytest.fixture
def staff(settings, db):
    def make(email: str):
        c = ScopedClient("config.urls_backoffice", settings.STAFF_TEST_MIDDLEWARE)
        assert c.post("/login/", {"username": email, "password": "staff1234"}).status_code == 302
        return c

    return make
