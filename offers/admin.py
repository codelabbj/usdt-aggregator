from django.contrib import admin
from .models import RateHistory


@admin.register(RateHistory)
class RateHistoryAdmin(admin.ModelAdmin):
    list_display = ("source_currency", "target_currency", "rate", "trade_type", "platform", "created_at")
    list_filter = ("platform", "trade_type")
