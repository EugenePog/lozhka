"""Every staff page needs a login and exactly one capability; roles do not overlap."""
import pytest
from django.urls import get_resolver

from lozhka_backoffice import permissions, urls as staff_urls

OPEN = {"health", "login", "logout", "home"}


def named_views():
    for p in staff_urls.urlpatterns:
        name = getattr(p, "name", None)
        if name and name not in OPEN:
            yield name, p


def test_every_staff_view_declares_a_capability():
    missing = [n for n, p in named_views() if not hasattr(p.callback, "required_capability")]
    assert not missing, f"views without a capability: {missing}"


def test_roles_do_not_overlap_except_shared_catalogue_read():
    owners: dict[str, list[str]] = {}
    for role, caps in permissions.ROLES.items():
        for c in caps:
            owners.setdefault(c, []).append(role)
    shared = {c: r for c, r in owners.items() if len(r) > 1}
    assert set(shared) <= {"view_catalogue"}


def test_every_menu_entry_needs_a_capability_of_its_role():
    for label, url, cap, role in permissions.MENU:
        assert cap in permissions.ROLES[role], (label, cap, role)


@pytest.mark.parametrize("email,allowed,denied", [
    ("operator@lozhka.example", ["/deliveries/", "/ready/", "/confirm/"], ["/incoming/", "/stock/", "/templates/", "/rules/", "/suppliers/", "/admin/"]),
    ("store@lozhka.example", ["/incoming/", "/stock/"], ["/deliveries/", "/ready/", "/confirm/", "/templates/", "/admin/"]),
    ("admin@lozhka.example", ["/templates/", "/rules/", "/return-reasons/", "/suppliers/", "/admin/"], ["/deliveries/", "/ready/", "/confirm/", "/incoming/", "/stock/"]),
    ("all@lozhka.example", ["/deliveries/", "/incoming/", "/templates/"], []),
])
def test_role_matrix(staff, email, allowed, denied):
    c = staff(email)
    for url in allowed:
        assert c.get(url).status_code == 200, (email, url)
    for url in denied:
        assert c.get(url).status_code == 403, (email, url)


def test_anonymous_is_sent_to_login(db, client):
    for url in ["/deliveries/", "/incoming/", "/templates/", "/admin/", "/"]:
        r = client.get(url)
        assert r.status_code == 302 and r["Location"].startswith("/login/"), url


def test_admin_cannot_see_customer_or_order_data(staff):
    c = staff("admin@lozhka.example")
    for url in ["/admin/sales/order/", "/admin/customers/customer/"]:
        assert c.get(url).status_code == 404


def test_customer_account_cannot_log_into_staff_console(db, client):
    r = client.post("/login/", {"username": "demo@lozhka.example", "password": "demo1234"})
    assert r.status_code == 200 and b"not right" in r.content
    assert client.get("/deliveries/").status_code == 302
