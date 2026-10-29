"""Incoming goods and stock adjustments (storekeeper, SC06)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import connection, transaction

from lozhka_api.procurement.models import DeliveryLineFix, Receiving, ReceivingLine, StockAdjustment

from .timeutil import now


class ReceivingError(Exception):
    pass


def line_issue(line: ReceivingLine) -> str:
    """Issue tag shown on the line (SC06)."""
    if line.best_before is None:
        return "best_before_missing"
    if line.unit_differs:
        return "unit_differs"
    fixed = DeliveryLineFix.objects.filter(supplier=line.receiving.supplier, delivery_ref=line.receiving.delivery_ref,
                                           line_key=line.supplier_sku or line.product.sku, status="active").exists()
    return "fixed_manually" if fixed else "ok"


def open_issue_count(receiving: Receiving) -> int:
    return sum(1 for ln in receiving.lines.select_related("product", "receiving__supplier") if line_issue(ln) in ("best_before_missing", "unit_differs"))


@transaction.atomic
def update_line(line: ReceivingLine, user, qty_received: Decimal | None, best_before: date | None, lot_code: str | None,
                qty_rejected: Decimal | None = None) -> ReceivingLine:
    rec = line.receiving
    if rec.status != "open":
        raise ReceivingError("This delivery is already received.")
    key = line.supplier_sku or line.product.sku

    def fix(field: str, new, document_value) -> None:
        DeliveryLineFix.objects.update_or_create(
            supplier=rec.supplier, delivery_ref=rec.delivery_ref, line_key=key, field=field,
            defaults={"value": str(new), "document_value": "" if document_value is None else str(document_value),
                      "status": "active", "created_by": user})

    if qty_received is not None and qty_received != line.qty_received:
        if qty_received < 0:
            raise ReceivingError("Quantity cannot be negative.")
        fix("qty_received", qty_received, line.qty_expected)
        line.qty_received = qty_received
    if qty_rejected is not None:
        line.qty_rejected = qty_rejected
    if best_before is not None and best_before != line.best_before:
        fix("best_before", best_before, line.best_before)
        line.best_before, line.best_before_source = best_before, "entered"
    if lot_code is not None and lot_code != line.supplier_lot_code:
        line.supplier_lot_code = lot_code
    line.save()
    return line


@transaction.atomic
def receive(receiving: Receiving, user) -> Receiving:
    receiving = Receiving.objects.select_for_update().get(pk=receiving.pk)
    if receiving.status != "open":
        raise ReceivingError("This delivery is already received.")
    lines = list(receiving.lines.select_related("product"))
    if not lines:
        raise ReceivingError("The delivery has no lines.")
    missing = [ln.product.sku for ln in lines if ln.qty_received > 0 and ln.best_before is None]
    if missing:
        raise ReceivingError("Best-before date is required for: " + ", ".join(missing))
    receiving.status = "accepted"
    receiving.received_at = now()
    receiving.received_by = user
    receiving.save(update_fields=["status", "received_at", "received_by"])
    return receiving


def lot_balance(line_id: int) -> Decimal:
    with connection.cursor() as cur:
        cur.execute("select balance from gold.lot_balance where lot_id = %s", [line_id])
        row = cur.fetchone()
    return row[0] if row else Decimal(0)


@transaction.atomic
def adjust(line: ReceivingLine, delta: Decimal, reason: str, note: str, user) -> StockAdjustment:
    if delta == 0:
        raise ReceivingError("The change cannot be zero.")
    if reason not in dict(StockAdjustment.REASONS) or reason == "return_to_stock":
        raise ReceivingError("Choose a reason.")
    if lot_balance(line.id) + delta < 0:
        raise ReceivingError("The lot would go below zero.")
    return StockAdjustment.objects.create(receiving_line=line, qty_delta=delta, reason=reason, note=note, created_by=user)
