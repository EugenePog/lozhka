from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from ninja import Schema


class Problem(Schema):
    code: str
    detail: str = ""
    extra: dict[str, Any] = {}


class ProductCard(Schema):
    sku: str
    slug: str
    name: str
    brand: Optional[str] = None
    unit_label: Optional[str] = None
    price_cents: int
    regular_cents: Optional[int] = None
    is_discounted: bool = False
    unit_price_cents: Optional[int] = None
    unit_price_per: Optional[str] = None
    tags: list[str] = []
    stock_status: str = "in_stock"
    max_qty: int = 0
    image: Optional[str] = None
    category_slug: str = ""
    is_favourite: bool = False


class ProductList(Schema):
    items: list[ProductCard]
    total: int
    page: int
    pages: int


class ProductDetail(ProductCard):
    short_description: str = ""
    description: str = ""
    ingredients: str = ""
    storage_instructions: str = ""
    country_of_origin: str = ""
    storage_type: str = "ambient"
    category_path: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    allergens: list[dict[str, Any]] = []
    nutrition: Optional[dict[str, Any]] = None
    vat_rate_pct: float = 9
    related: list[ProductCard] = []


class CategoryOut(Schema):
    slug: str
    name: str
    parent_slug: Optional[str] = None
    kind: str = "regular"
    product_count: int = 0
    children: list["CategoryOut"] = []


class CartLineOut(Schema):
    sku: str
    slug: str
    name: str
    unit_label: Optional[str] = None
    qty: float
    unit_price_cents: int
    line_total_cents: int
    stock_status: str
    max_qty: int
    image: Optional[str] = None
    is_discounted: bool = False
    problem: Optional[str] = None  # out_of_stock | reduced | unavailable


class CartOut(Schema):
    lines: list[CartLineOut]
    item_count: int
    subtotal_cents: int
    discount_cents: int
    promo_code: str = ""
    promo_error: str = ""
    min_order_cents: int
    shortfall_cents: int
    free_delivery_hint_cents: Optional[int] = None


class CartItemIn(Schema):
    sku: str
    qty: float = 1


class QtyIn(Schema):
    qty: float


class PromoIn(Schema):
    code: str = ""


class SlotOut(Schema):
    template_code: str
    name: str
    delivery_date: date
    deliver_from: str
    deliver_to: str
    deliver_starts_at: datetime
    order_by: datetime  # end of the collection range: last moment to order for this slot
    orders_left: int
    is_full: bool


class FeeTierOut(Schema):
    min_subtotal_cents: int
    max_subtotal_cents: Optional[int] = None
    fee_cents: int


class DeliveryOffersOut(Schema):
    postcode: str
    in_zone: bool
    zone: Optional[str] = None
    fee_tiers: list[FeeTierOut] = []
    asap: Optional[SlotOut] = None
    slots: list[SlotOut] = []


class AddressIn(Schema):
    label: str = ""
    first_name: str
    last_name: str
    street: str
    house_number: str
    addition: str = ""
    postcode: str
    city: str
    delivery_notes: str = ""
    is_default: bool = False


class AddressOut(AddressIn):
    id: int


class CheckoutIn(Schema):
    email: str
    phone: str = ""
    first_name: str
    last_name: str
    street: str
    house_number: str
    addition: str = ""
    postcode: str
    city: str
    notes: str = ""
    delivery_choice: str = "time_range"  # asap | time_range
    template_code: Optional[str] = None
    delivery_date: Optional[date] = None
    payment_method: str
    terms_accepted: bool = False
    marketing_opt_in: bool = False
    save_address: bool = False
    language: str = "nl"


class OrderLineOut(Schema):
    sku: str
    name: str
    qty: float
    unit_price_cents: int
    line_total_cents: int
    image: Optional[str] = None


class HistoryOut(Schema):
    status: str
    at: datetime


class OrderOut(Schema):
    order_number: str
    token: str
    status: str
    placed_at: datetime
    payment_method: str
    subtotal_cents: int
    discount_cents: int
    delivery_fee_cents: int
    total_cents: int
    vat_9_cents: int
    vat_21_cents: int
    promo_code: str = ""
    contact_email: str
    ship_name: str
    ship_address: str
    ship_postcode: str
    ship_city: str
    ship_notes: str = ""
    delivery_window_from: Optional[datetime] = None
    delivery_window_to: Optional[datetime] = None
    confirm_deadline_at: Optional[datetime] = None
    can_cancel: bool = False
    lines: list[OrderLineOut]
    history: list[HistoryOut]


class OrderSummary(Schema):
    order_number: str
    status: str
    placed_at: datetime
    total_cents: int
    item_count: int
    delivery_window_from: Optional[datetime] = None
    delivery_window_to: Optional[datetime] = None


class PlacedOut(Schema):
    order_number: str
    token: str
    status: str
    payment_method: str
    total_cents: int
    pay_url: Optional[str] = None  # online payment page, absent for pay on delivery


class RegisterIn(Schema):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    language: str = "nl"
    marketing_opt_in: bool = False


class LoginIn(Schema):
    email: str
    password: str


class MeOut(Schema):
    email: str
    first_name: str
    last_name: str
    phone: str
    language: str


class MeIn(Schema):
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    language: str = "nl"


class NotifyIn(Schema):
    email: str = ""
    lang: str = "nl"


class PayResultIn(Schema):
    token: str
    result: str  # success | fail


class ContentOut(Schema):
    slug: str
    kind: str
    title: str
    body_markdown: str


class HomeOut(Schema):
    hero: Optional[ContentOut] = None
    usps: list[ContentOut] = []
    categories: list[CategoryOut] = []
    bestsellers: list[ProductCard] = []
    new_items: list[ProductCard] = []
    offers: list[ProductCard] = []
    settings: dict[str, Any] = {}
