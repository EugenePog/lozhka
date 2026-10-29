"""Operator and storekeeper flows end to end (through the views, so permissions and forms are exercised)."""
from decimal import Decimal

import pytest

from conftest import post_json
from lozhka_api.catalog.models import Product
from lozhka_api.domain import stock
from lozhka_api.procurement.models import Receiving, ReceivingLine, StockAdjustment, Supplier
from lozhka_api.sales.models import Delivery, Driver, Order, Vehicle


def place_cod_order(public_client):
    for sku, qty in (("DAI-KEF-1L", 6), ("MEA-DOK-500", 5), ("PAN-GRE-900", 4), ("PRE-GHE-720", 3)):
        post_json(public_client, "/api/v1/cart/items", {"sku": sku, "qty": qty})
    slot = public_client.get("/api/v1/delivery/offers?postcode=1053EC").json()["slots"][0]
    body = dict(email="flow@example.com", phone="0612345678", first_name="F", last_name="Low", street="Damrak", house_number="1",
                postcode="1012LG", city="Amsterdam", delivery_choice="time_range", template_code=slot["template_code"],
                delivery_date=slot["delivery_date"], payment_method="card_on_delivery", terms_accepted=True)
    out = post_json(public_client, "/api/v1/checkout", body).json()
    return Order.objects.get(order_number=out["order_number"])


def test_confirm_approve_dispatch_close_with_return(public_client, staff):
    order = place_cod_order(public_client)
    kef = Product.objects.get(sku="DAI-KEF-1L")
    op = staff("operator@lozhka.example")

    # 1. the order waits for the operator; it is not "ready" yet
    assert op.get("/confirm/").status_code == 200 and order.order_number.encode() in op.get("/confirm/").content
    assert op.post(f"/confirm/{order.pk}/confirm/", {"note": "spoke to customer"}).status_code == 302
    order.refresh_from_db()
    assert order.status == "confirmed" and order.reservations.filter(status="committed").count() == 4

    # 2. approval needs a vehicle and driver, then allocates lots oldest-best-before first
    d = order.delivery
    r = op.post(f"/deliveries/{d.pk}/approve/")
    assert Delivery.objects.get(pk=d.pk).status == "open"          # blocked: no vehicle yet
    other_pending = d.orders.exclude(pk=order.pk).filter(status__in=["awaiting_payment", "pending_confirmation"])
    for o in other_pending:                                         # demo orders in the same delivery would block approval
        op.post(f"/confirm/{o.pk}/confirm/")
    op.post(f"/deliveries/{d.pk}/assign/", {"vehicle": Vehicle.objects.first().pk, "driver": Driver.objects.first().pk})
    assert op.post(f"/deliveries/{d.pk}/approve/").status_code == 302
    d.refresh_from_db()
    assert d.status == "approved"
    kef_picks = list(order.lines.get(product=kef).picks.select_related("receiving_line").order_by("receiving_line__best_before"))
    assert sum(p.qty for p in kef_picks) == 6
    assert kef_picks[0].receiving_line.supplier_lot_code.endswith("-B")      # the +7 day lot comes before the +18 day lot
    assert op.get(f"/deliveries/{d.pk}/packing-list/").status_code == 200

    # 3. dispatch consumes the reservations; stock now drops for real
    on_hand_before = stock.available([kef.id])[kef.id]
    op.post(f"/deliveries/{d.pk}/dispatch/")
    d.refresh_from_db(); order.refresh_from_db()
    assert d.status == "out_for_delivery" and order.status == "out_for_delivery"
    assert order.reservations.filter(status="consumed").count() == 4
    assert stock.available([kef.id])[kef.id] == on_hand_before          # reservation became a pick: availability unchanged

    # 4. close: two kefir bottles come back (restock reason), payment taken, customer flagged for refusing nothing
    line = order.lines.get(product=kef)
    stop_orders = [st.order for st in d.stops.select_related("order")]
    assert order in stop_orders
    form = {f"o{o.pk}_outcome": "delivered" for o in stop_orders}
    form.update({f"o{order.pk}_outcome": "returns", f"o{order.pk}_paid": "on",
                 f"o{order.pk}_ret_{line.id}": "2", f"o{order.pk}_reason_{line.id}": "wrong_item", "submit": "close"})
    for o in stop_orders:
        form[f"o{o.pk}_paid"] = "on"
    r = op.post(f"/deliveries/{d.pk}/close/", form)
    d.refresh_from_db(); order.refresh_from_db()
    assert d.status == "completed" and order.status == "delivered"
    assert StockAdjustment.objects.filter(reason="return_to_stock", qty_delta=Decimal("2")).exists()
    assert order.payments.filter(status="paid").exists()


def test_write_off_reason_does_not_restock(public_client, staff):
    from lozhka_api.domain import fulfilment as f

    order = place_cod_order(public_client)
    op_user = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.get(username="operator@lozhka.example")
    from lozhka_api.domain import orders as o_svc

    o_svc.confirm_cod(order, op_user)
    d = order.delivery
    for o in d.orders.exclude(pk=order.pk).filter(status="pending_confirmation"):
        o_svc.confirm_cod(o, op_user)
    d.vehicle, d.driver = Vehicle.objects.first(), Driver.objects.first()
    d.save()
    f.approve_delivery(d, op_user); f.dispatch(d, op_user)
    line = order.lines.first()
    entries = [f.StopEntry(st.order_id, "delivered") for st in d.stops.exclude(order=order)] + [
        f.StopEntry(order.pk, "returns", True, False, "", [f.ReturnEntry(line.id, Decimal("1"), "damaged")])]
    f.close_delivery(d, op_user, entries, final=True)
    assert not StockAdjustment.objects.filter(reason="return_to_stock", note__startswith=order.order_number).exists()


def test_unconfirmed_order_blocks_approval(public_client, staff):
    order = place_cod_order(public_client)
    op = staff("operator@lozhka.example")
    d = order.delivery
    op.post(f"/deliveries/{d.pk}/assign/", {"vehicle": Vehicle.objects.first().pk, "driver": Driver.objects.first().pk})
    op.post(f"/deliveries/{d.pk}/approve/")
    assert Delivery.objects.get(pk=d.pk).status == "open"


def test_rejecting_requires_a_reason_and_releases_stock(public_client, staff):
    order = place_cod_order(public_client)
    op = staff("operator@lozhka.example")
    op.post(f"/confirm/{order.pk}/reject/", {"reason": ""})
    order.refresh_from_db(); assert order.status == "pending_confirmation"
    op.post(f"/confirm/{order.pk}/reject/", {"reason": "customer said no", "flag": "on"})
    order.refresh_from_db()
    assert order.status == "cancelled" and not order.reservations.filter(status__in=["held", "committed"]).exists()
    assert order.customer.flags.filter(kind="refused_at_confirmation").exists()


def test_expired_pay_on_delivery_hold_cancels_the_order(public_client):
    from datetime import timedelta
    from lozhka_api.domain.timeutil import now

    order = place_cod_order(public_client)
    order.reservations.update(expires_at=now() - timedelta(minutes=1))
    assert order.pk in stock.expire_holds()
    order.refresh_from_db()
    assert order.status == "cancelled" and order.cancel_reason == "not_confirmed"


def test_two_operators_do_not_call_the_same_customer(public_client, staff):
    order = place_cod_order(public_client)
    a, b = staff("operator@lozhka.example"), staff("all@lozhka.example")
    assert a.get(f"/confirm/{order.pk}/").status_code == 200
    assert b.get(f"/confirm/{order.pk}/").status_code == 302


def test_receiving_needs_best_before_then_adds_stock(staff):
    sk = staff("store@lozhka.example")
    supplier = Supplier.objects.get(name="Eastern Foods Wholesale BV")
    rec = Receiving.objects.create(supplier=supplier, delivery_ref="TEST-1")
    product = Product.objects.get(sku="PAN-GRE-900")
    line = ReceivingLine.objects.create(receiving=rec, product=product, supplier_lot_code="T-LOT", qty_expected=10, qty_received=10)
    before = stock.available([product.id])[product.id]
    sk.post(f"/incoming/{rec.pk}/save/", {f"l{line.id}_qty": "10", f"l{line.id}_bb": "", f"l{line.id}_lot": "T-LOT", "submit": "receive"})
    rec.refresh_from_db(); assert rec.status == "open"                      # blocked: date missing
    sk.post(f"/incoming/{rec.pk}/save/", {f"l{line.id}_qty": "9", f"l{line.id}_bb": "2027-06-01", f"l{line.id}_lot": "T-LOT", "submit": "receive"})
    rec.refresh_from_db(); assert rec.status == "accepted"
    assert stock.available([product.id])[product.id] == before + 9
    assert rec.supplier.deliverylinefix_set.filter(field="qty_received", value="9").exists()    # the manual fix is kept


def test_adjustment_needs_a_reason_and_cannot_go_negative(staff):
    sk = staff("store@lozhka.example")
    lot = ReceivingLine.objects.get(product__sku="PAN-GRE-900", supplier_lot_code="LOT-900-A")
    n = StockAdjustment.objects.count()
    sk.post(f"/stock/{lot.pk}/adjust/", {"delta": "-1", "reason": ""})
    sk.post(f"/stock/{lot.pk}/adjust/", {"delta": "-9999", "reason": "waste_damaged"})
    assert StockAdjustment.objects.count() == n
    sk.post(f"/stock/{lot.pk}/adjust/", {"delta": "-2", "reason": "waste_damaged", "note": "dented"})
    assert StockAdjustment.objects.count() == n + 1


def test_template_save_is_blocked_on_gap_and_accepted_when_whole_day_is_covered(staff):
    from lozhka_api.sales.models import DeliveryTemplate

    ad = staff("admin@lozhka.example")
    rows = list(DeliveryTemplate.objects.order_by("sort"))

    def form(collect_ranges):
        data = {"id": [], "code": [], "name": [], "collect_from": [], "collect_to": [], "deliver_from": [], "deliver_to": [],
                "capacity_orders": [], "cod_confirmation_hours": []}
        for i, (t, (cf, ct)) in enumerate(zip(rows, collect_ranges)):
            data["id"].append(str(t.id)); data["code"].append(t.code); data["name"].append(t.name)
            data["collect_from"].append(cf); data["collect_to"].append(ct)
            data["deliver_from"].append(t.deliver_from.strftime("%H:%M")); data["deliver_to"].append(t.deliver_to.strftime("%H:%M"))
            data["capacity_orders"].append("20"); data["cod_confirmation_hours"].append("4")
            data[f"active_{t.id}_{i}"] = "on"
        data["id"].append("new"); data["code"].append(""); data["name"].append("")
        for k in ("collect_from", "collect_to", "deliver_from", "deliver_to"): data[k].append("00:00")
        data["capacity_orders"].append("20"); data["cod_confirmation_hours"].append("4")
        return data

    gap = ad.post("/templates/", form([("22:00", "10:00"), ("10:00", "15:00"), ("16:00", "22:00")]))
    assert gap.status_code == 200 and b"Gap or overlap" in gap.content
    assert DeliveryTemplate.objects.get(code="B").collect_to.hour == 16
    ok = ad.post("/templates/", form([("23:00", "10:00"), ("10:00", "16:00"), ("16:00", "23:00")]))
    assert ok.status_code == 302
    assert DeliveryTemplate.objects.get(code="A").collect_from.hour == 23
