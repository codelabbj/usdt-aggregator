import logging
from decimal import Decimal
from typing import Dict, Optional, List
from django.core.cache import cache

from offers.services import fetch_offers
from offers.models import RateHistory

logger = logging.getLogger(__name__)

CACHE_RATE_PREFIX = "usdt_agg_rate"
CACHE_RATE_TTL = 60


def _platform_code() -> str:
    from platforms.registry import get_default_platform
    p = get_default_platform()
    return p.code if p else "unknown"


def get_best_usdt_rate(fiat: str, trade_type: str, country: Optional[str] = None) -> Optional[float]:
    """
    Retourne le meilleur taux USDT/fiat. BUY = prix le plus bas ; SELL = prix le plus haut.
    Si USE_REFRESH_AS_SOURCE : on lit les offres (snapshot) via fetch_offers, pas BestRate.
    Sinon : BestRate puis fallback fetch_offers.
    """
    from django.conf import settings
    from core.models import BestRate

    use_refresh = getattr(settings, "USE_REFRESH_AS_SOURCE", False)
    if not use_refresh:
        qs = BestRate.objects.filter(fiat=fiat, trade_type=trade_type)
        if country:
            qs = qs.filter(country=country)
        if trade_type == "SELL":
            best = qs.order_by("-rate").first()
        else:
            best = qs.order_by("rate").first()
        if best is not None:
            return float(best.rate)

    # Source = snapshot (refresh) ou fallback : fetch offres et prendre la meilleure
    offers = fetch_offers(asset="USDT", fiat=fiat, trade_type=trade_type, country=country, use_cache=True)
    if not offers:
        return None
    prices = [o.get("adjusted_price") or o.get("price") or 0 for o in offers if (o.get("adjusted_price") or o.get("price"))]
    if not prices:
        return None
    if trade_type == "SELL":
        return max(prices)
    return min(prices)


def get_usdt_rate(fiat: str, trade_type: str, country: Optional[str] = None) -> Optional[float]:
    """Taux moyen 1 USDT = X fiat (pour SELL) ou 1 fiat = X USDT (pour BUY)."""
    offers = fetch_offers(asset="USDT", fiat=fiat, trade_type=trade_type, country=country, use_cache=True)
    if not offers:
        return None
    prices = [o.get("adjusted_price") or o.get("price") or 0 for o in offers]
    rate = sum(prices) / len(prices) if prices else None
    if rate is not None:
        try:
            RateHistory.objects.create(
                source_currency=fiat,
                target_currency="USDT",
                rate=rate,
                trade_type=trade_type,
                platform=_platform_code(),
                country=country or "",
            )
            _log_rate_variation(fiat, "USDT", rate, trade_type, country)
        except Exception:
            pass
    return rate


def compute_cross_rate(
    from_currency: str,
    to_currency: str,
    country_from: Optional[str] = None,
    country_to: Optional[str] = None,
) -> Optional[float]:
    """
    Taux croisé from_currency → to_currency via USDT.
    Retourne : 1 from_currency = X to_currency.
    Si pays indiqué et pas de taux pour ce pays → None (404). Pas de fallback tous pays.
    """
    if from_currency == to_currency:
        return 1.0
    key = f"{CACHE_RATE_PREFIX}:cross:{from_currency}:{to_currency}:{country_from or ''}:{country_to or ''}"
    cached = cache.get(key)
    if cached is not None:
        return float(cached)

    rate_buy_from = get_best_usdt_rate(from_currency, "BUY", country_from)
    rate_sell_to = get_best_usdt_rate(to_currency, "SELL", country_to)
    if rate_buy_from is None or rate_sell_to is None or rate_buy_from == 0:
        return None

    cross = rate_sell_to / rate_buy_from
    cross = round(float(cross), 8)
    cache.set(key, str(cross), CACHE_RATE_TTL)
    try:
        RateHistory.objects.create(
            source_currency=from_currency,
            target_currency=to_currency,
            rate=cross,
            trade_type="BUY",
            platform=_platform_code(),
            country=country_from or "",
        )
        _log_rate_variation(from_currency, to_currency, cross, "BUY", country_from)
    except Exception:
        pass
    return cross


def _log_rate_variation(source: str, target: str, rate: float, trade_type: str, country: Optional[str] = None):
    """Log du taux pour monitoring ; alerte si variation anormale vs dernier taux."""
    logger.info("rate_computed %s/%s=%.8f trade_type=%s country=%s", source, target, rate, trade_type, country or "")
    try:
        last = RateHistory.objects.filter(
            source_currency=source, target_currency=target, trade_type=trade_type
        ).exclude(rate=0).order_by("-created_at").values_list("rate", flat=True)[:2]
        last = list(last)
        if len(last) >= 2 and last[1]:
            prev = float(last[1])
            pct = abs(rate - prev) / prev * 100 if prev else 0
            if pct > 10:
                logger.warning("rate_variation_alert %s/%s %.2f%% (%.4f -> %.4f)", source, target, pct, prev, rate)
    except Exception:
        pass
