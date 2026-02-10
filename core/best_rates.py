"""
Refresh = seule source de vérité.
Récupère les offres brutes (plateforme) et les enregistre telles quelles dans OffersSnapshot.
Aucun calcul : pas de tri top 3, pas de BestRate, pas de config ni ajustement.
Les APIs lisent OffersSnapshot puis appliquent config liquidité + ajustements.
"""
import logging

from core.models import Currency, Country, OffersSnapshot
from offers.services import fetch_offers_raw
from platforms.registry import init_platforms, get_all_platforms

logger = logging.getLogger(__name__)


def _country_list_for_fiat(fiat: str):
    """Retourne [""] (global) puis les codes pays actifs pour cette devise (depuis la BDD)."""
    result = [""]
    for code in Country.objects.filter(currency__code=fiat, active=True).order_by("order", "code").values_list("code", flat=True):
        result.append(code)
    return result


def refresh_best_rates() -> dict:
    """
    Récupère les offres brutes pour chaque (plateforme, devise, pays, BUY/SELL)
    et les enregistre dans OffersSnapshot. Aucun calcul.
    """
    init_platforms()
    platforms = get_all_platforms()
    if not platforms:
        logger.warning("Aucune plateforme enregistrée.")
        return {"updated": 0, "errors": ["Aucune plateforme"]}

    supported_fiat = list(Currency.objects.filter(active=True).order_by("order", "code").values_list("code", flat=True))
    if not supported_fiat:
        logger.warning("Aucune devise active dans l'admin (Core > Devises).")
        return {"updated": 0, "errors": ["Aucune devise active"]}

    logger.info("refresh_best_rates: plateformes=%s, devises=%s", list(platforms.keys()), supported_fiat)
    updated = 0
    errors = []

    for platform_code, platform in platforms.items():
        for fiat in supported_fiat:
            for country in _country_list_for_fiat(fiat):
                country_param = country if country else None
                for trade_type in ("BUY", "SELL"):
                    country_label = country or "all"
                    try:
                        logger.debug(
                            "refresh_best_rates: fetch %s %s %s %s",
                            platform_code, fiat, country_label, trade_type,
                        )
                        offers = fetch_offers_raw(
                            asset="USDT",
                            fiat=fiat,
                            trade_type=trade_type,
                            country=country_param,
                            platform_code=platform_code,
                            use_cache=False,
                        )
                        snapshot, _ = OffersSnapshot.objects.update_or_create(
                            platform=platform_code,
                            fiat=fiat,
                            trade_type=trade_type,
                            country=country or "",
                            defaults={"data": offers},
                        )
                        updated += 1
                        logger.info(
                            "refresh_best_rates: %s %s %s %s — %s offres enregistrées",
                            platform_code, fiat, country_label, trade_type, len(offers),
                        )
                    except Exception as e:
                        msg = f"{platform_code} {fiat} {country or 'all'} {trade_type}: {e}"
                        errors.append(msg)
                        logger.exception("refresh_best_rates: %s", msg)

    logger.info("refresh_best_rates: fin — total snapshots=%s, errors=%s", updated, len(errors))
    return {"updated": updated, "errors": errors}
