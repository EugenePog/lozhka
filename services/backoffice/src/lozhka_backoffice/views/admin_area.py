"""Admin: delivery templates (SC07), delivery rules, return reasons, suppliers (SC08)."""
from __future__ import annotations

import json
from datetime import time

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lozhka_api.core.models import Setting
from lozhka_api.domain import deliveries as dsvc
from lozhka_api.domain import secrets as secret_store
from lozhka_api.domain.settings_store import get_setting
from lozhka_api.domain.timeutil import hhmm
from lozhka_api.procurement.models import (
    Supplier, SupplierCredential, SupplierCredentialSecret, SupplierDeliverySchedule, SupplierProduct,
)
from lozhka_api.sales.models import DeliveryFeeTier, DeliveryTemplate, DeliveryZone, ReturnReason, ReturnReasonTranslation

from ..permissions import staff_view

COLORS = ["#1E4A2B", "#A9481F", "#4b7f52", "#c9803a", "#6c8f5a", "#8c5a3c"]


def _t(value: str) -> time | None:
    try:
        return dsvc.time_from_str(value.strip())
    except (ValueError, AttributeError):
        return None


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def bar_segments(rows: list[dict]) -> list[dict]:
    """24-hour bar: the collection ranges of the active templates, wrapping past midnight."""
    segs = []
    for i, r in enumerate(rows):
        start, end = _minutes(r["collect_from"]), _minutes(r["collect_to"])
        length = 1440 if end == start else (end - start) % 1440
        parts = [(start, min(length, 1440 - start))] + ([(0, length - (1440 - start))] if start + length > 1440 else [])
        for a, ln in parts:
            segs.append({"left": a / 14.4, "width": ln / 14.4, "label": f'{r["code"]} {hhmm(r["collect_from"])}–{hhmm(r["collect_to"])}', "color": COLORS[i % len(COLORS)]})
    return segs


def delivered_when(t: dict) -> str:
    """'same day' / 'next day': where the delivery range falls relative to the day the collection ends."""
    from datetime import date

    class _T:  # the occurrence maths only needs the four times
        collect_from, collect_to, deliver_from, deliver_to = t["collect_from"], t["collect_to"], t["deliver_from"], t["deliver_to"]

    occ = dsvc.occurrence_from_collection_day(_T, date(2026, 1, 12))  # type: ignore[arg-type]
    days = (occ.delivery_date - occ.collect_starts_at.date()).days
    return "same day" if days == 0 else ("next day" if days == 1 else f"+{days} days")


@staff_view("edit_delivery_templates")
def templates(request):
    if request.method == "POST":
        return templates_save(request)
    rows = [_row(t) for t in DeliveryTemplate.objects.all()]
    return render(request, "backoffice/admin/templates.html", {"rows": rows, "segs": bar_segments([r for r in rows if r["is_active"]]), "gap": dsvc.check_template_coverage([r for r in rows if r["is_active"]])})


def _row(t: DeliveryTemplate) -> dict:
    d = {"id": t.id, "code": t.code, "name": t.name, "collect_from": t.collect_from, "collect_to": t.collect_to, "deliver_from": t.deliver_from,
         "deliver_to": t.deliver_to, "capacity_orders": t.capacity_orders, "cod_confirmation_hours": t.cod_confirmation_hours, "is_active": t.is_active, "sort": t.sort}
    d["delivered"] = delivered_when(d)
    return d


def templates_save(request):
    """All templates are saved together, because the collection ranges only have to tile the day as a set."""
    post = request.POST
    ids = [i for i in post.getlist("id")]
    parsed, errors = [], []
    for n, tid in enumerate(ids):
        g = lambda k: post.getlist(k)[n]  # noqa: E731
        is_new = tid == "new"
        if is_new and not g("code").strip():
            continue
        times = [_t(g(k)) for k in ("collect_from", "collect_to", "deliver_from", "deliver_to")]
        if any(x is None for x in times):
            errors.append(f"{g('code') or g('name')}: enter times as HH:MM.")
            continue
        try:
            parsed.append({"id": None if is_new else int(tid), "code": g("code").strip().upper(), "name": g("name").strip(),
                           "collect_from": times[0], "collect_to": times[1], "deliver_from": times[2], "deliver_to": times[3],
                           "capacity_orders": int(g("capacity_orders")), "cod_confirmation_hours": int(g("cod_confirmation_hours")),
                           "is_active": (post.getlist(f"active_{tid}_{n}") != [])})
        except ValueError:
            errors.append(f"{g('code')}: capacity and hours must be whole numbers.")
    active = [p for p in parsed if p["is_active"]]
    gap = dsvc.check_template_coverage(active)
    if gap:
        errors.append(f"The collection ranges of the active templates must cover the 24 hours exactly once. Gap or overlap: {gap} minutes.")
    if any(not p["code"] or not p["name"] or p["capacity_orders"] < 1 for p in parsed):
        errors.append("Every template needs a code, a name and a capacity of at least 1.")
    if errors:
        for e in errors:
            messages.error(request, e)
        rows = [dict(p, delivered=delivered_when(p)) for p in parsed]
        return render(request, "backoffice/admin/templates.html", {"rows": rows, "segs": bar_segments(active), "gap": gap})
    try:
        with transaction.atomic():
            for i, p in enumerate(parsed, start=1):
                fields = {k: p[k] for k in ("code", "name", "collect_from", "collect_to", "deliver_from", "deliver_to", "capacity_orders", "cod_confirmation_hours", "is_active")}
                if p["id"]:
                    DeliveryTemplate.objects.filter(pk=p["id"]).update(sort=i, **fields)
                else:
                    DeliveryTemplate.objects.create(sort=i, **fields)
    except IntegrityError as exc:
        messages.error(request, f"Not saved: {exc.__cause__ or exc}")
        return redirect("templates")
    messages.success(request, "Templates saved. Deliveries created from now on use these values; existing deliveries keep theirs.")
    return redirect("templates")


@staff_view("edit_delivery_templates")
def templates_preview(request):
    offers = dsvc.offers()
    return render(request, "backoffice/admin/templates_preview.html", {"offers": offers, "asap": dsvc.asap_offer(offers)})


# ---- delivery rules ------------------------------------------------------------------------------------------------------

RULE_KEYS = [("min_order_cents", "Minimum order (cents)", "int"), ("cod_enabled", "Offer pay on delivery (card terminal)", "bool"),
             ("reservation_ttl_min", "Online payment hold (minutes)", "int"), ("delivery_horizon_days", "Delivery choices: days ahead", "int"),
             ("cod_warn_minutes", "Warn operators before the confirmation deadline (minutes)", "int"),
             ("order_claim_minutes", "Hold an order while an operator calls (minutes)", "int")]


@staff_view("edit_delivery_rules")
def rules(request):
    if request.method == "POST":
        with transaction.atomic():
            for key, _label, kind in RULE_KEYS:
                if kind == "bool":
                    value = request.POST.get(key) == "on"
                else:
                    try:
                        value = int(request.POST.get(key, ""))
                    except ValueError:
                        messages.error(request, f"{key}: whole number required.")
                        return redirect("rules")
                Setting.objects.update_or_create(key=key, defaults={"value": value})
            for z in DeliveryZone.objects.all():
                z.is_active = request.POST.get(f"zone_{z.id}_active") == "on"
                ranges = [r.strip() for r in request.POST.get(f"zone_{z.id}_ranges", "").replace("\n", ",").split(",") if r.strip()]
                z.postcode4_ranges = ranges
                z.save()
                lines = [ln for ln in request.POST.get(f"zone_{z.id}_fees", "").splitlines() if ln.strip()]
                tiers = []
                for ln in lines:
                    parts = [p.strip() for p in ln.split(",")]
                    tiers.append((int(parts[0]), int(parts[1]) if parts[1] else None, int(parts[2])))
                z.fee_tiers.all().delete()
                DeliveryFeeTier.objects.bulk_create([DeliveryFeeTier(zone=z, min_subtotal_cents=a, max_subtotal_cents=b, fee_cents=c) for a, b, c in tiers])
        messages.success(request, "Delivery rules saved.")
        return redirect("rules")
    values = [{"key": k, "label": lbl, "kind": kind, "value": get_setting(k)} for k, lbl, kind in RULE_KEYS]
    zones = [{"z": z, "ranges": ", ".join(z.postcode4_ranges),
              "fees": "\n".join(f"{t.min_subtotal_cents},{t.max_subtotal_cents if t.max_subtotal_cents is not None else ''},{t.fee_cents}" for t in z.fee_tiers.all())}
             for z in DeliveryZone.objects.all()]
    return render(request, "backoffice/admin/rules.html", {"values": values, "zones": zones})


# ---- return reasons ------------------------------------------------------------------------------------------------------

@staff_view("edit_return_reasons")
def return_reasons(request):
    if request.method == "POST":
        post = request.POST
        with transaction.atomic():
            for i, rid in enumerate(post.getlist("id")):
                code = post.getlist("code")[i].strip().lower().replace(" ", "_")
                if rid == "new" and not code:
                    continue
                r = ReturnReason.objects.filter(pk=rid).first() if rid != "new" else ReturnReason()
                r.code, r.sort = code, (i + 1) * 10
                r.restock = f"restock_{rid}_{i}" in post
                r.flags_customer = f"flag_{rid}_{i}" in post
                r.is_active = f"active_{rid}_{i}" in post
                r.save()
                for lang in ("nl", "en", "ru"):
                    name = post.getlist(f"name_{lang}")[i].strip()
                    if name:
                        ReturnReasonTranslation.objects.update_or_create(reason=r, lang=lang, defaults={"name": name})
        messages.success(request, "Return reasons saved.")
        return redirect("return_reasons")
    rows = []
    for r in ReturnReason.objects.all():
        names = {t.lang: t.name for t in r.translations.all()}
        rows.append({"r": r, "nl": names.get("nl", ""), "en": names.get("en", ""), "ru": names.get("ru", "")})
    return render(request, "backoffice/admin/return_reasons.html", {"rows": rows})


# ---- suppliers ------------------------------------------------------------------------------------------------------------

@staff_view("edit_suppliers")
def suppliers(request):
    return render(request, "backoffice/admin/suppliers.html", {"suppliers": Supplier.objects.all()})


@staff_view("edit_suppliers")
def supplier_detail(request, pk: int):
    s = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        try:
            s.default_lead_time_days = int(request.POST.get("lead") or 0)
            s.min_order_value_cents = int(float(request.POST.get("min_order") or 0) * 100)
            fd = request.POST.get("free_delivery", "")
            s.free_delivery_threshold_cents = int(float(fd) * 100) if fd else None
            s.payment_terms_days = int(request.POST.get("terms_days")) if request.POST.get("terms_days") else None
            s.order_email, s.contact = request.POST.get("order_email", ""), request.POST.get("contact", "")
            s.save()
            # order schedule: one line per cycle "order weekday,cutoff HH:MM,delivery weekday"
            lines = [ln for ln in request.POST.get("schedule", "").splitlines() if ln.strip()]
            parsed = []
            for ln in lines:
                a, b, c = [p.strip() for p in ln.split(",")]
                parsed.append((int(a), _t(b), int(c)))
            s.schedules.all().delete()
            SupplierDeliverySchedule.objects.bulk_create([SupplierDeliverySchedule(supplier=s, order_weekday=a, order_cutoff_time=b, delivery_weekday=c) for a, b, c in parsed])
            for sp in s.products.all():
                p = request.POST.get(f"prio_{sp.id}")
                if p:
                    sp.priority = int(p)
                    sp.save(update_fields=["priority"])
            messages.success(request, "Supplier saved.")
        except (ValueError, TypeError, AttributeError):
            messages.error(request, "Check the numbers and the schedule lines (weekday 0 = Monday, time HH:MM).")
        return redirect("supplier_detail", pk=pk)
    creds = [{"c": c, "has_secret": hasattr(c, "secret")} for c in s.credentials.select_related("secret")]
    sched = "\n".join(f"{x.order_weekday},{hhmm(x.order_cutoff_time)},{x.delivery_weekday}" for x in s.schedules.all())
    return render(request, "backoffice/admin/supplier_detail.html", {"s": s, "creds": creds, "sched": sched, "products": s.products.select_related("product").order_by("product__sku"),
                  "can_set_creds": request.user.has_perm("core.set_supplier_credentials"), "kinds": SupplierCredential.KINDS})


@staff_view("set_supplier_credentials")
@require_POST
def supplier_credential(request, pk: int):
    s = get_object_or_404(Supplier, pk=pk)
    secret = request.POST.get("secret", "")
    label = request.POST.get("label", "").strip()
    if not secret or not label:
        messages.error(request, "Enter a label and the new secret.")
        return redirect("supplier_detail", pk=pk)
    try:
        sealed = secret_store.seal(secret)
    except Exception:  # noqa: BLE001 - never echo key material
        messages.error(request, "The encryption key is not configured. Credentials were not saved.")
        return redirect("supplier_detail", pk=pk)
    with transaction.atomic():
        cred, _ = SupplierCredential.objects.update_or_create(
            supplier=s, label=label, defaults={"kind": request.POST.get("kind", "portal_login"), "username": request.POST.get("username", ""),
                                               "endpoint_url": request.POST.get("endpoint_url", ""), "is_active": True, "created_by": request.user})
        SupplierCredentialSecret.objects.update_or_create(credential=cred, defaults={"secret_encrypted": sealed, "key_version": secret_store.KEY_VERSION})
        cred.last_rotated_at = timezone.now()
        cred.save(update_fields=["last_rotated_at"])
    messages.success(request, "Credentials replaced. The stored value can never be viewed again.")
    return redirect("supplier_detail", pk=pk)
