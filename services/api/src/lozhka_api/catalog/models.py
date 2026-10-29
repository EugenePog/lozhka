"""Catalogue: categories, product passports, prices, promo codes (docs 02 section 4.1, area a).

Natural keys (used by the seed files): category.slug, brand.name, product.sku, vat_rate.code,
allergen.code, promo_code.code; translations by (parent, lang).
"""
from django.conf import settings
from django.db import models

from lozhka_api.core.models import LANGS

LANG_CHOICES = LANGS
STORAGE = [("ambient", "ambient"), ("chilled", "chilled"), ("frozen", "frozen")]


class VatRate(models.Model):
    code = models.CharField(max_length=40, unique=True)  # reduced_9, standard_21
    rate_pct = models.DecimalField(max_digits=4, decimal_places=1)
    valid_from = models.DateField()

    class Meta:
        db_table = "vat_rate"

    def __str__(self) -> str:
        return f"{self.code} ({self.rate_pct}%)"


class Category(models.Model):
    KINDS = [("regular", "regular"), ("offers", "offers")]
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    slug = models.SlugField(max_length=80, unique=True)
    sort = models.IntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    # "offers" is a virtual category listing products that have an active offer price (W02 nav)
    kind = models.CharField(max_length=10, choices=KINDS, default="regular")
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "category"
        ordering = ["sort", "slug"]

    def __str__(self) -> str:
        return self.slug


class CategoryTranslation(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="translations")
    lang = models.CharField(max_length=2, choices=LANG_CHOICES)
    name = models.CharField(max_length=160)

    class Meta:
        db_table = "category_translation"
        constraints = [
            models.UniqueConstraint(fields=["category", "lang"], name="category_translation_uniq"),
            models.CheckConstraint(condition=models.Q(lang__in=["nl", "en", "ru"]), name="category_translation_lang_chk"),
        ]


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        db_table = "brand"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Allergen(models.Model):
    """The 14 EU allergens. Added to the design so allergen names exist in three languages as data."""

    code = models.CharField(max_length=30, unique=True)
    sort = models.IntegerField(default=0)

    class Meta:
        db_table = "allergen"
        ordering = ["sort", "code"]

    def __str__(self) -> str:
        return self.code


class AllergenTranslation(models.Model):
    allergen = models.ForeignKey(Allergen, on_delete=models.CASCADE, related_name="translations")
    lang = models.CharField(max_length=2, choices=LANG_CHOICES)
    name = models.CharField(max_length=120)

    class Meta:
        db_table = "allergen_translation"
        constraints = [models.UniqueConstraint(fields=["allergen", "lang"], name="allergen_translation_uniq")]


class Product(models.Model):
    """The product passport."""

    STATUS = [("draft", "draft"), ("active", "active"), ("archived", "archived")]
    UNIT_TYPE = [("piece", "piece"), ("weight", "weight")]
    NET_UNITS = [("g", "g"), ("kg", "kg"), ("ml", "ml"), ("l", "l"), ("pcs", "pcs")]

    sku = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    gtin = models.CharField(max_length=14, null=True, blank=True, unique=True)
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    status = models.CharField(max_length=10, choices=STATUS, default="draft")
    unit_type = models.CharField(max_length=10, choices=UNIT_TYPE, default="piece")
    net_content_value = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    net_content_unit = models.CharField(max_length=4, choices=NET_UNITS, null=True, blank=True)
    storage_type = models.CharField(max_length=10, choices=STORAGE, default="ambient")
    storage_temp_min_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    storage_temp_max_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    shelf_life_days_default = models.PositiveIntegerField(null=True, blank=True)
    min_shelf_life_days_for_sale = models.PositiveIntegerField(default=0)
    vat_rate = models.ForeignKey(VatRate, on_delete=models.PROTECT)
    country_of_origin = models.CharField(max_length=2, blank=True, default="")
    is_alcohol = models.BooleanField(default=False)
    age_restricted = models.BooleanField(default=False)
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=5)
    safety_stock_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    is_orderable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "product"
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=["draft", "active", "archived"]), name="product_status_chk"),
            models.CheckConstraint(condition=models.Q(storage_type__in=["ambient", "chilled", "frozen"]), name="product_storage_chk"),
            models.CheckConstraint(condition=models.Q(unit_type__in=["piece", "weight"]), name="product_unit_type_chk"),
            models.CheckConstraint(
                condition=models.Q(net_content_unit__isnull=True) | models.Q(net_content_unit__in=["g", "kg", "ml", "l", "pcs"]),
                name="product_net_unit_chk",
            ),
        ]
        indexes = [models.Index(fields=["category", "status"])]

    def __str__(self) -> str:
        return self.sku


class ProductTranslation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="translations")
    lang = models.CharField(max_length=2, choices=LANG_CHOICES)
    name = models.CharField(max_length=200)
    short_description = models.CharField(max_length=300, blank=True, default="")
    description = models.TextField(blank=True, default="")
    ingredients = models.TextField(blank=True, default="")
    storage_instructions = models.TextField(blank=True, default="")
    # transliterations ("pelmeni" for "пельмени") so search works in either script
    search_terms = models.TextField(blank=True, default="")

    class Meta:
        db_table = "product_translation"
        constraints = [
            models.UniqueConstraint(fields=["product", "lang"], name="product_translation_uniq"),
            models.CheckConstraint(condition=models.Q(lang__in=["nl", "en", "ru"]), name="product_translation_lang_chk"),
        ]


class ProductAllergen(models.Model):
    PRESENCE = [("contains", "contains"), ("may_contain", "may_contain")]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="allergens")
    allergen = models.ForeignKey(Allergen, to_field="code", db_column="allergen_code", on_delete=models.PROTECT)
    presence = models.CharField(max_length=12, choices=PRESENCE, default="contains")

    class Meta:
        db_table = "product_allergen"
        constraints = [models.UniqueConstraint(fields=["product", "allergen"], name="product_allergen_uniq")]


class ProductNutrition(models.Model):
    """Per 100 g or 100 ml, shown in the 'Ingredients and nutrition' tab."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="nutrition")
    basis = models.CharField(max_length=5, choices=[("100g", "100 g"), ("100ml", "100 ml")], default="100g")
    energy_kj = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    energy_kcal = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    saturates_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    carbohydrates_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    sugars_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    fibre_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    protein_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    salt_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "product_nutrition"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    storage_key = models.CharField(max_length=300)  # object storage key
    sort = models.IntegerField(default=0)
    alt_text = models.JSONField(default=dict, blank=True)  # {"nl": "...", "en": "...", "ru": "..."}

    class Meta:
        db_table = "product_image"
        constraints = [models.UniqueConstraint(fields=["product", "storage_key"], name="product_image_uniq")]
        ordering = ["sort"]


class ProductHighlight(models.Model):
    """Curated Bestsellers / New this week lists for the home page.
    Interim until the Gold ranking tables exist (docs 03 section 3, W01)."""

    KINDS = [("bestseller", "bestseller"), ("new", "new")]
    kind = models.CharField(max_length=12, choices=KINDS)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="highlights")
    sort = models.IntegerField(default=0)

    class Meta:
        db_table = "product_highlight"
        constraints = [models.UniqueConstraint(fields=["kind", "product"], name="product_highlight_uniq")]
        ordering = ["kind", "sort"]


class Price(models.Model):
    """Price history. The current price is the row valid now with the highest priority
    (markdown, offer, regular). Customer-facing prices include VAT."""

    KINDS = [("regular", "regular"), ("offer", "offer"), ("markdown", "markdown")]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="prices")
    amount_cents = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=KINDS, default="regular")
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "price"
        constraints = [
            models.UniqueConstraint(fields=["product", "kind", "valid_from"], name="price_natural_uniq"),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=models.F("valid_from")),
                name="price_valid_range_chk",
            ),
            models.CheckConstraint(condition=models.Q(kind__in=["regular", "offer", "markdown"]), name="price_kind_chk"),
        ]
        indexes = [models.Index(fields=["product", "valid_from"])]


class PromoCode(models.Model):
    KINDS = [("percent", "percent"), ("fixed", "fixed")]
    code = models.CharField(max_length=40, unique=True)
    kind = models.CharField(max_length=8, choices=KINDS)
    value = models.PositiveIntegerField()  # percent, or cents for a fixed amount
    min_order_cents = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    max_uses_per_customer = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "promo_code"
        constraints = [models.CheckConstraint(condition=models.Q(kind__in=["percent", "fixed"]), name="promo_kind_chk")]
