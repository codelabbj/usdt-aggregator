"""
Ajustements : offres (RateAdjustment) et cross (CrossRateAdjustment).
Offres : cible contient SELL ou BUY. Cross : modèle à part avec value_buy et value_sell.
"""
from decimal import Decimal
from typing import Union

from core.models import RateAdjustment, CrossRateAdjustment


def _candidate_targets(currency: str, country: str, trade_type: str) -> list[str]:
    """Cibles offres : XOF:BJ:SELL → XOF:SELL → SELL."""
    out = []
    if trade_type not in ("BUY", "SELL"):
        return out
    if currency:
        if country:
            out.append(f"{currency}:{country}:{trade_type}")
        out.append(f"{currency}:{trade_type}")
    out.append(trade_type)
    return out


def _cross_candidate_targets(from_currency: str, to_currency: str) -> list[str]:
    """Cibles cross : cross:FROM:TO, cross:FROM, cross."""
    out = []
    if from_currency and to_currency:
        out.append(f"cross:{from_currency}:{to_currency}")
    if from_currency:
        out.append(f"cross:{from_currency}")
    out.append("cross")
    return out


def apply_majoration(
    price: Union[float, str],
    currency: str = "",
    trade_type: str = "",
    country: str = "",
) -> float:
    """Applique la règle RateAdjustment (offres) la plus spécifique. SELL = majoration (v positif augmente le prix), BUY = minoration (v positif diminue le prix)."""
    value = Decimal(str(price))
    candidates = _candidate_targets(currency or "", country or "", trade_type or "")
    active = {r.target: r for r in RateAdjustment.objects.filter(active=True)}
    for target in candidates:
        if target in active:
            adj = active[target]
            v = Decimal(str(adj.value))
            minorer = trade_type == "BUY"
            if minorer:
                v = -v
            if adj.mode == RateAdjustment.MODE_PERCENT:
                value = value * (Decimal("1") + v / 100)
            else:
                value = value + v
            break
    return float(value)


def apply_cross_adjustment(
    price_buy: Union[float, str],
    price_sell: Union[float, str],
    from_currency: str,
    to_currency: str,
) -> float:
    """
    Applique la règle CrossRateAdjustment : ajustement sur le BUY (leg source) et sur le SELL (leg cible).
    rate = (price_sell après ajustement) / (price_buy après ajustement).
    """
    buy = Decimal(str(price_buy))
    sell = Decimal(str(price_sell))
    if buy <= 0:
        return float(sell) / float(buy) if buy else 0.0
    candidates = _cross_candidate_targets(from_currency or "", to_currency or "")
    active = {r.target: r for r in CrossRateAdjustment.objects.filter(active=True)}
    for target in candidates:
        if target in active:
            adj = active[target]
            if adj.mode == CrossRateAdjustment.MODE_PERCENT:
                buy = buy * (Decimal("1") + Decimal(str(adj.value_buy)) / 100)
                sell = sell * (Decimal("1") + Decimal(str(adj.value_sell)) / 100)
            else:
                buy = buy + Decimal(str(adj.value_buy))
                sell = sell + Decimal(str(adj.value_sell))
            break
    return float(sell / buy)
