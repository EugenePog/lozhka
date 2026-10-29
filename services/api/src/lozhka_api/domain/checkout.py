"""Place an order: one transaction, locks on products and on the delivery (docs 02 s.4.4, s.8)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from lozhka_api.catalog.models import Product
from lozhka_api.customers.models import Cart, ConsentLog, Customer
from lozhka_api.sales.models import DeliveryTemplate, Order, OrderLine, OrderStatusHistory, Payment

from . import deliveries, pricing, stock
from .orders import next_order_number
from .settings_store import get_setting, min_order_cents
from .timeutil import now


class CheckoutError(Exception):
    def __init__(self, code: str, detail: str = "", **extra):
        super().__init__(code)
        self.code, self.detail, self.extra = code, detail, extra


@dataclass
class CheckoutInput:
    cart: Cart
    customer: Customer
    email: str
    phone: str
    first_name: str
    last_name: str
    street: str
    house_number: str
    addition: str
    postcode: str
    city: str
    notes: str
    delivery_choice: str  # asap | time_range
    template_code: str | None
    delivery_date: date | None
    payment_method: str
    language: str
    terms_accepted: bool
    marketing_opt_in: bool = False
    lat: float | None = None
    lng: float | None = None


def cart_items(cart: Cart) -> list[tuple[Product, Decimal]]:
    lines = cart.lines.select_related("product__vat_rate").order_by("added_at", "id")
    return [(ln.product, ln.qty) for ln in lines]


@transaction.atomic
def place_order(data: CheckoutInput) -> Order:
    if not data.terms_accepted:
        raise CheckoutError("terms_required")
    if data.payment_method not in ("ideal", "card", "card_on_delivery"):
        raise CheckoutError("bad_payment_method")
    if data.payment_method == "card_on_delivery" and not get_setting("cod_enabled"):
        raise CheckoutError("cod_disabled")
    items = cart_items(data.cart)
    if not items:
        raise CheckoutError("empty_cart")
    zone = deliveries.zone_for_postcode(data.postcode)
    if zone is None:
        raise CheckoutError("outside_zone", postcode=data.postcode)

    ids = [p.id for p, _ in items]
    stock.lock_products(ids)  # from here on no other checkout can change these products' availability
    avail = stock.available(ids)
    short = []
    for product, qty in items:
        if product.status != "active" or not product.is_orderable:
            short.append({"sku": product.sku, "available": "0"})
        elif avail[product.id] < qty:
            short.append({"sku": product.sku, "available": str(avail[product.id])})
    if short:
        raise CheckoutError("out_of_stock", items=short)

    prices = pricing.current_prices(ids)
    priced = []
    for product, qty in items:
        if product.id not in prices:
            raise CheckoutError("no_price", sku=product.sku)
        priced.append((product, qty, prices[product.id][0]))
    subtotal = sum(pricing.line_total(u, q) for _, q, u in priced)
    if subtotal < min_order_cents():
        raise CheckoutError("below_minimum", minimum=min_order_cents(), subtotal=subtotal)

    promo = pricing.evaluate_promo(data.cart.promo_code, subtotal, data.customer.id)
    if promo.error:
        raise CheckoutError("promo_invalid", detail=promo.error)
    fee = deliveries.fee_for(zone, subtotal - promo.discount_cents)
    totals = pricing.compute_totals(priced, promo.discount_cents, fee)

    # ---- delivery slot -----------------------------------------------------------------------------------------
    at = now()
    offers = deliveries.offers(at)
    if data.delivery_choice == "asap":
        offer = deliveries.asap_offer(offers, at)
    else:
        if not data.template_code or not data.delivery_date:
            raise CheckoutError("delivery_required")
        offer = deliveries.find_offer(offers, data.template_code, data.delivery_date)
    if offer is None:
        raise CheckoutError("no_delivery_available")
    template = DeliveryTemplate.objects.get(pk=offer.occurrence.template.pk)
    delivery, _ = deliveries.get_or_create_delivery(template, offer.occurrence.delivery_date)  # takes the delivery lock
    if not deliveries.can_accept_orders(delivery, at):
        raise CheckoutError("delivery_closed")
    if deliveries.order_count(delivery) >= delivery.capacity_orders:
        raise CheckoutError("delivery_full")

    # ---- order -------------------------------------------------------------------------------------------------
    cod = data.payment_method == "card_on_delivery"
    deadline = None
    if cod:
        deadline = min(at + timedelta(hours=delivery.cod_confirmation_hours), delivery.deliver_starts_at)
    hold_until = deadline if cod else at + timedelta(minutes=int(get_setting("reservation_ttl_min")))
    order = Order.objects.create(
        order_number=next_order_number(), customer=data.customer, status="pending_confirmation" if cod else "awaiting_payment",
        placed_at=at, contact_email=data.email, contact_phone=data.phone,
        ship_first_name=data.first_name, ship_last_name=data.last_name, ship_street=data.street,
        ship_house_number=data.house_number, ship_addition=data.addition,
        ship_postcode=deliveries.normalise_postcode(data.postcode), ship_city=data.city, ship_notes=data.notes,
        ship_lat=data.lat, ship_lng=data.lng, delivery=delivery, delivery_choice=data.delivery_choice,
        payment_method=data.payment_method, confirm_deadline_at=deadline,
        subtotal_cents=totals.subtotal_cents, discount_cents=totals.discount_cents,
        delivery_fee_cents=totals.delivery_fee_cents, total_cents=totals.total_cents,
        vat_9_cents=totals.vat_9_cents, vat_21_cents=totals.vat_21_cents, promo_code=promo.code,
        language=data.language, terms_accepted_at=at,
    )
    OrderLine.objects.bulk_create([
        OrderLine(order=order, product=ln["product"], name_snapshot=_name(ln["product"], data.language),
                  storage_type_snapshot=ln["product"].storage_type, unit_price_cents=ln["unit"], qty=ln["qty"],
                  vat_rate_pct=ln["rate"], line_total_cents=ln["total"])
        for ln in totals.lines
    ])
    stock.reserve(order, [(ln["product"].id, ln["qty"]) for ln in totals.lines], hold_until)
    Payment.objects.create(order=order, provider="terminal" if cod else "test", method=data.payment_method,
                           status="pending", amount_cents=totals.total_cents)
    OrderStatusHistory.objects.create(order=order, status=order.status, actor="customer")
    ConsentLog.objects.create(customer=data.customer, kind="terms", version="1", granted=True)
    if data.marketing_opt_in:
        ConsentLog.objects.create(customer=data.customer, kind="marketing", version="1", granted=True)
    data.cart.lines.all().delete()
    data.cart.promo_code = ""
    data.cart.save(update_fields=["promo_code", "updated_at"])
    return order


def _name(product: Product, lang: str) -> str:
    tr = {t.lang: t.name for t in product.translations.all()}
    return tr.get(lang) or tr.get("en") or tr.get("nl") or product.sku
