from django.utils import timezone
from django.contrib import admin
from .models import (
    Currency,
    Country,
    LiquidityConfig,
    RateAdjustment,
    PlatformConfig,
    APIKey,
    APIKeyUsage,
    BillingConfig,
    BestRatesRefreshConfig,
    BestRate,
)


class CountryInline(admin.TabularInline):
    model = Country
    extra = 0
    fields = ("code", "name", "active", "order")
    ordering = ("order", "code")


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "active", "order", "countries_count")
    list_filter = ("active",)
    list_editable = ("active", "order")
    ordering = ("order", "code")
    inlines = [CountryInline]
    search_fields = ("code", "name")

    def countries_count(self, obj):
        return obj.countries.filter(active=True).count()
    countries_count.short_description = "Pays actifs"


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "currency", "active", "order")
    list_filter = ("currency", "active")
    list_editable = ("active", "order")
    ordering = ("currency", "order", "code")
    search_fields = ("code", "name")


@admin.register(LiquidityConfig)
class LiquidityConfigAdmin(admin.ModelAdmin):
    list_display = ("trade_type", "min_amount", "max_amount", "active")
    list_filter = ("trade_type", "active")


@admin.register(RateAdjustment)
class RateAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("scope", "currency", "country", "trade_type", "mode", "value", "active")
    list_filter = ("scope", "mode", "active")


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "active", "is_default")


@admin.register(APIKeyUsage)
class APIKeyUsageAdmin(admin.ModelAdmin):
    list_display = ("api_key", "period", "call_count")
    list_filter = ("period",)
    readonly_fields = ("api_key", "period", "call_count")

    def has_add_permission(self, request):
        return False


@admin.register(BillingConfig)
class BillingConfigAdmin(admin.ModelAdmin):
    list_display = ("price_per_call", "currency", "updated_at")

    def has_add_permission(self, request):
        return not BillingConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key_preview", "active", "billing_exempt", "monthly_quota", "usage_current_month", "created_at")
    list_filter = ("active", "billing_exempt")
    readonly_fields = ("key",)

    def key_preview(self, obj):
        if not obj.key:
            return "—"
        return f"{obj.key[:8]}…" if len(obj.key) > 8 else obj.key
    key_preview.short_description = "Clé"

    def usage_current_month(self, obj):
        period = timezone.now().strftime("%Y-%m")
        try:
            u = APIKeyUsage.objects.get(api_key=obj, period=period)
            quota = f" / {obj.monthly_quota}" if obj.monthly_quota else ""
            return f"{u.call_count}{quota}"
        except APIKeyUsage.DoesNotExist:
            return f"0{f' / {obj.monthly_quota}' if obj.monthly_quota else ''}"
    usage_current_month.short_description = "Appels ce mois"


@admin.register(BestRatesRefreshConfig)
class BestRatesRefreshConfigAdmin(admin.ModelAdmin):
    list_display = ("interval_minutes", "last_run_at", "is_active", "updated_at")
    list_display_links = ("last_run_at",)

    def has_add_permission(self, request):
        return not BestRatesRefreshConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BestRate)
class BestRateAdmin(admin.ModelAdmin):
    list_display = ("fiat", "trade_type", "country", "platform", "rate", "updated_at")
    list_filter = ("fiat", "trade_type", "platform")
