"""Configuration, content and the staff capability list (docs 02 sections 4.5 and 4.7)."""
from django.db import models

LANGS = [("nl", "Nederlands"), ("en", "English"), ("ru", "Русский")]


class Setting(models.Model):
    """Business rules editable without a release: minimum order, reservation time, switches."""

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "setting"

    def __str__(self) -> str:
        return self.key


class ContentBlock(models.Model):
    """Hero banner, USP row, FAQ and help pages (W01, W09). Natural key: (slug, lang)."""

    KINDS = [("hero", "hero"), ("usp", "usp"), ("faq", "faq"), ("page", "page"), ("card", "card")]
    slug = models.CharField(max_length=120)
    lang = models.CharField(max_length=2, choices=LANGS)
    kind = models.CharField(max_length=10, choices=KINDS)
    title = models.CharField(max_length=300, blank=True, default="")
    body_markdown = models.TextField(blank=True, default="")
    sort = models.IntegerField(default=0)
    published = models.BooleanField(default=True)

    class Meta:
        db_table = "content_block"
        constraints = [
            models.UniqueConstraint(fields=["slug", "lang"], name="content_block_slug_lang_uniq"),
            models.CheckConstraint(
                condition=models.Q(lang__in=["nl", "en", "ru"]), name="content_block_lang_chk"
            ),
        ]
        indexes = [models.Index(fields=["kind", "lang", "sort"])]

    def __str__(self) -> str:
        return f"{self.slug} [{self.lang}]"


class ExpiryRule(models.Model):
    """Thresholds for the expiry module M5. scope_ref is the natural reference of the scope:
    a storage type, a category slug or a product SKU (empty for the global rule)."""

    SCOPES = [("global", "global"), ("storage_type", "storage_type"), ("category", "category"), ("product", "product")]
    scope = models.CharField(max_length=20, choices=SCOPES)
    scope_ref = models.CharField(max_length=120, blank=True, default="")
    warn_days = models.JSONField(default=list)  # e.g. [14, 7, 3, 1]
    markdown_suggestion_pct = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "expiry_rule"
        constraints = [models.UniqueConstraint(fields=["scope", "scope_ref"], name="expiry_rule_scope_uniq")]


class NotificationRecipient(models.Model):
    """Who gets expiry digests, pipeline alerts and new-order alerts."""

    CHANNELS = [("email", "email"), ("telegram", "telegram")]
    name = models.CharField(max_length=120)
    channel = models.CharField(max_length=10, choices=CHANNELS)
    address = models.CharField(max_length=200)
    topics = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_recipient"
        constraints = [models.UniqueConstraint(fields=["channel", "address"], name="notification_recipient_uniq")]


class StaffCapability(models.Model):
    """No table: a holder for the staff permissions (one per capability, docs 02 section 4.7).
    Groups admin / operator / storekeeper are bundles of these permissions (seed: roles)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            # admin
            ("edit_delivery_templates", "Delivery templates"),
            ("edit_delivery_rules", "Delivery zones, fee tiers, minimum order, pay-on-delivery switch"),
            ("edit_return_reasons", "Return reasons"),
            ("edit_suppliers", "Suppliers, supplier products, order schedule"),
            ("set_supplier_credentials", "Set or replace supplier credentials (write-only)"),
            ("edit_catalogue", "Product passports, categories, prices, promo codes"),
            ("edit_content", "Hero, USP, FAQ and help pages"),
            ("manage_staff", "Staff accounts and roles"),
            ("view_audit_log", "Audit log"),
            # shared read access
            ("view_catalogue", "Read product passports and categories"),
            # operator
            ("view_customer_data", "See customer names, phones and addresses"),
            ("confirm_cod_orders", "Orders to confirm (pay on delivery)"),
            ("manage_ready_orders", "Orders ready for delivery"),
            ("manage_deliveries", "Deliveries: vehicle, driver, approve, dispatch, move orders"),
            ("close_deliveries", "Close a delivery with returns"),
            # storekeeper
            ("receive_goods", "Incoming deliveries and receiving"),
            ("fix_delivery_lines", "Manual fixes of supplier delivery lines"),
            ("adjust_stock", "Stock adjustments and write-offs"),
        ]
