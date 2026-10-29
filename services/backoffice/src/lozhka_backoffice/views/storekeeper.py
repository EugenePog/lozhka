"""Storekeeper: Incoming deliveries (SC06) and stock adjustments."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import connection
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from lozhka_api.catalog.models import Product
from lozhka_api.domain import receiving as rsvc
from lozhka_api.domain.timeutil import local_today
from lozhka_api.procurement.models import Receiving, ReceivingLine, StockAdjustment, Supplier, SupplierProduct

from ..permissions import staff_view

ISSUE_LABEL = {"ok": "OK", "fixed_manually": "Quantity fixed manually", "best_before_missing": "Best-before date missing", "unit_differs": "Unit differs"}
ISSUE_CLASS = {"ok": "", "fixed_manually": "warn", "best_before_missing": "bad", "unit_differs": "bad"}


def _dec(v: str, default=None):
    try:
        return Decimal(v) if v not in (None, "") else default
    except InvalidOperation:
        return default


@staff_view("receive_goods")
def incoming(request):
    recs = list(Receiving.objects.filter(Q(status="open") | Q(received_at__date__gte=local_today() - timedelta(days=14)))
                .select_related("supplier").order_by("status", "-expected_date", "-id"))
    for r in recs:
        r.issues = rsvc.open_issue_count(r)
    selected = next((r for r in recs if str(r.pk) == request.GET.get("r")), recs[0] if recs else None)
    lines = []
    if selected:
        for ln in selected.lines.select_related("product", "receiving__supplier").order_by("product__sku"):
            issue = rsvc.line_issue(ln)
            lines.append({"l": ln, "issue": issue, "label": ISSUE_LABEL[issue], "cls": ISSUE_CLASS[issue]})
    return render(request, "backoffice/storekeeper/incoming.html", {"recs": recs, "sel": selected, "lines": lines, "suppliers": Supplier.objects.filter(is_active=True)})


@staff_view("receive_goods")
@require_POST
def incoming_save(request, pk: int):
    rec = get_object_or_404(Receiving, pk=pk)
    try:
        for ln in rec.lines.select_related("product", "receiving__supplier"):
            k = f"l{ln.id}"
            qty = _dec(request.POST.get(f"{k}_qty"))
            rejected = _dec(request.POST.get(f"{k}_rej"))
            bb = parse_date(request.POST.get(f"{k}_bb", "") or "")
            rsvc.update_line(ln, request.user, qty, bb, request.POST.get(f"{k}_lot"), rejected)
        messages.success(request, "Changes saved. Manual fixes are kept if the file is loaded again.")
    except rsvc.ReceivingError as exc:
        messages.error(request, str(exc))
    if request.POST.get("submit") == "receive":
        try:
            rsvc.receive(rec, request.user)
            messages.success(request, "Delivery received. The stock is added.")
        except rsvc.ReceivingError as exc:
            messages.error(request, str(exc))
    return redirect(f"/incoming/?r={pk}")


@staff_view("receive_goods")
@require_POST
def incoming_upload(request):
    """STUB for the supplier-file parser (module M2): reads a simple CSV with the columns
    supplier_sku, qty, best_before, lot. Excel files and per-supplier layouts come with the parser."""
    supplier = get_object_or_404(Supplier, pk=request.POST.get("supplier"))
    f = request.FILES.get("file")
    if f is None:
        messages.error(request, "Choose a file.")
        return redirect("incoming")
    if not f.name.lower().endswith(".csv"):
        messages.error(request, "Only simple CSV files for now (columns: supplier_sku, qty, best_before, lot). Excel layouts arrive with the parser.")
        return redirect("incoming")
    ref = request.POST.get("delivery_ref") or f"UP-{date.today():%Y%m%d}-{f.name[:20]}"
    rec, created = Receiving.objects.get_or_create(supplier=supplier, delivery_ref=ref, defaults={"expected_date": local_today()})
    if not created and rec.status != "open":
        messages.error(request, "That delivery is already received.")
        return redirect("incoming")
    n = 0
    unknown = []
    text = f.read().decode("utf-8-sig")
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
        sp = SupplierProduct.objects.filter(supplier=supplier, supplier_sku=row.get("supplier_sku", "").strip()).select_related("product").first()
        if sp is None or sp.product is None:
            unknown.append(row.get("supplier_sku", "?"))
            continue
        qty = _dec(row.get("qty"), Decimal(0))
        ReceivingLine.objects.update_or_create(
            receiving=rec, product=sp.product, supplier_lot_code=(row.get("lot") or "").strip(),
            defaults={"supplier_sku": sp.supplier_sku, "qty_expected": qty, "qty_received": qty,
                      "best_before": parse_date(row.get("best_before", "") or ""), "best_before_source": "document"})
        n += 1
    messages.success(request, f"{n} lines loaded." + (f" Unknown supplier codes skipped: {', '.join(unknown)}." if unknown else ""))
    return redirect(f"/incoming/?r={rec.pk}")


@staff_view("adjust_stock")
def stock(request):
    q = request.GET.get("q", "").strip()
    sql = """select lb.lot_id, p.sku, p.slug, coalesce(t.name, p.sku) name, lb.supplier_lot_code, lb.best_before, lb.balance
               from gold.lot_balance lb join app.product p on p.id = lb.product_id
               left join app.product_translation t on t.product_id = p.id and t.lang = 'en'
              where lb.balance <> 0 and (%s = '' or p.sku ilike '%%'||%s||'%%' or t.name ilike '%%'||%s||'%%')
              order by p.sku, lb.best_before limit 200"""
    with connection.cursor() as cur:
        cur.execute(sql, [q, q, q])
        lots = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]
    log = StockAdjustment.objects.select_related("receiving_line__product", "created_by").order_by("-created_at")[:25]
    return render(request, "backoffice/storekeeper/stock.html", {"lots": lots, "q": q, "log": log,
                  "reasons": [(k, v) for k, v in StockAdjustment.REASONS if k != "return_to_stock"]})


@staff_view("adjust_stock")
@require_POST
def stock_adjust(request, lot_id: int):
    line = get_object_or_404(ReceivingLine, pk=lot_id)
    delta = _dec(request.POST.get("delta"))
    try:
        if delta is None:
            raise rsvc.ReceivingError("Enter a quantity change, for example -3 to write off three.")
        rsvc.adjust(line, delta, request.POST.get("reason", ""), request.POST.get("note", ""), request.user)
        messages.success(request, "Adjustment saved and logged.")
    except rsvc.ReceivingError as exc:
        messages.error(request, str(exc))
    return redirect(f"/stock/?q={request.POST.get('q', '')}")
