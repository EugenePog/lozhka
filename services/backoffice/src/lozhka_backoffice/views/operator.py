"""Operator: Deliveries (SC02), Orders ready (SC03), Orders to confirm (SC04), Close delivery (SC05)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST

from lozhka_api.domain import deliveries as dsvc
from lozhka_api.domain import fulfilment as fsvc
from lozhka_api.domain import orders as osvc
from lozhka_api.domain.settings_store import get_setting
from lozhka_api.domain.timeutil import local_today, now
from lozhka_api.sales.models import (
    CAPACITY_EXCLUDED, READY_STATUSES, Delivery, Driver, Order, OrderLine, ReturnReason, Vehicle,
)

from ..permissions import staff_view

STATUS_LABEL = {"open": "Open", "closed": "Closed", "approved": "Approved", "out_for_delivery": "Out for delivery", "completed": "Completed"}


# ---- counters (live, polled) --------------------------------------------------------------------------------------------

def counters() -> dict:
    today = local_today()
    return {
        "deliveries": Delivery.objects.filter(delivery_date__gte=today, status__in=["open", "closed", "approved", "out_for_delivery"]).count(),
        "ready": Order.objects.filter(status__in=READY_STATUSES, delivery__status="open").count(),
        "confirm": Order.objects.filter(status="pending_confirmation").count(),
    }


def tabs_ctx(active: str) -> dict:
    c = counters()
    warn_at = now() + timedelta(minutes=int(get_setting("cod_warn_minutes")))
    return {"tab": active, "counts": c,
            "confirm_alert": Order.objects.filter(status="pending_confirmation", confirm_deadline_at__lte=warn_at).exists() or c["confirm"] > 0}


@staff_view("manage_deliveries")
def tab_counters(request):
    """Small fragment polled every 20 s by the tab bar."""
    return render(request, "backoffice/operator/_tabs.html", tabs_ctx(request.GET.get("tab", "deliveries")))


def effective(d: Delivery) -> str:
    return dsvc.effective_status(d)


def delivery_rows(date_from, date_to, status):
    qs = Delivery.objects.filter(delivery_date__gte=date_from, delivery_date__lte=date_to).select_related("vehicle", "driver")
    rows = []
    counts = dsvc.count_orders(list(qs.values_list("id", flat=True)))
    for d in qs.order_by("delivery_date", "deliver_starts_at"):
        st = effective(d)
        if status and st != status:
            continue
        orders_ = d.orders.exclude(status__in=CAPACITY_EXCLUDED)
        items = sum(int(ln.qty) for o in orders_.prefetch_related("lines") for ln in o.lines.all())
        terminal = sum(o.total_cents for o in orders_ if o.payment_method == "card_on_delivery" and o.status in READY_STATUSES + ["picking", "packed", "out_for_delivery"])
        rows.append({"d": d, "status": st, "status_label": STATUS_LABEL[st], "orders": counts.get(d.id, 0), "items": items, "terminal_cents": terminal})
    return rows


@staff_view("manage_deliveries")
def deliveries(request):
    today = local_today()
    date_from = parse_date(request.GET.get("from", "")) or today
    date_to = parse_date(request.GET.get("to", "")) or today + timedelta(days=3)
    status = request.GET.get("status", "")
    ctx = {"rows": delivery_rows(date_from, date_to, status), "date_from": date_from, "date_to": date_to, "status": status,
           "statuses": STATUS_LABEL, **tabs_ctx("deliveries")}
    return render(request, "backoffice/operator/deliveries_list.html" if request.headers.get("HX-Request") and request.GET.get("part") else "backoffice/operator/deliveries.html", ctx)


def delivery_context(d: Delivery, tab: str) -> dict:
    stops_orders = list(d.orders.exclude(status__in=CAPACITY_EXCLUDED).select_related("customer").prefetch_related("lines__product"))
    stop_by_order = {s.order_id: s for s in d.stops.all()}
    stops = sorted(stops_orders, key=lambda o: (stop_by_order[o.id].sequence if o.id in stop_by_order else 10_000, o.order_number))
    by_storage: dict[str, int] = {}
    items: dict[tuple, dict] = {}
    for o in stops_orders:
        for ln in o.lines.all():
            by_storage[ln.storage_type_snapshot] = by_storage.get(ln.storage_type_snapshot, 0) + int(ln.qty)
            row = items.setdefault((ln.product.sku, ln.name_snapshot, ln.storage_type_snapshot), {"qty": Decimal(0)})
            row["qty"] += ln.qty
    st = effective(d)
    other = Delivery.objects.filter(status="open", delivery_date__gte=local_today()).exclude(pk=d.pk).order_by("delivery_date", "deliver_starts_at")
    rows = [{"o": o, "seq": stop_by_order[o.id].sequence if o.id in stop_by_order else None,
             "eta": stop_by_order[o.id].planned_arrival if o.id in stop_by_order else None} for o in stops]
    return {
        "d": d, "status": st, "status_label": STATUS_LABEL[st], "tab": tab, "rows": rows,
        "items": sorted(([k[0], k[1], k[2], v["qty"]] for k, v in items.items()), key=lambda r: (r[2], r[1])),
        "by_storage": by_storage, "count": len(stops), "vehicles": Vehicle.objects.filter(is_active=True),
        "drivers": Driver.objects.filter(is_active=True), "move_targets": other,
        "pending": dsvc.order_count(d) - fsvc.ready_orders(d).count() - d.orders.filter(status__in=["picking", "packed", "out_for_delivery", "delivered", "delivery_failed"]).count(),
        "can_edit": st in ("open", "closed"),
    }


@staff_view("manage_deliveries")
def delivery_detail(request, pk: int):
    d = get_object_or_404(Delivery, pk=pk)
    return render(request, "backoffice/operator/delivery_detail.html", delivery_context(d, request.GET.get("tab", "stops")))


def _back(pk: int):
    return redirect("delivery_detail", pk=pk)


@staff_view("manage_deliveries")
@require_POST
def delivery_assign(request, pk: int):
    d = get_object_or_404(Delivery, pk=pk)
    if effective(d) not in ("open", "closed"):
        messages.error(request, "Vehicle and driver can only be changed before approval.")
        return _back(pk)
    d.vehicle = Vehicle.objects.filter(pk=request.POST.get("vehicle") or None).first()
    d.driver = Driver.objects.filter(pk=request.POST.get("driver") or None).first()
    d.save(update_fields=["vehicle", "driver"])
    messages.success(request, "Vehicle and driver saved.")
    return _back(pk)


@staff_view("manage_deliveries")
@require_POST
def delivery_plan(request, pk: int):
    d = get_object_or_404(Delivery, pk=pk)
    n = fsvc.plan_route(d)
    messages.success(request, f"Route proposed for {n} stops (simple postcode order; the route planner replaces this).")
    return _back(pk)


@staff_view("manage_deliveries")
@require_POST
def delivery_approve(request, pk: int):
    d = get_object_or_404(Delivery, pk=pk)
    try:
        r = fsvc.approve_delivery(d, request.user)
        messages.success(request, f"Approved: {r['orders']} orders, lots allocated (oldest best-before first). Print the packing list.")
        return redirect("packing_list", pk=pk)
    except fsvc.FulfilmentError as exc:
        messages.error(request, str(exc))
        return _back(pk)


@staff_view("manage_deliveries")
def packing_list(request, pk: int):
    d = get_object_or_404(Delivery, pk=pk)
    rows = []
    for o in d.orders.filter(status__in=["picking", "packed", "out_for_delivery", "delivered"]).prefetch_related("lines__picks__receiving_line"):
        for ln in o.lines.all():
            rows.append({"order": o, "line": ln, "picks": list(ln.picks.all())})
    return render(request, "backoffice/operator/packing_list.html", {"d": d, "rows": rows})


@staff_view("manage_deliveries")
@require_POST
def delivery_packed(request, pk: int):
    fsvc.mark_packed(get_object_or_404(Delivery, pk=pk), request.user)
    messages.success(request, "Orders marked as packed.")
    return _back(pk)


@staff_view("manage_deliveries")
@require_POST
def delivery_dispatch(request, pk: int):
    try:
        fsvc.dispatch(get_object_or_404(Delivery, pk=pk), request.user)
        messages.success(request, "Delivery is out for delivery.")
    except fsvc.FulfilmentError as exc:
        messages.error(request, str(exc))
    return _back(pk)


@staff_view("manage_ready_orders")
@require_POST
def order_move(request, pk: int):
    order = get_object_or_404(Order, pk=pk)
    target = get_object_or_404(Delivery, pk=request.POST.get("target"))
    came_from = order.delivery_id
    try:
        fsvc.move_order(order, target, request.user)
        messages.success(request, f"{order.order_number} moved to {target.delivery_number}. The customer is notified.")
    except fsvc.FulfilmentError as exc:
        messages.error(request, str(exc))
    nxt = request.POST.get("next", "")
    if nxt == "ready":
        return redirect("ready")
    return redirect("delivery_detail", pk=came_from if Delivery.objects.filter(pk=came_from).exists() else target.pk)


@staff_view("manage_deliveries")
@require_POST
def order_remove(request, pk: int):
    order = get_object_or_404(Order, pk=pk)
    d_id = order.delivery_id
    try:
        fsvc.remove_order(order, request.user)
        messages.success(request, f"{order.order_number} removed and cancelled; stock released.")
    except (osvc.TransitionError, fsvc.FulfilmentError) as exc:
        messages.error(request, str(exc))
    return redirect("delivery_detail", pk=d_id) if Delivery.objects.filter(pk=d_id).exists() else redirect("deliveries")


# ---- SC03 ready ------------------------------------------------------------------------------------------------------------

@staff_view("manage_ready_orders")
def ready(request):
    groups = []
    qs = Delivery.objects.filter(status="open", delivery_date__gte=local_today()).order_by("delivery_date", "deliver_starts_at")
    for d in qs:
        orders_ = list(fsvc.ready_orders(d).select_related("customer").prefetch_related("lines"))
        if not orders_:
            continue
        frozen = sum(1 for o in orders_ if any(ln.storage_type_snapshot == "frozen" for ln in o.lines.all()))
        chilled = sum(1 for o in orders_ if any(ln.storage_type_snapshot == "chilled" for ln in o.lines.all()))
        groups.append({"d": d, "orders": orders_, "count": dsvc.order_count(d), "items": sum(int(ln.qty) for o in orders_ for ln in o.lines.all()),
                       "value": sum(o.total_cents for o in orders_), "frozen": frozen, "chilled": chilled,
                       "left": d.collect_ends_at - now(), "targets": [t for t in qs if t.pk != d.pk]})
    return render(request, "backoffice/operator/ready.html", {"groups": groups, **tabs_ctx("ready")})


# ---- SC04 confirm -----------------------------------------------------------------------------------------------------------

def confirm_rows():
    rows = []
    for o in Order.objects.filter(status="pending_confirmation").select_related("customer", "delivery", "claimed_by").prefetch_related("attempts", "customer__flags").order_by("confirm_deadline_at"):
        flags = {k: sum(1 for f in o.customer.flags.all() if f.kind == k) for k in ("refused_at_confirmation", "refused_at_delivery")}
        rows.append({"o": o, "attempts": len(o.attempts.all()), "flags": flags, "waiting": now() - o.placed_at,
                     "warn": o.confirm_deadline_at and o.confirm_deadline_at - now() <= timedelta(minutes=int(get_setting("cod_warn_minutes")))})
    return rows


@staff_view("confirm_cod_orders")
def confirm(request):
    ctx = {"rows": confirm_rows(), **tabs_ctx("confirm")}
    tpl = "backoffice/operator/confirm_list.html" if request.headers.get("HX-Request") and request.GET.get("part") else "backoffice/operator/confirm.html"
    return render(request, tpl, ctx)


@staff_view("confirm_cod_orders")
def confirm_detail(request, pk: int):
    order = get_object_or_404(Order.objects.select_related("customer", "delivery"), pk=pk, status="pending_confirmation")
    if not osvc.claim(order, request.user, int(get_setting("order_claim_minutes"))):
        messages.error(request, f"{order.claimed_by.get_username()} is already calling this customer.")
        return redirect("confirm")
    order.refresh_from_db()
    ctx = {"o": order, "lines": order.lines.all(), "attempts": order.attempts.select_related("operator"),
           "flags": order.customer.flags.values_list("kind", flat=True),
           "targets": Delivery.objects.filter(status="open", delivery_date__gte=local_today()).order_by("delivery_date", "deliver_starts_at"),
           **tabs_ctx("confirm")}
    return render(request, "backoffice/operator/confirm_detail.html", ctx)


@staff_view("confirm_cod_orders")
@require_POST
def confirm_action(request, pk: int, action: str):
    order = get_object_or_404(Order, pk=pk)
    flag = request.POST.get("flag") == "on"
    try:
        if action == "confirm":
            osvc.confirm_cod(order, request.user, request.POST.get("note", ""))
            messages.success(request, f"{order.order_number} confirmed. It is now in Orders ready for delivery.")
        elif action == "no-answer":
            nxt = parse_datetime(request.POST.get("next_call_at", "")) if request.POST.get("next_call_at") else None
            osvc.log_attempt(order, request.user, "no_answer", request.POST.get("note", ""), nxt)
            messages.success(request, "Call logged.")
            return redirect("confirm_detail", pk=pk)
        elif action == "reject":
            reason = request.POST.get("reason", "").strip()
            if not reason:
                messages.error(request, "A reason is required to reject an order.")
                return redirect("confirm_detail", pk=pk)
            osvc.log_attempt(order, request.user, "rejected", reason, flag=flag)
            messages.success(request, f"{order.order_number} rejected; stock released.")
        elif action == "change-delivery":
            fsvc.move_order(order, get_object_or_404(Delivery, pk=request.POST.get("target")), request.user)
            messages.success(request, "Delivery changed.")
            return redirect("confirm_detail", pk=pk)
    except (osvc.TransitionError, fsvc.FulfilmentError) as exc:
        messages.error(request, str(exc))
    return redirect("confirm")


# ---- SC05 close --------------------------------------------------------------------------------------------------------------

def _dec(value: str) -> Decimal:
    try:
        return Decimal(value or "0")
    except InvalidOperation:
        return Decimal(0)


@staff_view("close_deliveries")
def close(request, pk: int):
    d = get_object_or_404(Delivery, pk=pk)
    if d.status != "out_for_delivery":
        messages.error(request, "Only a delivery that is out for delivery can be closed.")
        return redirect("delivery_detail", pk=pk)
    stops = list(d.stops.select_related("order").prefetch_related("order__lines", "returns").order_by("sequence"))
    reasons = list(ReturnReason.objects.filter(is_active=True))
    if request.method == "POST":
        entries = []
        for s in stops:
            p = f"o{s.order_id}"
            outcome = request.POST.get(f"{p}_outcome", "delivered")
            returns = []
            if outcome != "delivered":
                for ln in s.order.lines.all():
                    qty = _dec(request.POST.get(f"{p}_ret_{ln.id}", "0"))
                    if qty > 0:
                        returns.append(fsvc.ReturnEntry(ln.id, qty, request.POST.get(f"{p}_reason_{ln.id}", ""), request.POST.get(f"{p}_note_{ln.id}", "")))
            entries.append(fsvc.StopEntry(s.order_id, outcome, request.POST.get(f"{p}_paid") == "on", request.POST.get(f"{p}_flag") == "on",
                                          request.POST.get(f"{p}_failure", ""), returns))
        final = request.POST.get("submit") == "close"
        try:
            fsvc.close_delivery(d, request.user, entries, final)
            messages.success(request, "Delivery closed." if final else "Draft saved.")
            return redirect("delivery_detail" if final else "close", pk=pk)
        except fsvc.FulfilmentError as exc:
            messages.error(request, str(exc))
    return render(request, "backoffice/operator/close.html", {"d": d, "stops": stops, "reasons": reasons})
