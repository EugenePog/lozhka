from __future__ import annotations

import math
from typing import Optional

from django.http import Http404
from ninja import Query, Router, Schema

from lozhka_api.catalog.models import Product
from lozhka_api.core.models import ContentBlock
from lozhka_api.customers.models import Customer, Favourite, NewsletterSubscription, StockNotifyRequest
from lozhka_api.domain.settings_store import get_setting, min_order_cents

from ..deps import customer_of, fetch_all, lang_of, public_auth
from ..schemas import CategoryOut, ContentOut, HomeOut, NotifyIn, ProductCard, ProductDetail, ProductList

router = Router(tags=["catalogue"], auth=public_auth)

CARD_COLS = """sku, slug, name, brand, unit_label, price_cents, regular_cents, is_discounted, unit_price_cents,
 unit_price_per, tags, stock_status, available_qty, category_slug, (images -> 0 ->> 'key') as image"""


def card(row: dict, favourites: set[str] | None = None) -> dict:
    avail = row.pop("available_qty", 0) or 0
    row["max_qty"] = int(min(avail, 99))
    row["tags"] = list(row.get("tags") or [])
    row["is_favourite"] = bool(favourites and row["sku"] in favourites)
    return row


def favourite_skus(request) -> set[str]:
    customer = customer_of(request)
    if customer is None:
        return set()
    return set(Favourite.objects.filter(customer=customer).values_list("product__sku", flat=True))


@router.get("/categories", response=list[CategoryOut], summary="Category tree")
def categories(request, lang: str = "nl"):
    rows = fetch_all(
        "select slug, parent_slug, name, kind, product_count, sort from gold.storefront_category "
        "where lang = %s and is_visible order by sort, slug", [lang_of(lang)])
    return build_tree(rows)


def build_tree(rows: list[dict]) -> list[dict]:
    nodes = {r["slug"]: {**r, "children": []} for r in rows}
    roots = []
    for r in rows:
        node = nodes[r["slug"]]
        parent = nodes.get(r["parent_slug"]) if r["parent_slug"] else None
        (parent["children"] if parent else roots).append(node)
    return roots


SORTS = {
    "relevance": "rank desc, name",
    "price_asc": "price_cents asc, name",
    "price_desc": "price_cents desc, name",
    "name": "name",
    "new": "created_at desc",
}


class ProductQuery(Schema):
    category: Optional[str] = None
    q: Optional[str] = None
    offers: bool = False
    tag: Optional[str] = None
    in_stock: bool = False
    sort: str = "relevance"
    page: int = 1
    page_size: int = 24
    lang: str = "nl"


@router.get("/products", response=ProductList, summary="Browse and search products")
def products(request, params: ProductQuery = Query(...)):
    lang = lang_of(params.lang)
    where, args = ["lang = %s"], [lang]
    rank = "0"
    if params.category:
        where.append("""(category_slug = %s or exists (select 1 from jsonb_array_elements(category_path) e where e ->> 'slug' = %s))""")
        args += [params.category, params.category]
    if params.offers:
        where.append("is_discounted")
    if params.tag:
        where.append("%s = any(tags)")
        args.append(params.tag)
    if params.in_stock:
        where.append("stock_status <> 'out_of_stock'")
    if params.q and params.q.strip():
        tokens = [t for t in params.q.lower().split() if t][:6]
        for t in tokens:
            where.append("search_text like '%%' || lower(unaccent(%s)) || '%%'")
            args.append(t)
        rank = "(case when lower(unaccent(name)) like lower(unaccent(%s)) || '%%' then 2 else 0 end + case when sku ilike %s then 3 else 0 end)"
        rank_args = [tokens[0], params.q.strip()] if tokens else [params.q, params.q]
    else:
        rank_args = []
    order = SORTS.get(params.sort, SORTS["relevance"])
    page = max(1, params.page)
    size = min(max(1, params.page_size), 60)
    clause = " and ".join(where)
    total = fetch_all(f"select count(*) as n from gold.storefront_product where {clause}", args)[0]["n"]
    rows = fetch_all(
        f"select {CARD_COLS}, created_at, {rank} as rank from gold.storefront_product where {clause} "
        f"order by {order} limit %s offset %s",
        [*rank_args, *args, size, (page - 1) * size],
    )
    favs = favourite_skus(request)
    return {"items": [card(r) | {"is_favourite": r["sku"] in favs} for r in rows], "total": total,
            "page": page, "pages": max(1, math.ceil(total / size))}


@router.get("/products/suggest", response=list[dict], summary="Search-as-you-type")
def suggest(request, q: str, lang: str = "nl"):
    q = q.strip()
    if len(q) < 2:
        return []
    return fetch_all(
        "select sku, slug, name, price_cents, (images -> 0 ->> 'key') as image from gold.storefront_product "
        "where lang = %s and search_text like '%%' || lower(unaccent(%s)) || '%%' order by "
        "(lower(unaccent(name)) like lower(unaccent(%s)) || '%%') desc, name limit 6", [lang_of(lang), q, q])


@router.get("/products/{slug}", response=ProductDetail, summary="Product page")
def product(request, slug: str, lang: str = "nl"):
    rows = fetch_all("select * from gold.storefront_product where lang = %s and slug = %s", [lang_of(lang), slug])
    if not rows:
        raise Http404()
    row = rows[0]
    related = fetch_all(
        f"select {CARD_COLS} from gold.storefront_product where lang = %s and category_slug = %s and sku <> %s "
        "and stock_status <> 'out_of_stock' order by random() limit 4", [lang_of(lang), row["category_slug"], row["sku"]])
    favs = favourite_skus(request)
    detail = card(fetch_all(f"select {CARD_COLS} from gold.storefront_product where lang = %s and slug = %s", [lang_of(lang), slug])[0], favs)
    detail.update(
        short_description=row["short_description"], description=row["description"], ingredients=row["ingredients"],
        storage_instructions=row["storage_instructions"], country_of_origin=row["country_of_origin"],
        storage_type=row["storage_type"], category_path=row["category_path"] or [], images=row["images"],
        allergens=row["allergens"], nutrition=row["nutrition"], vat_rate_pct=float(row["vat_rate_pct"]),
        related=[card(r, favs) for r in related])
    return detail


@router.post("/products/{sku}/notify", response={204: None}, summary="Tell me when it is back")
def notify(request, sku: str, body: NotifyIn):
    product = Product.objects.filter(sku=sku).first()
    if product is None:
        raise Http404()
    customer = customer_of(request)
    email = body.email or (customer.email if customer else "")
    if not email:
        from ninja.errors import HttpError

        raise HttpError(422, "email_required")
    StockNotifyRequest.objects.get_or_create(product=product, email=email, notified_at=None,
                                             defaults={"customer": customer, "lang": lang_of(body.lang)})
    return 204, None


@router.post("/newsletter", response={204: None}, summary="Subscribe to the offers e-mail")
def newsletter(request, body: NotifyIn):
    from ninja.errors import HttpError

    if "@" not in body.email:
        raise HttpError(422, "email_invalid")
    NewsletterSubscription.objects.get_or_create(email=body.email.strip().lower(), defaults={"lang": lang_of(body.lang)})
    return 204, None


@router.get("/home", response=HomeOut, summary="Home page data")
def home(request, lang: str = "nl"):
    lang = lang_of(lang)
    favs = favourite_skus(request)

    def cards(where: str, order: str = "name", limit: int = 8) -> list[dict]:
        rows = fetch_all(f"select {CARD_COLS} from gold.storefront_product where lang = %s and {where} order by {order} limit {limit}", [lang])
        return [card(r, favs) for r in rows]

    blocks = list(ContentBlock.objects.filter(lang=lang, published=True, kind__in=["hero", "usp"]).order_by("sort"))
    to_out = lambda b: {"slug": b.slug, "kind": b.kind, "title": b.title, "body_markdown": b.body_markdown}  # noqa: E731
    return {
        "hero": next((to_out(b) for b in blocks if b.kind == "hero"), None),
        "usps": [to_out(b) for b in blocks if b.kind == "usp"],
        "categories": categories(request, lang),
        "bestsellers": cards("'bestseller' = any(tags)"),
        "new_items": cards("'new' = any(tags)", "created_at desc"),
        "offers": cards("is_discounted", "name"),
        "settings": public_settings(),
    }


def public_settings() -> dict:
    return {
        "min_order_cents": min_order_cents(),
        "cod_enabled": bool(get_setting("cod_enabled")),
        "shop_name": get_setting("shop_name", "Lozhka"),
        "support_email": get_setting("support_email", ""),
        "support_phone": get_setting("support_phone", ""),
        "delivery_horizon_days": int(get_setting("delivery_horizon_days")),
    }


@router.get("/settings", response=dict, summary="Public settings")
def settings_view(request):
    return public_settings()


@router.get("/pages/{slug}", response=ContentOut, summary="Help and legal pages")
def page(request, slug: str, lang: str = "nl"):
    block = (ContentBlock.objects.filter(slug=slug, lang=lang_of(lang), published=True).first()
             or ContentBlock.objects.filter(slug=slug, lang="en", published=True).first())
    if block is None:
        raise Http404()
    return {"slug": block.slug, "kind": block.kind, "title": block.title, "body_markdown": block.body_markdown}
