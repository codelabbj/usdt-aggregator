from django.contrib import admin
from .models import LiquidityConfig, RateAdjustment, PlatformConfig, APIKey, BestRatesRefreshConfig, BestRate


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


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "active", "created_at")


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
