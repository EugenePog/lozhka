"""Prices, promo codes and VAT (all integer cents, prices include VAT)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from django.db import connection
from django.db.models import F, Q

from lozhka_api.catalog.models import Product, PromoCode

from .timeutil import now


def current_prices(product_ids: Iterable[int]) -> dict[int, tuple[int, bool, int | None]]:
    """product_id -> (price_cents, is_discounted, regular_cents)."""
    ids = list(set(product_ids))
    if not ids:
        return {}
    with connection.cursor() as cur:
        cur.execute(
            "select product_id, amount_cents, is_discounted, regular_cents from gold.current_price where product_id = any(%s)",
            [ids],
        )
        return {pid: (amt, bool(disc), reg) for pid, amt, disc, reg in cur.fetchall() if amt is not None}


def line_total(unit_cents: int, qty: Decimal) -> int:
    return int((Decimal(unit_cents) * qty).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def vat_included(gross_cents: int, rate_pct: Decimal) -> int:
    return int((Decimal(gross_cents) * rate_pct / (Decimal(100) + rate_pct)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class PromoResult:
    code: str = ""
    discount_cents: int = 0
    error: str = ""


def evaluate_promo(code: str, subtotal_cents: int, customer_id: int | None = None) -> PromoResult:
    if not code:
        return PromoResult()
    code = code.strip()
    promo = PromoCode.objects.filter(code__iexact=code, is_active=True).first()
    at = now()
    if promo is None:
        return PromoResult(code=code, error="unknown_code")
    if (promo.valid_from and promo.valid_from > at) or (promo.valid_to and promo.valid_to < at):
        return PromoResult(code=code, error="expired")
    if subtotal_cents < promo.min_order_cents:
        return PromoResult(code=code, error="min_order")
    from lozhka_api.sales.models import Order

    used = Order.objects.filter(promo_code__iexact=promo.code).exclude(status__in=["cancelled", "payment_failed"])
    if promo.max_uses is not None and used.count() >= promo.max_uses:
        return PromoResult(code=code, error="used_up")
    if promo.max_uses_per_customer is not None and customer_id and used.filter(customer_id=customer_id).count() >= promo.max_uses_per_customer:
        return PromoResult(code=code, error="used_up")
    amount = subtotal_cents * promo.value // 100 if promo.kind == "percent" else promo.value
    return PromoResult(code=promo.code, discount_cents=min(amount, subtotal_cents))


@dataclass
class Totals:
    subtotal_cents: int = 0
    discount_cents: int = 0
    delivery_fee_cents: int = 0
    vat_9_cents: int = 0
    vat_21_cents: int = 0
    lines: list[dict] = field(default_factory=list)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents - self.discount_cents + self.delivery_fee_cents


def compute_totals(items: list[tuple[Product, Decimal, int]], discount_cents: int, fee_cents: int) -> Totals:
    """items: (product, qty, unit_price_cents). VAT is carved out of the gross prices; the discount is spread pro rata."""
    t = Totals(discount_cents=discount_cents, delivery_fee_cents=fee_cents)
    for product, qty, unit in items:
        total = line_total(unit, qty)
        t.subtotal_cents += total
        t.lines.append({"product": product, "qty": qty, "unit": unit, "total": total, "rate": product.vat_rate.rate_pct})
    factor = Decimal(t.subtotal_cents - discount_cents) / Decimal(t.subtotal_cents) if t.subtotal_cents else Decimal(1)
    for ln in t.lines:
        vat = vat_included(int(Decimal(ln["total"]) * factor), ln["rate"])
        if ln["rate"] == Decimal("9.0") or ln["rate"] == 9:
            t.vat_9_cents += vat
        else:
            t.vat_21_cents += vat
    t.vat_21_cents += vat_included(fee_cents, Decimal(21))
    return t
