"""
Module central de majoration : un seul point d'appel pour appliquer les ajustements
(markup/markdown) à tout prix ou taux qui sort des APIs.
Utilise le modèle RateAdjustment (scope: global, devise, pays, trade_type; mode: % ou fixe).
"""
from decimal import Decimal
from typing import Union

from core.models import RateAdjustment


def apply_majoration(
    price: Union[float, str],
    currency: str = "",
    trade_type: str = "",
    country: str = "",
) -> float:
    """
    Applique la majoration configurée (RateAdjustment actifs) au prix/taux.
    À appeler sur tout prix ou taux avant de le renvoyer dans les réponses API.

    :param price: Prix ou taux brut
    :param currency: Code devise (ex. XOF, GHS) pour les règles par devise
    :param trade_type: BUY ou SELL pour les règles par type
    :param country: Code pays (optionnel)
    :return: Prix après application des ajustements (cumulés)
    """
    value = Decimal(str(price))
    for adj in RateAdjustment.objects.filter(active=True).order_by("id"):
        if adj.scope == RateAdjustment.SCOPE_GLOBAL:
            pass
        elif adj.scope == RateAdjustment.SCOPE_CURRENCY and adj.currency != currency:
            continue
        elif adj.scope == RateAdjustment.SCOPE_COUNTRY and adj.country and adj.country != country:
            continue
        elif adj.scope == RateAdjustment.SCOPE_TRADE_TYPE and adj.trade_type and adj.trade_type != trade_type:
            continue
        v = adj.value
        if adj.mode == RateAdjustment.MODE_PERCENT:
            value = value * (1 + float(v) / 100)
        else:
            value = value + float(v)
    return float(value)
