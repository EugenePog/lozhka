import pytest

from conftest import post_json
from lozhka_api.domain import deliveries


def fill_cart(client, items=(("DAI-KEF-1L", 6), ("MEA-DOK-500", 5), ("PAN-GRE-900", 4), ("PRE-GHE-720", 3))):
    for sku, qty in items:
        assert post_json(client, "/api/v1/cart/items", {"sku": sku, "qty": qty}).status_code == 200


def checkout_body(client, payment="card_on_delivery", **over):
    slot = client.get("/api/v1/delivery/offers?postcode=1053EC").json()["slots"][0]
    body = dict(email="t1@example.com", phone="0612345678", first_name="T", last_name="One", street="Damrak", house_number="1",
                postcode="1012LG", city="Amsterdam", delivery_choice="time_range", template_code=slot["template_code"],
                delivery_date=slot["delivery_date"], payment_method=payment, terms_accepted=True)
    body.update(over)
    return body


def test_browse_search_and_product_page(public_client):
    home = public_client.get("/api/v1/home?lang=en").json()
    assert home["bestsellers"] and home["offers"] and home["settings"]["min_order_cents"] == 5000
    assert public_client.get("/api/v1/products?category=dairy-eggs&lang=en").json()["total"] >= 4
    # transliterated search term finds the Russian-named product from a Latin query
    assert public_client.get("/api/v1/products?q=pelmeni&lang=ru").json()["total"] >= 2
    page = public_client.get("/api/v1/products/dai-kef-1l?lang=nl").json()
    assert page["sku"] == "DAI-KEF-1L" and page["allergens"][0]["code"] == "milk" and page["related"]


def test_out_of_stock_item_cannot_be_added(public_client):
    r = post_json(public_client, "/api/v1/cart/items", {"sku": "FIS-SHP-250", "qty": 1})
    assert r.status_code == 409


def test_cart_quantity_is_clamped_to_availability(public_client):
    cart = post_json(public_client, "/api/v1/cart/items", {"sku": "DAI-SYR-200", "qty": 500}).json()
    line = cart["lines"][0]
    assert 0 < line["qty"] <= 99 and line["qty"] == line["max_qty"] or line["qty"] < 500


def test_csrf_is_required_for_changes(public_client):
    import json

    r = public_client.post("/api/v1/cart/items", json.dumps({"sku": "DAI-KEF-1L", "qty": 1}), content_type="application/json")
    assert r.status_code == 403


def test_zone_check(public_client):
    assert public_client.get("/api/v1/delivery/offers?postcode=1053EC").json()["in_zone"] is True
    out = public_client.get("/api/v1/delivery/offers?postcode=9999ZZ").json()
    assert out["in_zone"] is False and out["slots"] == []


def test_minimum_order_blocks_checkout(public_client):
    fill_cart(public_client, (("DAI-KEF-1L", 2),))
    r = post_json(public_client, "/api/v1/checkout", checkout_body(public_client))
    assert r.status_code == 409 and r.json()["code"] == "below_minimum"


def test_pay_on_delivery_checkout_reserves_stock_and_creates_delivery_lazily(public_client):
    from lozhka_api.domain import stock
    from lozhka_api.catalog.models import Product
    from lozhka_api.sales.models import Delivery, Order

    pid = Product.objects.get(sku="DAI-KEF-1L").id
    before = stock.available([pid])[pid]
    fill_cart(public_client)
    r = post_json(public_client, "/api/v1/checkout", checkout_body(public_client))
    assert r.status_code == 201, r.content
    out = r.json()
    assert out["status"] == "pending_confirmation" and out["pay_url"] is None
    order = Order.objects.get(order_number=out["order_number"])
    assert order.delivery is not None and order.confirm_deadline_at is not None
    assert order.reservations.filter(status="held").count() == 4
    assert stock.available([pid])[pid] == before - 6
    assert order.total_cents == order.subtotal_cents - order.discount_cents + order.delivery_fee_cents
    # the cart is emptied
    assert public_client.get("/api/v1/cart").json()["lines"] == []


def test_online_payment_stub_marks_paid_and_failure_releases_stock(public_client):
    from lozhka_api.sales.models import Order

    fill_cart(public_client)
    out = post_json(public_client, "/api/v1/checkout", checkout_body(public_client, "ideal")).json()
    assert out["status"] == "awaiting_payment" and out["pay_url"]
    r = post_json(public_client, f"/api/v1/payments/test/{out['order_number']}/complete", {"token": out["token"], "result": "success"})
    assert r.json()["status"] == "paid"
    assert Order.objects.get(order_number=out["order_number"]).reservations.filter(status="committed").count() == 4

    fill_cart(public_client)
    out2 = post_json(public_client, "/api/v1/checkout", checkout_body(public_client, "card")).json()
    r2 = post_json(public_client, f"/api/v1/payments/test/{out2['order_number']}/complete", {"token": out2["token"], "result": "fail"})
    assert r2.json()["status"] == "payment_failed"
    assert not Order.objects.get(order_number=out2["order_number"]).reservations.filter(status__in=["held", "committed"]).exists()


def test_guest_needs_the_token_to_see_an_order(public_client):
    fill_cart(public_client)
    out = post_json(public_client, "/api/v1/checkout", checkout_body(public_client)).json()
    assert public_client.get(f"/api/v1/orders/{out['order_number']}").status_code == 404
    assert public_client.get(f"/api/v1/orders/{out['order_number']}?token={out['token']}").status_code == 200


def test_register_login_and_guest_cart_merge(public_client):
    fill_cart(public_client, (("DAI-KEF-1L", 2),))
    r = post_json(public_client, "/api/v1/auth/register", {"email": "newbie@example.com", "password": "longenough1", "first_name": "N"})
    assert r.status_code == 201
    public_client.token = public_client.get("/api/v1/auth/csrf").json()["csrf"]
    assert public_client.get("/api/v1/cart").json()["lines"][0]["qty"] == 2
    assert post_json(public_client, "/api/v1/auth/register", {"email": "newbie@example.com", "password": "longenough1"}).status_code == 409


def test_wrong_password_is_rejected(public_client):
    assert post_json(public_client, "/api/v1/auth/login", {"email": "demo@lozhka.example", "password": "nope"}).status_code == 401
    assert post_json(public_client, "/api/v1/auth/login", {"email": "demo@lozhka.example", "password": "demo1234"}).status_code == 200


def test_staff_cannot_sign_in_on_the_public_api(public_client):
    assert post_json(public_client, "/api/v1/auth/login", {"email": "operator@lozhka.example", "password": "staff1234"}).status_code == 401


def test_delivery_full_blocks_new_orders(public_client):
    from lozhka_api.sales.models import Delivery

    body = checkout_body(public_client)
    fill_cart(public_client)
    first = post_json(public_client, "/api/v1/checkout", body).json()
    from lozhka_api.sales.models import Order

    d = Order.objects.get(order_number=first["order_number"]).delivery
    d.capacity_orders = deliveries.order_count(d)
    d.save(update_fields=["capacity_orders"])
    fill_cart(public_client)
    r = post_json(public_client, "/api/v1/checkout", body)
    assert r.status_code == 409 and r.json()["code"] == "delivery_full"
