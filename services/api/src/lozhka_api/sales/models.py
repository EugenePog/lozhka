"""Orders, payments, reservations and deliveries (docs 02 sections 4.3 and 4.4, areas d and e).

Natural keys: order.order_number, delivery_zone.name, delivery_template.code, vehicle.name,
return_reason.code, delivery (template code, delivery_date).
"""
import uuid

from django.conf import settings
from django.db import models

from lozhka_api.catalog.models import Product
from lozhka_api.core.models import LANGS
from lozhka_api.customers.models import Customer
from lozhka_api.procurement.models import ReceivingLine

User = settings.AUTH_USER_MODEL

# ---- delivery configuration -----------------------------------------------------------------------------------


class DeliveryZone(models.Model):
    """Where you deliver. 'We do not deliver to this postcode yet' comes from here."""

    name = models.CharField(max_length=120, unique=True)
    postcode4_ranges = models.JSONField(default=list)  # ["1000-1299", "2000-2999"]
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "delivery_zone"

    def __str__(self) -> str:
        return self.name


class DeliveryTemplate(models.Model):
    """One delivery that can happen on any day. The collection ranges of all ACTIVE templates must cover
    the 24 hours exactly (database constraint trigger, db/scripts/constraints_after_app.sql)."""

    code = models.CharField(max_length=10, unique=True)  # used in the delivery number, e.g. A, B
    name = models.CharField(max_length=80, unique=True)
    collect_from = models.TimeField()
    collect_to = models.TimeField()
    deliver_from = models.TimeField()
    deliver_to = models.TimeField()
    capacity_orders = models.PositiveIntegerField(default=20)
    cod_confirmation_hours = models.PositiveIntegerField(default=4)
    sort = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "delivery_template"
        ordering = ["sort", "collect_from"]
        constraints = [models.CheckConstraint(condition=models.Q(capacity_orders__gt=0), name="delivery_template_capacity_chk")]

    def __str__(self) -> str:
        return self.name


class DeliveryFeeTier(models.Model):
    """The fee table on W09. max_subtotal_cents empty = no upper limit."""

    zone = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE, related_name="fee_tiers")
    min_subtotal_cents = models.PositiveIntegerField()
    max_subtotal_cents = models.PositiveIntegerField(null=True, blank=True)
    fee_cents = models.PositiveIntegerField()

    class Meta:
        db_table = "delivery_fee_tier"
        ordering = ["zone", "min_subtotal_cents"]
        constraints = [models.UniqueConstraint(fields=["zone", "min_subtotal_cents"], name="delivery_fee_tier_uniq")]


class Vehicle(models.Model):
    name = models.CharField(max_length=80, unique=True)
    plate = models.CharField(max_length=20, blank=True, default="")
    capacity_orders = models.PositiveIntegerField(default=20)
    capacity_volume_l = models.PositiveIntegerField(null=True, blank=True)
    capacity_kg = models.PositiveIntegerField(null=True, blank=True)
    has_cooling = models.BooleanField(default=False)
    fuel_type = models.CharField(max_length=20, blank=True, default="diesel")
    consumption_l_per_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "vehicle"

    def __str__(self) -> str:
        return self.name


class Driver(models.Model):
    """Added to the design: there is no driver role yet (docs 07 Q19c), so drivers are plain records
    that an operator picks. Link to a staff account later."""

    name = models.CharField(max_length=120, unique=True)
    phone = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "driver"

    def __str__(self) -> str:
        return self.name


class Depot(models.Model):
    name = models.CharField(max_length=120, unique=True)
    street = models.CharField(max_length=160, blank=True, default="")
    house_number = models.CharField(max_length=20, blank=True, default="")
    postcode = models.CharField(max_length=7, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "depot"


class ReturnReason(models.Model):
    """List used when a delivery is closed (admin edits). restock=False means written off."""

    code = models.CharField(max_length=40, unique=True)
    restock = models.BooleanField(default=True)
    flags_customer = models.BooleanField(default=False)  # refusal reasons
    sort = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "return_reason"
        ordering = ["sort", "code"]

    def __str__(self) -> str:
        return self.code


class ReturnReasonTranslation(models.Model):
    reason = models.ForeignKey(ReturnReason, on_delete=models.CASCADE, related_name="translations")
    lang = models.CharField(max_length=2, choices=LANGS)
    name = models.CharField(max_length=160)

    class Meta:
        db_table = "return_reason_translation"
        constraints = [models.UniqueConstraint(fields=["reason", "lang"], name="return_reason_translation_uniq")]


# ---- deliveries -------------------------------------------------------------------------------------------------


class Delivery(models.Model):
    """One delivery = many orders, one vehicle. Created when the first order for a template and date arrives
    (values copied from the template), deleted when it has no orders left."""

    STATUS = [(s, s) for s in ("open", "closed", "approved", "out_for_delivery", "completed")]
    delivery_number = models.CharField(max_length=30, db_index=True)  # D-1027-A
    delivery_date = models.DateField()
    template = models.ForeignKey(DeliveryTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="deliveries")
    template_code = models.CharField(max_length=10)
    template_name = models.CharField(max_length=80)
    collect_from = models.TimeField()
    collect_to = models.TimeField()
    deliver_from = models.TimeField()
    deliver_to = models.TimeField()
    capacity_orders = models.PositiveIntegerField()
    cod_confirmation_hours = models.PositiveIntegerField()
    collect_starts_at = models.DateTimeField()
    collect_ends_at = models.DateTimeField()
    deliver_starts_at = models.DateTimeField()
    deliver_ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS, default="open")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL)
    driver = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.SET_NULL)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    distance_m = models.PositiveIntegerField(null=True, blank=True)
    duration_s = models.PositiveIntegerField(null=True, blank=True)
    fuel_l_estimate = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    cost_cents_estimate = models.PositiveIntegerField(null=True, blank=True)
    algorithm_version = models.CharField(max_length=40, blank=True, default="")
    parameters = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "delivery"
        ordering = ["delivery_date", "deliver_from"]
        constraints = [
            models.UniqueConstraint(fields=["template", "delivery_date"], name="delivery_template_date_uniq"),
            models.CheckConstraint(
                condition=models.Q(status__in=["open", "closed", "approved", "out_for_delivery", "completed"]),
                name="delivery_status_chk",
            ),
        ]

    def __str__(self) -> str:
        return self.delivery_number


# ---- orders ------------------------------------------------------------------------------------------------------

ORDER_STATUSES = [
    "awaiting_payment", "paid", "pending_confirmation", "confirmed", "picking", "packed",
    "out_for_delivery", "delivered", "payment_failed", "cancelled", "delivery_failed", "refunded",
]
READY_STATUSES = ["paid", "confirmed"]  # "ready for delivery"
CAPACITY_EXCLUDED = ["cancelled", "payment_failed"]


class Order(models.Model):
    """Address and contact are copied into the order so later edits do not change history."""

    order_number = models.CharField(max_length=20, unique=True)  # LZ-10428
    public_token = models.UUIDField(default=uuid.uuid4, editable=False)  # lets a guest open the confirmation
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=24, default="awaiting_payment")
    placed_at = models.DateTimeField()
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=40, blank=True, default="")
    ship_first_name = models.CharField(max_length=100)
    ship_last_name = models.CharField(max_length=100)
    ship_street = models.CharField(max_length=160)
    ship_house_number = models.CharField(max_length=20)
    ship_addition = models.CharField(max_length=20, blank=True, default="")
    ship_postcode = models.CharField(max_length=7)
    ship_city = models.CharField(max_length=100)
    ship_lat = models.FloatField(null=True, blank=True)
    ship_lng = models.FloatField(null=True, blank=True)
    ship_notes = models.CharField(max_length=300, blank=True, default="")
    delivery_method = models.CharField(max_length=10, default="own_van")
    delivery = models.ForeignKey(Delivery, null=True, blank=True, on_delete=models.PROTECT, related_name="orders")
    delivery_choice = models.CharField(max_length=10, default="time_range")
    payment_method = models.CharField(max_length=20)
    confirm_deadline_at = models.DateTimeField(null=True, blank=True)  # pay on delivery: reservation hold deadline
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cancel_reason = models.CharField(max_length=40, blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    claimed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    claimed_until = models.DateTimeField(null=True, blank=True)
    subtotal_cents = models.IntegerField()
    discount_cents = models.IntegerField(default=0)
    delivery_fee_cents = models.IntegerField(default=0)
    total_cents = models.IntegerField()
    vat_9_cents = models.IntegerField(default=0)
    vat_21_cents = models.IntegerField(default=0)
    promo_code = models.CharField(max_length=40, blank=True, default="")
    language = models.CharField(max_length=2, choices=LANGS, default="nl")
    channel = models.CharField(max_length=10, default="web")
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order"
        ordering = ["-placed_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=ORDER_STATUSES), name="order_status_chk"),
            models.CheckConstraint(condition=models.Q(delivery_method__in=["own_van", "carrier", "pickup"]), name="order_delivery_method_chk"),
            models.CheckConstraint(condition=models.Q(delivery_choice__in=["asap", "time_range"]), name="order_delivery_choice_chk"),
            models.CheckConstraint(condition=models.Q(payment_method__in=["ideal", "card", "card_on_delivery"]), name="order_payment_method_chk"),
            models.CheckConstraint(condition=models.Q(channel__in=["web", "ios", "android"]), name="order_channel_chk"),
            models.CheckConstraint(condition=models.Q(total_cents__gte=0), name="order_total_chk"),
        ]
        indexes = [
            models.Index(fields=["status", "placed_at"]),
            models.Index(fields=["delivery", "status"]),
        ]

    def __str__(self) -> str:
        return self.order_number


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name_snapshot = models.CharField(max_length=200)
    storage_type_snapshot = models.CharField(max_length=10)
    unit_price_cents = models.IntegerField()
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    vat_rate_pct = models.DecimalField(max_digits=4, decimal_places=1)  # frozen at order time
    line_total_cents = models.IntegerField()

    class Meta:
        db_table = "order_line"
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="order_line_qty_chk"),
            models.UniqueConstraint(fields=["order", "product"], name="order_line_product_uniq"),
        ]


class OrderConfirmationAttempt(models.Model):
    """Call log for pay-on-delivery orders."""

    OUTCOMES = [(o, o) for o in ("confirmed", "no_answer", "customer_cancelled", "details_changed", "rejected")]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="attempts")
    attempted_at = models.DateTimeField(auto_now_add=True)
    operator = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    outcome = models.CharField(max_length=20, choices=OUTCOMES)
    note = models.CharField(max_length=300, blank=True, default="")
    next_call_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "order_confirmation_attempt"
        ordering = ["attempted_at"]


class CustomerFlag(models.Model):
    """Informational only: nothing is blocked automatically."""

    KINDS = [("refused_at_confirmation", "refused_at_confirmation"), ("refused_at_delivery", "refused_at_delivery")]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="flags")
    kind = models.CharField(max_length=30, choices=KINDS)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = "customer_flag"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=24)
    at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=120, blank=True, default="system")

    class Meta:
        db_table = "order_status_history"
        ordering = ["at", "id"]


class DeliveryStop(models.Model):
    STATUS = [(s, s) for s in ("pending", "arrived", "delivered", "failed", "rescheduled")]
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="stops")
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="stop")
    sequence = models.PositiveIntegerField()
    planned_arrival = models.DateTimeField(null=True, blank=True)
    window_start = models.DateTimeField(null=True, blank=True)
    window_end = models.DateTimeField(null=True, blank=True)
    leg_distance_m = models.PositiveIntegerField(null=True, blank=True)
    leg_duration_s = models.PositiveIntegerField(null=True, blank=True)
    instructions = models.JSONField(default=list, blank=True)
    geometry = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True, default="")
    flag_customer = models.BooleanField(default=False)  # entered while closing, saved on close
    payment_collected = models.BooleanField(default=False)  # card terminal, entered while closing

    class Meta:
        db_table = "delivery_stop"
        ordering = ["delivery", "sequence"]
        constraints = [models.UniqueConstraint(fields=["delivery", "sequence"], name="delivery_stop_sequence_uniq", deferrable=models.Deferrable.DEFERRED)]


class DeliveryReturn(models.Model):
    """Written when the operator closes the delivery (drafts allowed): what came back and why."""

    delivery_stop = models.ForeignKey(DeliveryStop, on_delete=models.CASCADE, related_name="returns")
    order_line = models.ForeignKey(OrderLine, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.ForeignKey(ReturnReason, on_delete=models.PROTECT)
    note = models.CharField(max_length=300, blank=True, default="")
    recorded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    recorded_at = models.DateTimeField(auto_now=True)
    is_final = models.BooleanField(default=False)  # False while the close is only saved as a draft
    stock_movement_id = models.BigIntegerField(null=True, blank=True)  # silver ledger row, filled by the pipeline

    class Meta:
        db_table = "delivery_return"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_return_qty_chk"),
            models.UniqueConstraint(fields=["delivery_stop", "order_line"], name="delivery_return_line_uniq"),
        ]


class Payment(models.Model):
    """No card data is stored. For pay on delivery the payment stays pending until collection is confirmed."""

    METHODS = [("ideal", "ideal"), ("card", "card"), ("card_on_delivery", "card_on_delivery")]
    STATUS = [(s, s) for s in ("pending", "paid", "failed", "refunded")]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=20)  # test, mollie, terminal
    provider_payment_id = models.CharField(max_length=80, blank=True, default="")
    method = models.CharField(max_length=20, choices=METHODS)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    amount_cents = models.IntegerField()
    paid_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True, default="")
    collected_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    collected_at = models.DateTimeField(null=True, blank=True)
    delivery_stop = models.ForeignKey(DeliveryStop, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment"


class StockReservation(models.Model):
    """held -> committed (paid / confirmed) -> consumed (out for delivery); or released / expired."""

    STATUS = [(s, s) for s in ("held", "committed", "released", "expired", "consumed")]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="reservations")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    status = models.CharField(max_length=10, choices=STATUS, default="held")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_reservation"
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="stock_reservation_qty_chk"),
            models.UniqueConstraint(fields=["order", "product"], name="stock_reservation_uniq"),
        ]
        indexes = [models.Index(fields=["product", "status"])]


class PickLine(models.Model):
    """Which lot went into which order line: the traceability link for recalls. Written when the
    operator approves a delivery (first-expired-first-out allocation)."""

    order_line = models.ForeignKey(OrderLine, on_delete=models.PROTECT, related_name="picks")
    receiving_line = models.ForeignKey(ReceivingLine, on_delete=models.PROTECT, related_name="picks")
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    picked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    picked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pick_line"
        constraints = [models.CheckConstraint(condition=models.Q(qty__gt=0), name="pick_line_qty_chk")]
