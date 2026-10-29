"""Shared helpers for the public API: CSRF-aware guest-friendly auth, language, customer and cart lookup."""
from __future__ import annotations

import json
import secrets
from decimal import Decimal
from typing import Any

from django.db import connection
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.utils import check_csrf

from lozhka_api.customers.models import Cart, Customer

LANGS = ("nl", "en", "ru")


class PublicAuth:
    """Every public endpoint goes through this. Guests are allowed (they get a cart through the session), but unsafe
    methods must carry the CSRF token, because the browser sends the session cookie automatically."""

    def __call__(self, request: HttpRequest) -> Any:
        if request.method not in ("GET", "HEAD", "OPTIONS") and not getattr(request, "_ninja_csrf_exempt", False):
            error = check_csrf(request)
            if error is not None:
                raise HttpError(403, "csrf_failed")
        return True


class LoggedIn(PublicAuth):
    """Same, and the visitor must be a signed-in customer."""

    def __call__(self, request: HttpRequest) -> Any:
        super().__call__(request)
        if customer_of(request) is None:
            return None  # Ninja answers 401
        return True


public_auth = PublicAuth()
customer_auth = LoggedIn()


def lang_of(lang: str | None) -> str:
    return lang if lang in LANGS else "nl"


def customer_of(request: HttpRequest) -> Customer | None:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    return Customer.objects.filter(auth_user=user).first()


def get_cart(request: HttpRequest, create: bool = False) -> Cart | None:
    customer = customer_of(request)
    if customer is not None:
        cart, _ = Cart.objects.get_or_create(customer=customer) if create else (Cart.objects.filter(customer=customer).first(), False)
        return cart
    token = request.session.get("cart")
    if token:
        cart = Cart.objects.filter(session_token=token).first()
        if cart:
            return cart
    if not create:
        return None
    token = secrets.token_urlsafe(24)
    request.session["cart"] = token
    return Cart.objects.create(session_token=token)


def merge_guest_cart(request: HttpRequest, customer: Customer) -> None:
    """On login: the guest cart (from this browser session) is added into the customer's cart."""
    token = request.session.get("cart")
    if not token:
        return
    guest = Cart.objects.filter(session_token=token).first()
    if guest is None:
        return
    mine, _ = Cart.objects.get_or_create(customer=customer)
    for line in guest.lines.all():
        existing = mine.lines.filter(product_id=line.product_id).first()
        if existing:
            existing.qty += line.qty
            existing.save(update_fields=["qty"])
        else:
            mine.lines.create(product_id=line.product_id, qty=line.qty)
    if not mine.promo_code and guest.promo_code:
        mine.promo_code = guest.promo_code
        mine.save(update_fields=["promo_code"])
    guest.delete()
    request.session.pop("cart", None)


def fetch_all(sql: str, params: list | tuple = ()) -> list[dict]:
    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        json_cols = {i for i, c in enumerate(cur.description) if c.type_code in (114, 3802)}  # json, jsonb
        # Django hands jsonb back as text; decode it here
        return [
            dict(zip(cols, (json.loads(v) if i in json_cols and isinstance(v, str) else v for i, v in enumerate(row))))
            for row in cur.fetchall()
        ]


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value
