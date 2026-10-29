"""Master data in the Django admin, gated by the capability permissions (not by Django's model permissions), so each
function belongs to one role. Customer and order data is NOT registered here: the admin role cannot see it."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from lozhka_api.catalog import models as cat
from lozhka_api.core import models as core
from lozhka_api.procurement import models as proc
from lozhka_api.sales import models as sales

admin.site.site_header = "Lozhka · catalogue and master data"
admin.site.index_title = "Master data"


class CapabilityAdmin(admin.ModelAdmin):
    capability = "edit_catalogue"
    save_on_top = True

    def _ok(self, request) -> bool:
        return request.user.is_active and request.user.has_perm(f"core.{self.capability}")

    has_module_permission = has_view_permission = has_add_permission = has_change_permission = has_delete_permission = (
        lambda self, request, obj=None: self._ok(request))  # type: ignore[assignment]


class TranslationInline(admin.TabularInline):
    extra = 0


class ProductTranslationInline(TranslationInline):
    model = cat.ProductTranslation


class ProductAllergenInline(TranslationInline):
    model = cat.ProductAllergen


class ProductImageInline(TranslationInline):
    model = cat.ProductImage


class PriceInline(TranslationInline):
    model = cat.Price
    fields = ("kind", "amount_cents", "valid_from", "valid_to", "reason")


class NutritionInline(admin.StackedInline):
    model = cat.ProductNutrition
    extra = 0


@admin.register(cat.Product)
class ProductAdmin(CapabilityAdmin):
    list_display = ("sku", "slug", "category", "brand", "status", "storage_type", "is_orderable")
    list_filter = ("status", "storage_type", "category")
    search_fields = ("sku", "slug", "translations__name")
    inlines = [ProductTranslationInline, PriceInline, ProductAllergenInline, NutritionInline, ProductImageInline]
    fieldsets = (
        ("Identity", {"fields": ("sku", "slug", "gtin", "brand", "category", "status", "is_orderable")}),
        ("Content and storage", {"fields": ("unit_type", ("net_content_value", "net_content_unit"), "storage_type", ("storage_temp_min_c", "storage_temp_max_c"),
                                            "shelf_life_days_default", "min_shelf_life_days_for_sale", "country_of_origin")}),
        ("Tax and rules", {"fields": ("vat_rate", "is_alcohol", "age_restricted")}),
        ("Stock", {"fields": ("low_stock_threshold", "safety_stock_qty")}),
    )


class CategoryTranslationInline(TranslationInline):
    model = cat.CategoryTranslation


@admin.register(cat.Category)
class CategoryAdmin(CapabilityAdmin):
    list_display = ("slug", "parent", "sort", "is_visible", "kind")
    inlines = [CategoryTranslationInline]


class AllergenTranslationInline(TranslationInline):
    model = cat.AllergenTranslation


@admin.register(cat.Allergen)
class AllergenAdmin(CapabilityAdmin):
    inlines = [AllergenTranslationInline]


for model in (cat.Brand, cat.VatRate, cat.PromoCode, cat.ProductHighlight):
    admin.site.register(model, type(f"{model.__name__}Admin", (CapabilityAdmin,), {}))


@admin.register(core.ContentBlock)
class ContentBlockAdmin(CapabilityAdmin):
    capability = "edit_content"
    list_display = ("slug", "lang", "kind", "title", "published")
    list_filter = ("kind", "lang")


@admin.register(core.ExpiryRule, core.NotificationRecipient)
class ExpiryAdmin(CapabilityAdmin):
    capability = "edit_delivery_rules"


for model in (proc.Supplier, proc.SupplierProduct, proc.SupplierImportProfile):
    admin.site.register(model, type(f"{model.__name__}Admin", (CapabilityAdmin,), {"capability": "edit_suppliers"}))

for model in (sales.DeliveryZone, sales.Vehicle, sales.Driver, sales.Depot):
    admin.site.register(model, type(f"{model.__name__}Admin", (CapabilityAdmin,), {"capability": "edit_delivery_rules"}))


@admin.register(core.Setting)
class SettingAdmin(CapabilityAdmin):
    capability = "edit_delivery_rules"
    list_display = ("key", "value", "updated_at")


# ---- people and roles (manage_staff) --------------------------------------------------------------------------------------

User = get_user_model()
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class StaffUserAdmin(UserAdmin, CapabilityAdmin):
    capability = "manage_staff"
    list_display = ("username", "email", "is_staff", "is_active", "role_list")
    list_filter = ("is_active", "groups")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Person", {"fields": ("first_name", "last_name", "email")}),
        ("Access", {"fields": ("is_active", "is_staff", "groups")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2", "is_staff", "groups")}),)

    def get_queryset(self, request):
        # customers share the user table; they never show up in the staff list
        return super().get_queryset(request).exclude(username__startswith="customer:")

    @admin.display(description="Roles")
    def role_list(self, obj):
        return ", ".join(g.name for g in obj.groups.all())


@admin.register(Group)
class RoleAdmin(CapabilityAdmin):
    capability = "manage_staff"
    filter_horizontal = ("permissions",)
