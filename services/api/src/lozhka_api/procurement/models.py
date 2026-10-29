"""Suppliers, receiving, stock actions (docs 02 sections 4.1, 4.2, 4.6; areas b, c, f).

Natural keys: supplier.name, supplier_product (supplier, supplier_sku), receiving (supplier, delivery_ref),
purchase_order.po_number.
A receiving line IS a stock lot: its id is the lot id everywhere else.
"""
from django.conf import settings
from django.db import models

from lozhka_api.catalog.models import Category, Product

User = settings.AUTH_USER_MODEL


class Supplier(models.Model):
    CHANNELS = [("email", "email"), ("portal", "portal"), ("api", "api"), ("edi", "edi"), ("phone", "phone")]
    name = models.CharField(max_length=160, unique=True)
    country = models.CharField(max_length=2, blank=True, default="")
    vat_number = models.CharField(max_length=30, blank=True, default="")
    contact = models.TextField(blank=True, default="")
    order_channel = models.CharField(max_length=10, choices=CHANNELS, default="email")
    order_email = models.EmailField(blank=True, default="")
    min_order_value_cents = models.PositiveIntegerField(default=0)
    free_delivery_threshold_cents = models.PositiveIntegerField(null=True, blank=True)
    payment_terms_days = models.PositiveIntegerField(null=True, blank=True)
    default_lead_time_days = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "supplier"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SupplierProduct(models.Model):
    """Mapping between the wholesaler's article and our product. Several suppliers per product."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="products")
    supplier_sku = models.CharField(max_length=60)
    supplier_gtin = models.CharField(max_length=14, blank=True, default="")
    supplier_description = models.CharField(max_length=300, blank=True, default="")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="supplier_products")
    pack_size_units = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    purchase_price_cents = models.PositiveIntegerField(null=True, blank=True)  # per pack
    valid_from = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=1)  # 1 = first choice
    is_orderable = models.BooleanField(default=True)
    min_order_qty_packs = models.PositiveIntegerField(default=1)
    order_multiple_packs = models.PositiveIntegerField(default=1)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)  # empty = supplier default

    class Meta:
        db_table = "supplier_product"
        constraints = [models.UniqueConstraint(fields=["supplier", "supplier_sku"], name="supplier_product_uniq")]


class SupplierImportProfile(models.Model):
    """Describes one supplier file layout. New layout = new profile, no code change (module M2)."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="import_profiles")
    name = models.CharField(max_length=120)
    file_type = models.CharField(max_length=10, choices=[("xlsx", "xlsx"), ("xls", "xls"), ("csv", "csv")])
    sheet_name = models.CharField(max_length=80, blank=True, default="")
    header_row = models.PositiveIntegerField(default=1)
    encoding = models.CharField(max_length=20, blank=True, default="utf-8")
    delimiter = models.CharField(max_length=2, blank=True, default=";")
    decimal_separator = models.CharField(max_length=1, default=",")
    date_format = models.CharField(max_length=30, blank=True, default="%d.%m.%Y")
    column_map = models.JSONField(default=dict)
    transforms = models.JSONField(default=dict, blank=True)
    skip_rules = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "supplier_import_profile"
        constraints = [models.UniqueConstraint(fields=["supplier", "name", "version"], name="supplier_import_profile_uniq")]


class DeliveryLineFix(models.Model):
    """Manual correction of a supplier delivery line. Survives file reloads (docs 02 section 9)."""

    STATUS = [("active", "active"), ("stale", "stale")]
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    delivery_ref = models.CharField(max_length=80)
    line_key = models.CharField(max_length=100)  # supplier SKU, or SKU|lot when a SKU repeats
    field = models.CharField(max_length=30)  # qty_received, best_before, lot_code, ...
    value = models.CharField(max_length=100)
    document_value = models.CharField(max_length=100, blank=True, default="")  # source cell when the fix was made
    reason = models.CharField(max_length=300, blank=True, default="")
    status = models.CharField(max_length=8, choices=STATUS, default="active")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "delivery_line_fix"
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "delivery_ref", "line_key", "field"], name="delivery_line_fix_uniq"
            )
        ]


class Receiving(models.Model):
    """The physical event of goods arriving (also the HACCP record). Stock increases only when accepted."""

    STATUS = [("open", "open"), ("accepted", "accepted"), ("cancelled", "cancelled")]
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="receivings")
    delivery_ref = models.CharField(max_length=80)
    status = models.CharField(max_length=10, choices=STATUS, default="open")
    expected_date = models.DateField(null=True, blank=True)
    purchase_order_number = models.CharField(max_length=40, blank=True, default="")
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    vehicle_temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "receiving"
        constraints = [
            models.UniqueConstraint(fields=["supplier", "delivery_ref"], name="receiving_uniq"),
            models.CheckConstraint(condition=models.Q(status__in=["open", "accepted", "cancelled"]), name="receiving_status_chk"),
        ]
        ordering = ["-expected_date", "-id"]


class ReceivingLine(models.Model):
    """A receiving line is a stock lot."""

    SOURCES = [("document", "document"), ("entered", "entered"), ("estimated", "estimated")]
    receiving = models.ForeignKey(Receiving, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="lots")
    supplier_sku = models.CharField(max_length=60, blank=True, default="")
    supplier_lot_code = models.CharField(max_length=60, blank=True, default="")
    qty_expected = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)  # from the document
    qty_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    qty_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    best_before = models.DateField(null=True, blank=True)
    best_before_source = models.CharField(max_length=10, choices=SOURCES, default="entered")
    unit_cost_cents = models.PositiveIntegerField(null=True, blank=True)
    unit_differs = models.BooleanField(default=False)  # flag from the document check (SC06 issue tag)

    class Meta:
        db_table = "receiving_line"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(qty_received__gte=0) & models.Q(qty_rejected__gte=0), name="receiving_line_qty_chk"
            ),
            models.UniqueConstraint(
                fields=["receiving", "product", "supplier_lot_code"], name="receiving_line_uniq"
            ),
        ]
        indexes = [models.Index(fields=["product", "best_before"])]


class StockAdjustment(models.Model):
    """Write-offs and corrections against a lot. Reason required."""

    REASONS = [
        ("waste_expired", "waste_expired"),
        ("waste_damaged", "waste_damaged"),
        ("count_correction", "count_correction"),
        ("sample", "sample"),
        ("return_to_stock", "return_to_stock"),
        ("other", "other"),
    ]
    receiving_line = models.ForeignKey(ReceivingLine, on_delete=models.PROTECT, related_name="adjustments")
    qty_delta = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=20, choices=REASONS)
    note = models.CharField(max_length=300, blank=True, default="")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_adjustment"
        constraints = [
            models.CheckConstraint(condition=~models.Q(qty_delta=0), name="stock_adjustment_nonzero_chk"),
            models.CheckConstraint(
                condition=models.Q(reason__in=["waste_expired", "waste_damaged", "count_correction", "sample", "return_to_stock", "other"]),
                name="stock_adjustment_reason_chk",
            ),
        ]


# --- M8 purchasing (docs 02 section 4.6) ---------------------------------------------------------------------

class SupplierDeliverySchedule(models.Model):
    """One row per ordering cycle: two deliveries a week = two rows."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="schedules")
    order_weekday = models.PositiveSmallIntegerField()  # 0 = Monday
    order_cutoff_time = models.TimeField()
    delivery_weekday = models.PositiveSmallIntegerField()
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "supplier_delivery_schedule"
        constraints = [
            models.UniqueConstraint(fields=["supplier", "order_weekday", "delivery_weekday"], name="supplier_schedule_uniq"),
            models.CheckConstraint(
                condition=models.Q(order_weekday__lte=6) & models.Q(delivery_weekday__lte=6), name="supplier_schedule_weekday_chk"
            ),
        ]


class SupplierOrderTemplate(models.Model):
    """How a purchase order is written for this supplier (mirror image of the import profile)."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="order_templates")
    name = models.CharField(max_length=120)
    file_type = models.CharField(max_length=10, choices=[("xlsx", "xlsx"), ("csv", "csv")])
    layout = models.JSONField(default=dict)
    email_subject = models.JSONField(default=dict, blank=True)  # per language
    email_body = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "supplier_order_template"
        constraints = [models.UniqueConstraint(fields=["supplier", "name", "version"], name="supplier_order_template_uniq")]


class SupplierCredential(models.Model):
    """Metadata only. No secret in this table. Never copied to Bronze, readable only by lozhka_purchasing."""

    KINDS = [("portal_login", "portal_login"), ("api_key", "api_key"), ("sftp", "sftp"),
             ("email_account", "email_account"), ("edi", "edi")]
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="credentials")
    kind = models.CharField(max_length=20, choices=KINDS)
    label = models.CharField(max_length=120)
    endpoint_url = models.URLField(blank=True, default="")
    username = models.CharField(max_length=160, blank=True, default="")
    is_active = models.BooleanField(default=True)
    valid_until = models.DateField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = "supplier_credential"
        constraints = [models.UniqueConstraint(fields=["supplier", "label"], name="supplier_credential_uniq")]


class SupplierCredentialSecret(models.Model):
    """The encrypted password, API key or token (RSA-OAEP sealed with the PUBLIC key: the back office
    can write it but cannot read it back; only lozhka-worker-purchasing holds the private key)."""

    credential = models.OneToOneField(SupplierCredential, primary_key=True, on_delete=models.CASCADE, related_name="secret")
    secret_encrypted = models.BinaryField()
    key_version = models.CharField(max_length=40, default="v1")
    rotated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_credential_secret"


class ReplenishmentPolicy(models.Model):
    """The most specific scope wins. scope_ref = storage type, category slug or product SKU."""

    SCOPES = [("global", "global"), ("storage_type", "storage_type"), ("category", "category"), ("product", "product")]
    scope = models.CharField(max_length=20, choices=SCOPES)
    scope_ref = models.CharField(max_length=120, blank=True, default="")
    service_level = models.DecimalField(max_digits=4, decimal_places=3, default=0.95)
    safety_days = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    min_cover_days = models.DecimalField(max_digits=5, decimal_places=2, default=3)
    max_cover_days = models.DecimalField(max_digits=5, decimal_places=2, default=14)
    max_shelf_life_share = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    min_stock_qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    target_stock_qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    mode = models.CharField(max_length=12, choices=[("suggest_only", "suggest_only"), ("auto_draft", "auto_draft")], default="suggest_only")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "replenishment_policy"
        constraints = [models.UniqueConstraint(fields=["scope", "scope_ref"], name="replenishment_policy_uniq")]


class DemandOverride(models.Model):
    """Planned promotions, holidays, a known large order. Applied on top of the forecast."""

    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE)
    date_from = models.DateField()
    date_to = models.DateField()
    multiplier = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    extra_units = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "demand_override"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(product__isnull=False) | models.Q(category__isnull=False), name="demand_override_target_chk"
            )
        ]


class PurchaseOrder(models.Model):
    STATUS = [(s, s) for s in ("draft", "approved", "sent", "confirmed", "partially_received", "received", "cancelled")]
    po_number = models.CharField(max_length=40, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    channel = models.CharField(max_length=10, blank=True, default="")
    total_cost_cents = models.BigIntegerField(default=0)
    forecast_run_id = models.BigIntegerField(null=True, blank=True)  # silver.forecast_run, no cross-schema FK
    created_by = models.CharField(max_length=80, blank=True, default="system")
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    supplier_reference = models.CharField(max_length=80, blank=True, default="")
    document_storage_key = models.CharField(max_length=300, blank=True, default="")
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "purchase_order"


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    supplier_product = models.ForeignKey(SupplierProduct, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty_packs_suggested = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    qty_packs_ordered = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    pack_size_units = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit_cost_cents = models.PositiveIntegerField(default=0)  # per pack
    reason = models.JSONField(default=dict, blank=True)
    edited_by_staff = models.BooleanField(default=False)

    class Meta:
        db_table = "purchase_order_line"
