
from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.http import Http404
from ninja import Router
from ninja.errors import HttpError

from lozhka_api.catalog.models import Product
from lozhka_api.domain import pricing, stock
from lozhka_api.domain.settings_store import min_order_cents

from ..deps import fetch_all, get_cart, lang_of, public_auth
from ..schemas import CartItemIn, CartOut, PromoIn, QtyIn

router = Router(tags=["cart"], auth=public_auth)


def cart_out(cart, lang: str = "nl") -> dict:
    lines_out: list[dict] = []
    subtotal = 0
    if cart is not None:
        lines = list(cart.lines.select_related("product"))
        ids = [ln.product_id for ln in lines]
        avail = stock.available(ids)
        prices = pricing.current_prices(ids)
        info = {r["sku"]: r for r in fetch_all(
            "select sku, slug, name, unit_label, stock_status, (images -> 0 ->> 'key') as image "
            "from gold.storefront_product where lang = %s and product_id = any(%s)", [lang, ids])} if ids else {}
        for ln in lines:
            p = ln.product
            meta = info.get(p.sku)
            price = prices.get(p.id)
            problem = None
            if meta is None or price is None or not p.is_orderable:
                problem = "unavailable"
            elif avail[p.id] <= 0:
                problem = "out_of_stock"
            elif avail[p.id] < ln.qty:
                problem = "reduced"
            unit = price[0] if price else 0
            total = pricing.line_total(unit, ln.qty)
            if problem not in ("unavailable", "out_of_stock"):
                subtotal += total
            lines_out.append({
                "sku": p.sku, "slug": meta["slug"] if meta else p.slug, "name": meta["name"] if meta else p.sku,
                "unit_label": meta["unit_label"] if meta else None, "qty": float(ln.qty), "unit_price_cents": unit,
                "line_total_cents": total, "stock_status": meta["stock_status"] if meta else "out_of_stock",
                "max_qty": int(min(avail[p.id], 99)), "image": meta["image"] if meta else None,
                "is_discounted": bool(price and price[1]), "problem": problem})
    promo = pricing.evaluate_promo(cart.promo_code, subtotal) if cart is not None and cart.promo_code else pricing.PromoResult()
    minimum = min_order_cents()
    net = subtotal - promo.discount_cents
    return {
        "lines": lines_out, "item_count": int(sum(ln["qty"] for ln in lines_out)), "subtotal_cents": subtotal,
        "discount_cents": promo.discount_cents, "promo_code": promo.code, "promo_error": promo.error,
        "min_order_cents": minimum, "shortfall_cents": max(0, minimum - net), "free_delivery_hint_cents": max(0, 10000 - net) or None,
    }


def clamp(product: Product, qty: Decimal) -> tuple[Decimal, bool]:
    """Whole numbers for piece products; never more than is available."""
    qty = qty.quantize(Decimal("1"), rounding=ROUND_DOWN) if product.unit_type == "piece" else qty.quantize(Decimal("0.001"))
    available = stock.available([product.id])[product.id]
    if qty > available:
        return available.quantize(Decimal("1"), rounding=ROUND_DOWN) if product.unit_type == "piece" else available, True
    return qty, False


@router.get("/cart", response=CartOut, summary="Current cart")
def get_cart_view(request, lang: str = "nl"):
    return cart_out(get_cart(request), lang_of(lang))


@router.post("/cart/items", response=CartOut, summary="Add to cart (adds to the quantity already there)")
@transaction.atomic
def add_item(request, body: CartItemIn, lang: str = "nl"):
    product = Product.objects.filter(sku=body.sku, status="active", is_orderable=True).first()
    if product is None:
        raise Http404()
    if body.qty <= 0:
        raise HttpError(422, "qty_positive")
    cart = get_cart(request, create=True)
    line = cart.lines.filter(product=product).first()
    wanted = Decimal(str(body.qty)) + (line.qty if line else 0)
    qty, clipped = clamp(product, wanted)
    if qty <= 0:
        raise HttpError(409, "out_of_stock")
    if line:
        line.qty = qty
        line.save(update_fields=["qty"])
    else:
        cart.lines.create(product=product, qty=qty)
    cart.save(update_fields=["updated_at"])
    return cart_out(cart, lang_of(lang))


@router.put("/cart/items/{sku}", response=CartOut, summary="Set the quantity (0 removes the line)")
@transaction.atomic
def set_item(request, sku: str, body: QtyIn, lang: str = "nl"):
    cart = get_cart(request, create=True)
    line = cart.lines.filter(product__sku=sku).select_related("product").first()
    if body.qty <= 0:
        if line:
            line.delete()
        return cart_out(cart, lang_of(lang))
    product = line.product if line else Product.objects.filter(sku=sku, status="active", is_orderable=True).first()
    if product is None:
        raise Http404()
    qty, _ = clamp(product, Decimal(str(body.qty)))
    if qty <= 0:
        raise HttpError(409, "out_of_stock")
    if line:
        line.qty = qty
        line.save(update_fields=["qty"])
    else:
        cart.lines.create(product=product, qty=qty)
    return cart_out(cart, lang_of(lang))


@router.delete("/cart/items/{sku}", response=CartOut, summary="Remove a line")
def remove_item(request, sku: str, lang: str = "nl"):
    cart = get_cart(request)
    if cart:
        cart.lines.filter(product__sku=sku).delete()
    return cart_out(cart, lang_of(lang))


@router.post("/cart/promo", response=CartOut, summary="Apply or clear a promo code")
def apply_promo(request, body: PromoIn, lang: str = "nl"):
    cart = get_cart(request, create=True)
    code = body.code.strip()
    cart.promo_code = ""
    error = ""
    if code:
        error = pricing.evaluate_promo(code, cart_out(cart)["subtotal_cents"], cart.customer_id).error
        if not error or error == "min_order":  # a code that only misses the minimum stays on the cart
            cart.promo_code = code
    cart.save(update_fields=["promo_code", "updated_at"])
    out = cart_out(cart, lang_of(lang))
    if error and not out["promo_error"]:
        out["promo_error"], out["promo_code"] = error, code
    return out
