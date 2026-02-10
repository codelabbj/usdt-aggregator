import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings

from core.models import LiquidityConfig, OffersSnapshot
from core.majoration import apply_majoration
from platforms.registry import get_platform, get_default_platform, init_platforms

logger = logging.getLogger(__name__)

CACHE_OFFERS_PREFIX = "usdt_agg_offers"
CACHE_TTL = getattr(settings, "CACHE_OFFERS_TTL", 120)


def get_liquidity_bounds(trade_type: str) -> tuple:
    """Retourne (min, max ou None, require_inclusion, amount_in_fiat). amount_in_fiat=True => filtre sur min_fiat/max_fiat, False => min_usdt/max_usdt."""
    try:
        conf = LiquidityConfig.objects.get(trade_type=trade_type, active=True)
        min_a = float(conf.min_amount)
        max_a = float(conf.max_amount) if conf.max_amount else None
        require_inclusion = getattr(conf, "require_inclusion", False)
        amount_in_fiat = getattr(conf, "amount_in_fiat", True)
        return (min_a, max_a, require_inclusion, amount_in_fiat)
    except LiquidityConfig.DoesNotExist:
        return (0.0, None, False, True)


def get_offers_from_snapshot(
    platform_code: str,
    fiat: str,
    trade_type: str,
    country: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lit la liste d'offres brutes depuis OffersSnapshot (refresh = source de vérité)."""
    try:
        snap = OffersSnapshot.objects.get(
            platform=platform_code,
            fiat=fiat,
            trade_type=trade_type,
            country=country or "",
        )
        return list(snap.data) if isinstance(snap.data, list) else []
    except OffersSnapshot.DoesNotExist:
        return []


def filter_by_liquidity(offers: List[Dict], trade_type: str) -> List[Dict]:
    """Filtre par min/max selon amount_in_fiat (fiat => min_fiat/max_fiat, usdt => min_usdt/max_usdt). Puis inclusion ou chevauchement selon require_inclusion."""
    min_a, max_a, require_inclusion, amount_in_fiat = get_liquidity_bounds(trade_type)
    out = []
    for o in offers:
        try:
            if amount_in_fiat:
                o_min = float(o.get("min_fiat") or 0)
                o_max = float(o.get("max_fiat") or 0)
            else:
                o_min = float(o.get("min_usdt") or 0)
                o_max = float(o.get("max_usdt") or 0)
        except (TypeError, ValueError):
            continue
        if require_inclusion:
            # Inclusion : [o_min, o_max] doit être inclus dans [min_a, max_a]
            if o_min < min_a:
                continue
            if max_a is not None and o_max > max_a:
                continue
        else:
            # Chevauchement : intersection non vide
            if o_max < min_a:
                continue
            if max_a is not None and o_min > max_a:
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
    """Récupère les offres : si USE_REFRESH_AS_SOURCE, lit OffersSnapshot ; sinon plateforme (et cache). Puis filtre liquidité + ajustement."""
    init_platforms()
    platform = get_platform(platform_code or "") or get_default_platform()
    if not platform:
        logger.warning("fetch_offers: aucune plateforme (code=%s)", platform_code or "default")
        return []
    code = platform.code

    use_refresh = getattr(settings, "USE_REFRESH_AS_SOURCE", False)
    if use_refresh:
        offers = get_offers_from_snapshot(code, fiat, trade_type, country)
        logger.debug("fetch_offers: snapshot %s %s %s %s → %s offres", code, fiat, country or "all", trade_type, len(offers))
    else:
        cache_key = f"{CACHE_OFFERS_PREFIX}:{code}:{asset}:{fiat}:{trade_type}:{country or 'all'}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug("fetch_offers: cache hit %s %s %s %s", code, fiat, country or "all", trade_type)
                offers = cached
            else:
                offers = _fetch_offers_with_fallback(platform, platform_code, asset, fiat, trade_type, country)
                cache.set(cache_key, offers, CACHE_TTL)
        else:
            offers = _fetch_offers_with_fallback(platform, platform_code, asset, fiat, trade_type, country)
    before_liquidity = len(offers)
    offers = filter_by_liquidity(offers, trade_type)
    logger.debug(
        "fetch_offers: %s %s %s %s — brut=%s, après liquidité=%s",
        code, fiat, country or "all", trade_type, before_liquidity, len(offers),
    )
    for o in offers:
        raw_price = o.get("price") or 0
        o["adjusted_price"] = apply_majoration(
            raw_price, fiat, trade_type, o.get("country") or country or ""
        )
    # Meilleure offre en premier : BUY = prix le plus bas, SELL = prix le plus haut
    def _price(o):
        return float(o.get("adjusted_price") or o.get("price") or 0)
    offers.sort(key=_price, reverse=(trade_type == "SELL"))
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
            logger.debug("fetch_offers: appel plateforme %s fiat=%s country=%s trade_type=%s", p.code, fiat, country or "all", trade_type)
            offers = p.fetch_offers(asset=asset, fiat=fiat, trade_type=trade_type, country=country)
            if offers is not None:
                logger.info("fetch_offers: %s → %s offres", p.code, len(offers or []))
                return offers or []
        except Exception as e:
            logger.warning("fetch_offers: %s a échoué — %s", p.code, e)
            continue
    logger.warning("fetch_offers: toutes les plateformes ont échoué (fiat=%s %s)", fiat, trade_type)
    return []


def fetch_offers_raw(
    asset: str = "USDT",
    fiat: str = "XOF",
    trade_type: str = "SELL",
    country: Optional[str] = None,
    platform_code: Optional[str] = None,
    use_cache: bool = False,
) -> List[Dict[str, Any]]:
    """
    Récupère les offres brutes (plateforme uniquement).
    N'applique ni la config liquidité ni les ajustements de taux.
    Utilisé par le refresh périodique (best rates).
    """
    init_platforms()
    platform = get_platform(platform_code or "") or get_default_platform()
    if not platform:
        logger.warning("fetch_offers_raw: aucune plateforme (code=%s)", platform_code or "default")
        return []
    cache_key = f"{CACHE_OFFERS_PREFIX}_raw:{platform.code}:{asset}:{fiat}:{trade_type}:{country or 'all'}" if use_cache else None
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    offers = _fetch_offers_with_fallback(platform, platform_code, asset, fiat, trade_type, country)
    if use_cache and cache_key and offers:
        cache.set(cache_key, offers, CACHE_TTL)
    return offers
