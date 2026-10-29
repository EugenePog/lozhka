"""Roles are bundles of capability permissions (docs 02 s.4.7, GUI s.7). A page needs ONE capability; roles do not
overlap, a person with several roles sees the menus of all of them."""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

APP = "core"  # the unmanaged StaffCapability model lives in lozhka_api.core

ROLES: dict[str, list[str]] = {
    "admin": ["edit_delivery_templates", "edit_delivery_rules", "edit_return_reasons", "edit_suppliers",
              "set_supplier_credentials", "edit_catalogue", "edit_content", "manage_staff", "view_audit_log", "view_catalogue"],
    "operator": ["view_customer_data", "confirm_cod_orders", "manage_ready_orders", "manage_deliveries", "close_deliveries", "view_catalogue"],
    "storekeeper": ["receive_goods", "fix_delivery_lines", "adjust_stock", "view_catalogue"],
}

# menu: (label, url name, capability, role). Order = display order.
MENU = [
    ("Deliveries", "deliveries", "manage_deliveries", "operator"),
    ("Orders ready", "ready", "manage_ready_orders", "operator"),
    ("Orders to confirm", "confirm", "confirm_cod_orders", "operator"),
    ("Incoming deliveries", "incoming", "receive_goods", "storekeeper"),
    ("Stock adjustments", "stock", "adjust_stock", "storekeeper"),
    ("Delivery templates", "templates", "edit_delivery_templates", "admin"),
    ("Delivery rules", "rules", "edit_delivery_rules", "admin"),
    ("Return reasons", "return_reasons", "edit_return_reasons", "admin"),
    ("Suppliers", "suppliers", "edit_suppliers", "admin"),
    ("Catalogue and content", "admin:index", "edit_catalogue", "admin"),
    ("People and roles", "admin:auth_user_changelist", "manage_staff", "admin"),
]
LANDING = [("manage_deliveries", "deliveries"), ("receive_goods", "incoming"), ("edit_delivery_templates", "templates")]


def can(user, capability: str) -> bool:
    return user.is_active and user.has_perm(f"{APP}.{capability}")


def staff_view(capability: str):
    """Marks a view with the capability it needs (the URL-permission test reads `required_capability`) and enforces it.
    Not logged in -> login page; logged in without the capability -> 'not allowed'."""

    def deco(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not can(request.user, capability):
                return render(request, "backoffice/not_allowed.html", status=403)
            return view(request, *args, **kwargs)

        wrapper.required_capability = capability
        return wrapper

    return deco


def menu_for(user) -> list[dict]:
    return [{"label": label, "url": url, "role": role} for label, url, cap, role in MENU if can(user, cap)]


def landing_for(user) -> str | None:
    for cap, url in LANDING:
        if can(user, cap):
            return url
    return None


def forbidden(request):
    return HttpResponseForbidden("not allowed")
