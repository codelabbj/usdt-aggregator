from django.db import models


class RateHistory(models.Model):
    """Historique des taux pour reporting et audit."""

    source_currency = models.CharField(max_length=10)
    target_currency = models.CharField(max_length=10)
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    trade_type = models.CharField(max_length=4)
    platform = models.CharField(max_length=30)
    country = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historique taux"
        verbose_name_plural = "Historiques taux"
        ordering = ["-created_at"]
