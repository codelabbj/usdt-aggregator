from decimal import Decimal
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings

from core.models import LiquidityConfig
from core.majoration import apply_majoration
from platforms.registry import get_platform, get_default_platform, init_platforms


CACHE_OFFERS_PREFIX = "usdt_agg_offers"
CACHE_TTL = getattr(settings, "CACHE_OFFERS_TTL", 120)


def get_liquidity_bounds(trade_type: str) -> tuple:
    try:
        conf = LiquidityConfig.objects.get(trade_type=trade_type, active=True)
        min_a = conf.min_amount
        max_a = conf.max_amount
        return (float(min_a), float(max_a) if max_a else None)
    except LiquidityConfig.DoesNotExist:
        return (0, None)


def filter_by_liquidity(offers: List[Dict], trade_type: str) -> List[Dict]:
    min_a, max_a = get_liquidity_bounds(trade_type)
    out = []
    for o in offers:
        avail = o.get("available_amount") or o.get("max_amount") or 0
        try:
            avail = float(avail)
        except (TypeError, ValueError):
            continue
        if avail < min_a:
            continue
        if max_a is not None and avail > max_a:
            continue
        out.append(o)
    return out


def fetch_offers(
    asset: str = "USDT",
    fiat: str = "XOF",
    trade_type: str = "SELL",
    country: Optional[str] = None,
    platform_code: Optional[str] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Récupère les offres avec fallback automatique si la plateforme ne répond pas."""
    init_platforms()
    platform = get_platform(platform_code or "") or get_default_platform()
    if not platform:
        return []
    cache_key = f"{CACHE_OFFERS_PREFIX}:{platform.code}:{asset}:{fiat}:{trade_type}:{country or 'all'}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            offers = cached
        else:
            offers = _fetch_offers_with_fallback(platform, platform_code, asset, fiat, trade_type, country)
            cache.set(cache_key, offers, CACHE_TTL)
    else:
        offers = _fetch_offers_with_fallback(platform, platform_code, asset, fiat, trade_type, country)
    offers = filter_by_liquidity(offers, trade_type)
    for o in offers:
        raw_price = o.get("price") or 0
        o["adjusted_price"] = apply_majoration(
            raw_price, fiat, trade_type, o.get("country") or country or ""
        )
    return offers


def _fetch_offers_with_fallback(
    platform, platform_code, asset, fiat, trade_type, country
) -> List[Dict[str, Any]]:
    """Appelle la plateforme ; en cas d'échec, essaie les autres (fallback)."""
    from platforms.registry import get_all_platforms
    to_try = [platform]
    if not platform_code:
        for code, p in get_all_platforms().items():
            if p is not platform:
                to_try.append(p)
    for p in to_try:
        try:
            offers = p.fetch_offers(asset=asset, fiat=fiat, trade_type=trade_type, country=country)
            if offers is not None:
                return offers or []
        except Exception:
            continue
    return []
