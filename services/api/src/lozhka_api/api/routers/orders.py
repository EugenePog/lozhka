from __future__ import annotations

import uuid
from typing import Optional

from django.http import Http404
from ninja import Router
from ninja.errors import HttpError

from lozhka_api.catalog.models import Product
from lozhka_api.customers.models import Customer, CustomerAddress
from lozhka_api.domain import checkout as co
from lozhka_api.domain import deliveries, orders as order_svc
from lozhka_api.sales.models import Order

from ..deps import customer_auth, customer_of, get_cart, lang_of, public_auth
from ..schemas import CheckoutIn, OrderOut, OrderSummary, PayResultIn, PlacedOut

router = Router(tags=["orders"], auth=public_auth)
member = Router(tags=["orders"], auth=customer_auth)

CANCELLABLE = ["awaiting_payment", "pending_confirmation", "paid", "confirmed"]


def order_out(order: Order) -> dict:
    images = dict(Product.objects.filter(id__in=order.lines.values("product_id")).values_list("id", "sku"))
    delivery = order.delivery
    return {
        "order_number": order.order_number, "token": str(order.public_token), "status": order.status,
        "placed_at": order.placed_at, "payment_method": order.payment_method, "subtotal_cents": order.subtotal_cents,
        "discount_cents": order.discount_cents, "delivery_fee_cents": order.delivery_fee_cents,
        "total_cents": order.total_cents, "vat_9_cents": order.vat_9_cents, "vat_21_cents": order.vat_21_cents,
        "promo_code": order.promo_code, "contact_email": order.contact_email,
        "ship_name": f"{order.ship_first_name} {order.ship_last_name}",
        "ship_address": f"{order.ship_street} {order.ship_house_number}{(' ' + order.ship_addition) if order.ship_addition else ''}",
        "ship_postcode": order.ship_postcode, "ship_city": order.ship_city, "ship_notes": order.ship_notes,
        "delivery_window_from": delivery.deliver_starts_at if delivery else None,
        "delivery_window_to": delivery.deliver_ends_at if delivery else None,
        "confirm_deadline_at": order.confirm_deadline_at if order.status == "pending_confirmation" else None,
        "can_cancel": order.status in CANCELLABLE and (delivery is None or delivery.status == "open"),
        "lines": [{"sku": images.get(ln.product_id, ""), "name": ln.name_snapshot, "qty": float(ln.qty),
                   "unit_price_cents": ln.unit_price_cents, "line_total_cents": ln.line_total_cents, "image": None}
                  for ln in order.lines.all()],
        "history": [{"status": h.status, "at": h.at} for h in order.history.all()],
    }


def load_order(request, number: str, token: Optional[str]) -> Order:
    order = Order.objects.select_related("delivery", "customer").filter(order_number=number).first()
    if order is None:
        raise Http404()
    customer = customer_of(request)
    owner = customer is not None and order.customer_id == customer.id
    try:
        by_token = token is not None and uuid.UUID(token) == order.public_token
    except ValueError:
        by_token = False
    if not (owner or by_token):
        raise Http404()
    return order


@router.post("/checkout", response={201: PlacedOut, 409: dict, 422: dict}, summary="Place the order")
def place(request, body: CheckoutIn):
    cart = get_cart(request)
    if cart is None:
        return 409, {"code": "empty_cart", "detail": "", "extra": {}}
    customer = customer_of(request)
    if customer is None:
        if "@" not in body.email:
            return 422, {"code": "email_invalid", "detail": "", "extra": {}}
        customer = Customer.objects.create(email=body.email.strip().lower(), first_name=body.first_name,
                                           last_name=body.last_name, phone=body.phone, is_guest=True,
                                           language=lang_of(body.language))
    elif body.phone and not customer.phone:
        customer.phone = body.phone
        customer.save(update_fields=["phone"])
    try:
        order = co.place_order(co.CheckoutInput(
            cart=cart, customer=customer, email=body.email.strip().lower(), phone=body.phone, first_name=body.first_name,
            last_name=body.last_name, street=body.street, house_number=body.house_number, addition=body.addition,
            postcode=body.postcode, city=body.city, notes=body.notes, delivery_choice=body.delivery_choice,
            template_code=body.template_code, delivery_date=body.delivery_date, payment_method=body.payment_method,
            language=lang_of(body.language), terms_accepted=body.terms_accepted, marketing_opt_in=body.marketing_opt_in))
    except co.CheckoutError as exc:
        return 409, {"code": exc.code, "detail": exc.detail, "extra": exc.extra}
    if body.save_address and not customer.is_guest:
        CustomerAddress.objects.get_or_create(
            customer=customer, street=body.street, house_number=body.house_number, postcode=deliveries.normalise_postcode(body.postcode),
            defaults={"first_name": body.first_name, "last_name": body.last_name, "addition": body.addition, "city": body.city,
                      "delivery_notes": body.notes, "is_default": not customer.addresses.exists()})
    pay_url = None if order.payment_method == "card_on_delivery" else f"/pay/test/{order.order_number}?token={order.public_token}"
    return 201, {"order_number": order.order_number, "token": str(order.public_token), "status": order.status,
                 "payment_method": order.payment_method, "total_cents": order.total_cents, "pay_url": pay_url}


@router.get("/orders/{number}", response=OrderOut, summary="Order confirmation / tracking (guest: token)")
def order_detail(request, number: str, token: Optional[str] = None):
    return order_out(load_order(request, number, token))


@router.post("/orders/{number}/cancel", response=OrderOut, summary="Customer cancels while the delivery is still open")
def cancel(request, number: str, token: Optional[str] = None):
    order = load_order(request, number, token)
    try:
        order = order_svc.cancel_order(order, reason="customer", actor="customer")
    except order_svc.TransitionError as exc:
        raise HttpError(409, str(exc)) from exc
    order.refresh_from_db()
    return order_out(order)


@router.post("/payments/test/{number}/complete", response=OrderOut,
             summary="STUB payment page result (iDEAL/card provider replaces this later)")
def pay_test(request, number: str, body: PayResultIn):
    order = load_order(request, number, body.token)
    try:
        if body.result == "success":
            order_svc.mark_paid(order, provider_payment_id=f"test_{uuid.uuid4().hex[:12]}")
        else:
            order_svc.mark_payment_failed(order, reason="test_failed")
    except order_svc.TransitionError as exc:
        raise HttpError(409, str(exc)) from exc
    order.refresh_from_db()
    return order_out(order)


@member.get("/me/orders", response=list[OrderSummary], summary="My orders")
def my_orders(request):
    customer = customer_of(request)
    result = []
    for o in order_svc.customer_orders(customer):
        result.append({"order_number": o.order_number, "status": o.status, "placed_at": o.placed_at, "total_cents": o.total_cents,
                       "item_count": int(sum(ln.qty for ln in o.lines.all())),
                       "delivery_window_from": o.delivery.deliver_starts_at if o.delivery else None,
                       "delivery_window_to": o.delivery.deliver_ends_at if o.delivery else None})
    return result
