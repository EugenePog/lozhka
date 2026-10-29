"""Availability and reservations (docs 02 s.8). Reads the Gold views; writes reservations in `app`."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.db import connection, transaction

from lozhka_api.sales.models import Order, StockReservation

from .timeutil import now

ZERO = Decimal("0")


def available(product_ids: Iterable[int]) -> dict[int, Decimal]:
    ids = list(set(product_ids))
    if not ids:
        return {}
    with connection.cursor() as cur:
        cur.execute("select product_id, available_qty from gold.stock_available where product_id = any(%s)", [ids])
        found = {pid: qty for pid, qty in cur.fetchall()}
    return {pid: found.get(pid, ZERO) for pid in ids}


def lock_products(product_ids: Iterable[int]) -> None:
    """Serialise concurrent checkouts per product. Sorted order avoids deadlocks. Held until commit."""
    with connection.cursor() as cur:
        for pid in sorted(set(product_ids)):
            cur.execute("select pg_advisory_xact_lock(hashtext(%s))", [f"stock:{pid}"])


def reserve(order: Order, lines: list[tuple[int, Decimal]], expires_at: datetime | None) -> None:
    StockReservation.objects.bulk_create(
        [StockReservation(order=order, product_id=pid, qty=qty, status="held", expires_at=expires_at) for pid, qty in lines]
    )


def commit(order: Order) -> int:
    """Payment received or operator confirmed: the hold becomes permanent."""
    return order.reservations.filter(status="held").update(status="committed", expires_at=None)


def release(order: Order, status: str = "released") -> int:
    return order.reservations.filter(status__in=["held", "committed"]).update(status=status)


@transaction.atomic
def expire_holds(at: datetime | None = None) -> list[int]:
    """Sweep: held reservations past their deadline expire; their orders are cancelled
    (payment timeout / pay-on-delivery not confirmed in time). Returns affected order ids."""
    from .orders import cancel_order

    at = at or now()
    ids = list(
        StockReservation.objects.filter(status="held", expires_at__lte=at).values_list("order_id", flat=True).distinct()
    )
    for order in Order.objects.select_for_update().filter(id__in=ids, status__in=["awaiting_payment", "pending_confirmation"]):
        reason = "payment_timeout" if order.status == "awaiting_payment" else "not_confirmed"
        cancel_order(order, reason=reason, actor="system")
    StockReservation.objects.filter(status="held", expires_at__lte=at).update(status="expired")
    return ids
