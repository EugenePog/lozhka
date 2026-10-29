"""Delivery operations done by the operator: route stub, approve (lot allocation), dispatch, move, close (docs 03 s.7)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from lozhka_api.customers.models import Customer
from lozhka_api.procurement.models import ReceivingLine, StockAdjustment
from lozhka_api.sales.models import (
    READY_STATUSES, CustomerFlag, Delivery, DeliveryReturn, DeliveryStop, Order, OrderLine, PickLine, Payment, ReturnReason,
)

from . import deliveries, orders as order_svc, stock
from .settings_store import get_setting
from .timeutil import now


class FulfilmentError(Exception):
    pass


def ready_orders(delivery: Delivery):
    return delivery.orders.filter(status__in=READY_STATUSES)


def pending_orders(delivery: Delivery):
    return delivery.orders.filter(status__in=["awaiting_payment", "pending_confirmation"])


# ---- route planning (stub: the real planner is module M3) ----------------------------------------------------------

@transaction.atomic
def plan_route(delivery: Delivery) -> int:
    """STUB. Orders the stops by postcode and spreads ETAs from the start of the delivery range; the route planner
    service replaces this later. Returns the number of stops."""
    orders_ = list(ready_orders(delivery).order_by("ship_postcode", "ship_house_number"))
    delivery.stops.all().delete()
    service = int(get_setting("service_time_s")) + 420
    for i, o in enumerate(orders_, start=1):
        eta = delivery.deliver_starts_at + timedelta(seconds=service * (i - 1))
        DeliveryStop.objects.create(delivery=delivery, order=o, sequence=i, planned_arrival=eta,
                                    window_start=delivery.deliver_starts_at, window_end=delivery.deliver_ends_at)
    delivery.algorithm_version = "stub-postcode-sort"
    delivery.planned_start = delivery.deliver_starts_at
    delivery.planned_end = delivery.deliver_starts_at + timedelta(seconds=service * len(orders_))
    delivery.save(update_fields=["algorithm_version", "planned_start", "planned_end"])
    return len(orders_)


def ensure_stops(delivery: Delivery) -> None:
    """Every ready order needs a stop. Keep a route the operator already planned; add stops for orders that joined
    after planning and drop stops of orders that left."""
    ready_ids = set(ready_orders(delivery).values_list("id", flat=True))
    delivery.stops.exclude(order_id__in=ready_ids).delete()
    have = set(delivery.stops.values_list("order_id", flat=True))
    if not have or have != ready_ids:
        if not have:
            plan_route(delivery)
        else:
            last = delivery.stops.order_by("-sequence").values_list("sequence", flat=True).first() or 0
            for i, o in enumerate(ready_orders(delivery).exclude(id__in=have).order_by("ship_postcode"), start=last + 1):
                DeliveryStop.objects.create(delivery=delivery, order=o, sequence=i, window_start=delivery.deliver_starts_at,
                                            window_end=delivery.deliver_ends_at)


# ---- approve: allocate lots, oldest best-before first ----------------------------------------------------------------

def _free_lots(product_id: int) -> list[list]:
    """[receiving_line_id, free_qty, best_before] ordered by best-before. Free = balance minus quantities that are
    already allocated to approved deliveries that have not left yet."""
    from .stock import ZERO  # noqa: F401
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            """select lb.lot_id, lb.balance - coalesce(a.qty, 0) as free, lb.best_before
                 from gold.lot_balance lb
                 left join (select pk.receiving_line_id, sum(pk.qty) qty
                              from app.pick_line pk
                              join app.order_line ol on ol.id = pk.order_line_id
                              join app."order" o on o.id = ol.order_id
                              join app.delivery d on d.id = o.delivery_id
                             where d.status = 'approved' group by 1) a on a.receiving_line_id = lb.lot_id
                where lb.product_id = %s and lb.balance - coalesce(a.qty, 0) > 0
                order by lb.best_before nulls last, lb.lot_id""", [product_id])
        return [[r[0], r[1], r[2]] for r in cur.fetchall()]


@transaction.atomic
def approve_delivery(delivery: Delivery, user) -> dict:
    delivery = Delivery.objects.select_for_update().get(pk=delivery.pk)
    if delivery.status not in ("open", "closed"):
        raise FulfilmentError("Delivery is already approved or further.")
    if pending_orders(delivery).exists():
        raise FulfilmentError("Some orders are still awaiting payment or confirmation. Resolve them first.")
    orders_ = list(ready_orders(delivery).prefetch_related("lines"))
    if not orders_:
        raise FulfilmentError("No orders are ready in this delivery.")
    if delivery.vehicle_id is None or delivery.driver_id is None:
        raise FulfilmentError("Choose a vehicle and a driver first.")
    PickLine.objects.filter(order_line__order__delivery=delivery).delete()
    lots_cache: dict[int, list[list]] = {}
    shortages = []
    picks = []
    for o in orders_:
        for ln in o.lines.all():
            lots = lots_cache.setdefault(ln.product_id, _free_lots(ln.product_id))
            need = ln.qty
            for lot in lots:
                if need <= 0:
                    break
                take = min(need, lot[1])
                if take > 0:
                    picks.append(PickLine(order_line=ln, receiving_line_id=lot[0], qty=take))
                    lot[1] -= take
                    need -= take
            if need > 0:
                shortages.append(f"{ln.name_snapshot}: {need} short")
    if shortages:
        raise FulfilmentError("Not enough stock in lots: " + "; ".join(shortages))
    PickLine.objects.bulk_create(picks)
    ensure_stops(delivery)  # while the orders are still "ready"; afterwards they are picking
    delivery.status = "approved"
    delivery.approved_by = user
    delivery.approved_at = now()
    delivery.save(update_fields=["status", "approved_by", "approved_at"])
    for o in orders_:
        order_svc.set_status(o, "picking", user.get_username())
    return {"orders": len(orders_), "picks": len(picks)}


@transaction.atomic
def mark_packed(delivery: Delivery, user) -> None:
    for o in delivery.orders.filter(status="picking"):
        order_svc.set_status(o, "packed", user.get_username())


@transaction.atomic
def dispatch(delivery: Delivery, user) -> None:
    delivery = Delivery.objects.select_for_update().get(pk=delivery.pk)
    if delivery.status != "approved":
        raise FulfilmentError("Approve the delivery (and print the packing list) first.")
    delivery.status = "out_for_delivery"
    delivery.dispatched_at = now()
    delivery.save(update_fields=["status", "dispatched_at"])
    for o in delivery.orders.filter(status__in=["picking", "packed"]):
        order_svc.set_status(o, "out_for_delivery", user.get_username())
        o.reservations.filter(status__in=["held", "committed"]).update(status="consumed")


# ---- move / remove ------------------------------------------------------------------------------------------------------

@transaction.atomic
def move_order(order: Order, target: Delivery, user) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    target = Delivery.objects.select_for_update().get(pk=target.pk)
    old = order.delivery
    if old is None or old.status != "open":
        raise FulfilmentError("The order's delivery is already approved; it cannot be moved.")
    if target.pk == old.pk:
        return order
    if not deliveries.can_accept_orders(target):
        raise FulfilmentError("The target delivery is not open.")
    if deliveries.order_count(target) >= target.capacity_orders:
        raise FulfilmentError("The target delivery is full.")
    DeliveryStop.objects.filter(order=order).delete()
    order.delivery = target
    order.save(update_fields=["delivery"])
    deliveries.release_if_empty(old)
    return order


@transaction.atomic
def remove_order(order: Order, user, reason: str = "removed_by_operator") -> Order:
    return order_svc.cancel_order(order, reason=reason, actor=user.get_username())


# ---- close delivery (SC05) ----------------------------------------------------------------------------------------------

@dataclass
class ReturnEntry:
    order_line_id: int
    quantity: Decimal
    reason_code: str
    note: str = ""


@dataclass
class StopEntry:
    order_id: int
    outcome: str  # delivered | returns | not_delivered
    payment_collected: bool = False
    flag_customer: bool = False
    failure_reason: str = ""
    returns: list[ReturnEntry] = field(default_factory=list)


@transaction.atomic
def close_delivery(delivery: Delivery, user, entries: list[StopEntry], final: bool) -> None:
    delivery = Delivery.objects.select_for_update().get(pk=delivery.pk)
    if delivery.status not in ("out_for_delivery",):
        raise FulfilmentError("Only a delivery that is out for delivery can be closed.")
    reasons = {r.code: r for r in ReturnReason.objects.all()}
    stops = {s.order_id: s for s in delivery.stops.select_related("order")}
    if delivery.orders.filter(status="out_for_delivery").exclude(id__in=stops).exists():
        raise FulfilmentError("Some orders on this delivery have no stop. Contact support before closing.")
    for e in entries:
        stop = stops.get(e.order_id)
        if stop is None:
            raise FulfilmentError("Unknown order in the entries.")
        stop.flag_customer = e.flag_customer
        stop.payment_collected = e.payment_collected
        stop.failure_reason = e.failure_reason
        stop.status = {"delivered": "delivered", "returns": "delivered", "not_delivered": "failed"}[e.outcome]
        stop.save()
        stop.returns.all().delete()
        lines = {ln.id: ln for ln in stop.order.lines.all()}
        for r in e.returns:
            ln = lines.get(r.order_line_id)
            if ln is None or r.quantity <= 0 or r.quantity > ln.qty:
                raise FulfilmentError("Return quantity must be between 0 and the ordered quantity.")
            if r.reason_code not in reasons:
                raise FulfilmentError("Choose a return reason for every returned item.")
            DeliveryReturn.objects.create(delivery_stop=stop, order_line=ln, quantity=r.quantity, reason=reasons[r.reason_code],
                                          note=r.note, recorded_by=user, is_final=final)
        if e.outcome == "not_delivered" and not e.returns and not e.failure_reason:
            raise FulfilmentError("Give a reason for an order that was not delivered.")
    if not final:
        return
    missing = [oid for oid in stops if oid not in {e.order_id for e in entries}]
    if missing:
        raise FulfilmentError("Every order needs an outcome before the delivery can be closed.")
    for e in entries:
        stop, order = stops[e.order_id], stops[e.order_id].order
        if e.outcome == "not_delivered":
            _restock_whole_order(order, reasons.get(e.failure_reason), user)
            order_svc.set_status(order, "delivery_failed", user.get_username())
        else:
            for r in e.returns:
                _restock_line(OrderLine.objects.get(pk=r.order_line_id), r.quantity, reasons[r.reason_code], user)
            order_svc.set_status(order, "delivered", user.get_username())
            stop.delivered_at = now()
            stop.save(update_fields=["delivered_at"])
            if order.payment_method == "card_on_delivery" and e.payment_collected:
                Payment.objects.filter(order=order, status="pending").update(
                    status="paid", paid_at=now(), collected_by=user, collected_at=now(), delivery_stop=stop)
        if e.flag_customer:
            CustomerFlag.objects.create(customer=order.customer, kind="refused_at_delivery", order=order, created_by=user)
    delivery.status = "completed"
    delivery.completed_by = user
    delivery.completed_at = now()
    delivery.save(update_fields=["status", "completed_by", "completed_at"])


def _restock_line(line: OrderLine, qty: Decimal, reason: ReturnReason, user) -> None:
    """Goods go back to the lot they were picked from, unless the reason is a write-off reason."""
    if not reason.restock:
        return
    remaining = qty
    for pick in line.picks.select_related("receiving_line").order_by("-receiving_line__best_before"):
        take = min(remaining, pick.qty)
        if take > 0:
            StockAdjustment.objects.create(receiving_line=pick.receiving_line, qty_delta=take, reason="return_to_stock",
                                           note=f"{line.order.order_number}: {reason.code}", created_by=user)
            remaining -= take
        if remaining <= 0:
            break


def _restock_whole_order(order: Order, reason: ReturnReason | None, user) -> None:
    if reason is None or not reason.restock:
        return
    for line in order.lines.all():
        _restock_line(line, line.qty, reason, user)
