from django.db import models


class Currency(models.Model):
    """
    Devise pour laquelle on agrège les offres P2P (ex. XOF, GHS, USD).
    Créée et gérée dans l'admin. Seules les devises actives sont utilisées par le refresh des best rates.
    """
    code = models.CharField(max_length=10, unique=True, help_text="Code ISO (ex. XOF, GHS, USD)")
    name = models.CharField(max_length=100, blank=True, help_text="Nom affiché (ex. Franc CFA BCEAO)")
    active = models.BooleanField(default=True, help_text="Désactiver pour exclure du refresh des taux")
    order = models.PositiveSmallIntegerField(default=0, help_text="Ordre d'affichage (plus petit = en premier)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Devise"
        verbose_name_plural = "Devises"
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.code}" + (f" ({self.name})" if self.name else "")


class Country(models.Model):
    """
    Pays associé à une devise, pour segmenter les offres (ex. Bénin pour XOF).
    Créé et géré dans l'admin. Pour une devise sans pays, le refresh utilise uniquement le filtre "global" (tous pays).
    """
    code = models.CharField(max_length=10, help_text="Code ISO pays (ex. BJ, SN, CI)")
    name = models.CharField(max_length=100, help_text="Nom du pays")
    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name="countries",
        help_text="Devise à laquelle ce pays est rattaché",
    )
    active = models.BooleanField(default=True, help_text="Désactiver pour exclure du refresh")
    order = models.PositiveSmallIntegerField(default=0, help_text="Ordre d'affichage")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pays"
        verbose_name_plural = "Pays"
        ordering = ["currency", "order", "code"]
        unique_together = [["currency", "code"]]

    def __str__(self):
        return f"{self.code} ({self.name}) — {self.currency.code}"


class LiquidityConfig(models.Model):
    """Min/max fiat pour filtrer les offres BUY et SELL (plage de montant en devise)."""

    TRADE_TYPE_BUY = "BUY"
    TRADE_TYPE_SELL = "SELL"
    TRADE_TYPES = [(TRADE_TYPE_BUY, "Achat"), (TRADE_TYPE_SELL, "Vente")]

    trade_type = models.CharField(max_length=4, choices=TRADE_TYPES)
    min_amount = models.DecimalField(
        max_digits=20, decimal_places=8, default=0,
        help_text="Montant fiat minimum (ex. FCFA)"
    )
    max_amount = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True,
        help_text="Montant fiat maximum, vide = pas de limite"
    )
    require_inclusion = models.BooleanField(
        default=False,
        help_text="Si coché : garder seulement les offres dont la plage est incluse dans [min, max]. Sinon : chevauchement suffit."
    )
    amount_in_fiat = models.BooleanField(
        default=True,
        help_text="Si coché : min/max config et plage offre en fiat (min_fiat, max_fiat). Sinon : en USDT (min_usdt, max_usdt)."
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Config liquidité"
        verbose_name_plural = "Configs liquidité"
        unique_together = [["trade_type"]]

    def __str__(self):
        return f"Liquidité {self.get_trade_type_display()} min={self.min_amount} max={self.max_amount}"


class RateAdjustment(models.Model):
    """
    Règle d'ajustement des taux. 3 champs : cible (à qui), mode (comment), valeur.
    Offres : cible contient toujours SELL ou BUY (base SELL/BUY, puis XOF:SELL, XOF:BJ:SELL…). Pas de global ni devise seule.
    Cross : cross | cross:SOURCE | cross:SOURCE:CIBLE.
    """
    MODE_PERCENT = "percent"
    MODE_FIXED = "fixed"
    MODE_CHOICES = [(MODE_PERCENT, "Pourcentage (%)"), (MODE_FIXED, "Montant fixe")]

    # Offres uniquement : SELL, BUY, XOF:SELL, XOF:BUY, XOF:BJ:SELL… (toujours SELL ou BUY)
    target = models.CharField(
        max_length=50,
        default="SELL",
        help_text="Offres: SELL | BUY | XOF:SELL | XOF:BUY | XOF:BJ:SELL…",
    )
    # Mode : % ou montant fixe
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    # Valeur : le % (ex. 2.5) ou le montant fixe. Positif = majoration, négatif = minoration.
    value = models.DecimalField(max_digits=20, decimal_places=8)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ajustement de taux"
        verbose_name_plural = "Ajustements de taux"

    def __str__(self):
        return f"{self.target} {self.get_mode_display()}={self.value}"


class CrossRateAdjustment(models.Model):
    """
    Ajustement dédié au taux croisé (from → to via USDT).
    Indique l'ajustement à appliquer sur le BUY (côté devise source) et sur le SELL (côté devise cible).
    Cible = cross | cross:SOURCE | cross:SOURCE:CIBLE (ex. cross:XOF:GHS).
    """
    MODE_PERCENT = "percent"
    MODE_FIXED = "fixed"
    MODE_CHOICES = [(MODE_PERCENT, "Pourcentage (%)"), (MODE_FIXED, "Montant fixe")]

    target = models.CharField(
        max_length=50,
        default="cross",
        help_text="cross | cross:SOURCE | cross:SOURCE:CIBLE (ex. cross:XOF:GHS)",
    )
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    # Ajustement sur le prix BUY (côté devise source : client donne from_currency, reçoit USDT)
    value_buy = models.DecimalField(
        max_digits=20, decimal_places=8, default=0,
        help_text="% ou montant fixe sur le leg BUY. Positif = majoration, négatif = minoration.",
    )
    # Ajustement sur le prix SELL (côté devise cible : client donne USDT, reçoit to_currency)
    value_sell = models.DecimalField(
        max_digits=20, decimal_places=8, default=0,
        help_text="% ou montant fixe sur le leg SELL. Positif = majoration, négatif = minoration.",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ajustement taux croisé"
        verbose_name_plural = "Ajustements taux croisé"

    def __str__(self):
        return f"{self.target} BUY={self.value_buy} SELL={self.value_sell}"


class PlatformConfig(models.Model):
    """Plateforme P2P source (Binance par défaut, extensible)."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plateforme P2P"
        verbose_name_plural = "Plateformes P2P"

    def __str__(self):
        return f"{self.name} ({self.code})"


def _generate_api_key():
    import secrets
    return secrets.token_urlsafe(32)


class APIKey(models.Model):
    """Clé API pour authentification et facturation par nombre d'appels."""
    name = models.CharField(max_length=100, help_text="Usage ou identifiant client")
    key = models.CharField(max_length=64, unique=True, blank=True, help_text="Laisser vide pour générer à l'enregistrement.")
    active = models.BooleanField(default=True)
    monthly_quota = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Nombre max d'appels par mois (vide = illimité).",
    )
    billing_exempt = models.BooleanField(
        default=False,
        help_text="Si coché, cette clé est exemptée de facturation (montant = 0).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Clé API"
        verbose_name_plural = "Clés API"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = _generate_api_key()
        super().save(*args, **kwargs)


class APIKeyUsage(models.Model):
    """Compteur d'appels par clé API et par mois (pour facturation)."""
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name="usages")
    period = models.CharField(max_length=7, help_text="YYYY-MM")
    call_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Usage API (mois)"
        verbose_name_plural = "Usages API (mois)"
        unique_together = [["api_key", "period"]]
        ordering = ["api_key", "-period"]

    def __str__(self):
        return f"{self.api_key.name} {self.period}: {self.call_count} appels"


class BillingConfig(models.Model):
    """
    Configuration globale de facturation (une seule ligne = singleton).
    Prix par appel appliqué à toutes les clés non exemptées.
    """
    price_per_call = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
        help_text="Prix facturé par appel API (ex: 0.001 pour 0,001 €/appel).",
    )
    currency = models.CharField(
        max_length=10,
        default="EUR",
        help_text="Devise (ex: EUR, USD, XOF).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Config facturation"
        verbose_name_plural = "Config facturation"

    def __str__(self):
        return f"{self.price_per_call} {self.currency}/appel"


class BestRatesRefreshConfig(models.Model):
    """
    Config du rafraîchissement des best rates (une seule ligne = singleton).
    L'admin définit l'intervalle en minutes ; le cron appelle la commande chaque minute,
    la commande n'exécute le refresh que si (now - last_run_at) >= interval_minutes.
    """
    INTERVAL_CHOICES = [(1, "1 min"), (5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min")]
    interval_minutes = models.PositiveSmallIntegerField(
        default=5,
        choices=INTERVAL_CHOICES,
        help_text="Fréquence de rafraîchissement (cron doit appeler la commande toutes les 1 min).",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Désactiver pour arrêter le refresh automatique.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Config refresh best rates"
        verbose_name_plural = "Config refresh best rates"

    def __str__(self):
        return f"Refresh toutes les {self.interval_minutes} min (dernier: {self.last_run_at})"


class BestRate(models.Model):
    """
    Meilleurs taux USDT/fiat par devise, type (BUY/SELL) et plateforme. Pas de filtre pays.
    Jusqu'à 3 lignes par (fiat, trade_type, platform). À la lecture on trie par rate
    et on expose les 3 meilleurs tous plateformes confondus (SELL = desc, BUY = asc).
    """
    fiat = models.CharField(max_length=10)
    trade_type = models.CharField(max_length=4)  # BUY, SELL
    country = models.CharField(max_length=10, blank=True)
    platform = models.CharField(max_length=30)
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meilleur taux"
        verbose_name_plural = "Meilleurs taux"
        ordering = ["fiat", "trade_type", "country", "platform", "rate"]

    def __str__(self):
        return f"USDT/{self.fiat} {self.trade_type} {self.rate} ({self.platform})"


class OffersSnapshot(models.Model):
    """
    Snapshot des offres brutes (refresh = seule source de vérité).
    Une ligne par (platform, fiat, trade_type, country). data = liste d'offres (JSON), aucun calcul.
    Les APIs lisent ici puis appliquent config liquidité + ajustements.
    """
    platform = models.CharField(max_length=30)
    fiat = models.CharField(max_length=10)
    trade_type = models.CharField(max_length=4)  # BUY, SELL
    country = models.CharField(max_length=10, blank=True, default="")
    data = models.JSONField(default=list, help_text="Liste d'offres brutes (price, min_fiat, max_fiat, advertiser, etc.)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Snapshot offres"
        verbose_name_plural = "Snapshots offres"
        unique_together = [["platform", "fiat", "trade_type", "country"]]
        ordering = ["platform", "fiat", "trade_type", "country"]

    def __str__(self):
        return f"{self.platform} {self.fiat} {self.trade_type} {self.country or 'all'} ({len(self.data)} offres)"
