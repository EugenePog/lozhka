"""Order status transitions. Every change writes order_status_history (docs 02 s.4.4)."""
from __future__ import annotations

from django.db import connection, transaction

from lozhka_api.customers.models import Customer
from lozhka_api.sales.models import CustomerFlag, Order, OrderConfirmationAttempt, OrderStatusHistory, Payment

from . import deliveries, stock
from .timeutil import now


class TransitionError(Exception):
    pass


def next_order_number() -> str:
    with connection.cursor() as cur:
        cur.execute("select nextval('order_number_seq')")
        return f"LZ-{cur.fetchone()[0]}"


def set_status(order: Order, status: str, actor: str = "system", **fields) -> None:
    order.status = status
    order.save(update_fields=["status", *fields.keys()] if fields else ["status"])
    OrderStatusHistory.objects.create(order=order, status=status, actor=actor)


def _require(order: Order, allowed: list[str]) -> None:
    if order.status not in allowed:
        raise TransitionError(f"order {order.order_number} is {order.status}, expected one of {allowed}")


@transaction.atomic
def mark_paid(order: Order, provider_payment_id: str = "", actor: str = "payment") -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == "paid":
        return order
    _require(order, ["awaiting_payment"])
    Payment.objects.filter(order=order, status="pending").update(status="paid", paid_at=now(), provider_payment_id=provider_payment_id)
    stock.commit(order)
    set_status(order, "paid", actor)
    return order


@transaction.atomic
def mark_payment_failed(order: Order, reason: str = "", actor: str = "payment") -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require(order, ["awaiting_payment"])
    Payment.objects.filter(order=order, status="pending").update(status="failed", failure_reason=reason)
    stock.release(order)
    set_status(order, "payment_failed", actor)
    deliveries.release_if_empty(order.delivery)
    return order


@transaction.atomic
def cancel_order(order: Order, reason: str = "customer", actor: str = "system") -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require(order, ["awaiting_payment", "pending_confirmation", "paid", "confirmed"])
    if order.delivery and order.delivery.status != "open":
        raise TransitionError("delivery already approved; contact the shop")
    Payment.objects.filter(order=order, status="pending").update(status="failed", failure_reason=reason)
    stock.release(order)
    order.cancel_reason = reason
    order.cancelled_at = now()
    set_status(order, "cancelled", actor, cancel_reason=order.cancel_reason, cancelled_at=order.cancelled_at)
    delivery = order.delivery
    order.delivery = None if delivery and not delivery.orders.exclude(pk=order.pk).exists() else order.delivery
    if order.delivery is None and delivery is not None:
        order.save(update_fields=["delivery"])
        deliveries.release_if_empty(delivery)
    return order


@transaction.atomic
def confirm_cod(order: Order, operator, note: str = "") -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require(order, ["pending_confirmation"])
    OrderConfirmationAttempt.objects.create(order=order, operator=operator, outcome="confirmed", note=note)
    stock.commit(order)
    order.confirmed_at = now()
    order.confirmed_by = operator
    order.claimed_by = None
    order.claimed_until = None
    set_status(order, "confirmed", operator.get_username(), confirmed_at=order.confirmed_at, confirmed_by=operator,
               claimed_by=None, claimed_until=None)
    return order


@transaction.atomic
def log_attempt(order: Order, operator, outcome: str, note: str = "", next_call_at=None, flag: bool = False) -> Order:
    """no_answer / details_changed keep the order waiting; customer_cancelled / rejected cancel it."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    _require(order, ["pending_confirmation"])
    OrderConfirmationAttempt.objects.create(order=order, operator=operator, outcome=outcome, note=note, next_call_at=next_call_at)
    if outcome in ("customer_cancelled", "rejected"):
        if flag or outcome == "rejected":
            CustomerFlag.objects.create(customer=order.customer, kind="refused_at_confirmation", order=order, created_by=operator)
        return cancel_order(order, reason=outcome, actor=operator.get_username())
    return order


@transaction.atomic
def claim(order: Order, operator, minutes: int) -> bool:
    """Soft lock so two operators do not call the same customer."""
    from datetime import timedelta

    order = Order.objects.select_for_update().get(pk=order.pk)
    at = now()
    if order.claimed_by_id and order.claimed_by_id != operator.id and order.claimed_until and order.claimed_until > at:
        return False
    order.claimed_by = operator
    order.claimed_until = at + timedelta(minutes=minutes)
    order.save(update_fields=["claimed_by", "claimed_until"])
    return True


def customer_orders(customer: Customer):
    return Order.objects.filter(customer=customer).select_related("delivery").prefetch_related("lines")
