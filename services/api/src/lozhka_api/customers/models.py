"""Customers, carts and engagement (docs 02 sections 4.2 and 4.3, area d).

Personal data lives in a few tables (docs 02 section 10): customer, customer_address,
consent_log, newsletter_subscription and the address snapshot on the order.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from lozhka_api.catalog.models import Product
from lozhka_api.core.models import LANGS


class Customer(models.Model):
    """Guests get a row too, so orders always have a customer. Natural key (registered): email."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField()
    email_verified_at = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    language = models.CharField(max_length=2, choices=LANGS, default="nl")
    is_guest = models.BooleanField(default=False)
    auth_user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer"
        constraints = [
            models.UniqueConstraint(
                Lower("email"), condition=models.Q(is_guest=False), name="customer_registered_email_uniq"
            ),
        ]

    def __str__(self) -> str:
        return self.email


class CustomerAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=60, blank=True, default="")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    street = models.CharField(max_length=160)
    house_number = models.CharField(max_length=20)
    addition = models.CharField(max_length=20, blank=True, default="")
    postcode = models.CharField(max_length=7)  # "1234 AB"
    city = models.CharField(max_length=100)
    delivery_notes = models.CharField(max_length=300, blank=True, default="")
    is_default = models.BooleanField(default=False)
    bag_id = models.CharField(max_length=20, blank=True, default="")
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "customer_address"


class Favourite(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="favourites")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favourite"
        constraints = [models.UniqueConstraint(fields=["customer", "product"], name="favourite_uniq")]


class ConsentLog(models.Model):
    KINDS = [("terms", "terms"), ("privacy", "privacy"), ("marketing", "marketing"), ("cookies", "cookies")]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=10, choices=KINDS)
    version = models.CharField(max_length=20, blank=True, default="")
    granted = models.BooleanField()
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "consent_log"


class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)
    lang = models.CharField(max_length=2, choices=LANGS, default="nl")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "newsletter_subscription"


class Cart(models.Model):
    """Server-side cart so web and app share it. Carts do NOT reserve stock."""

    customer = models.OneToOneField(Customer, null=True, blank=True, on_delete=models.CASCADE, related_name="cart")
    session_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    promo_code = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(customer__isnull=False) | models.Q(session_token__isnull=False),
                name="cart_owner_chk",
            )
        ]


class CartLine(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_line"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="cart_line_uniq"),
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="cart_line_qty_chk"),
        ]
        ordering = ["added_at", "id"]


class StockNotifyRequest(models.Model):
    """The 'Notify me' button on out-of-stock items."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, default="")
    lang = models.CharField(max_length=2, choices=LANGS, default="nl")
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_notify_request"
