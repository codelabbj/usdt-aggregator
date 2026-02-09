"""
Agrégation des meilleures offres et stockage des meilleurs taux USDT/fiat
par devise, type (BUY/SELL), pays et plateforme.
Les devises et pays viennent de l'admin (modèles Currency et Country).
country="" = tous les pays (global) ; sinon code pays (ex. BJ, CI).
À lancer à intervalle régulier (cron).
"""
import logging
from decimal import Decimal

from core.models import BestRate, Currency, Country
from offers.services import fetch_offers
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
    Récupère les offres pour chaque (plateforme, devise, pays, BUY/SELL),
    calcule les 3 meilleurs taux et les enregistre.
    Devises et pays = ceux actifs dans l'admin (Currency, Country).
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
                        offers = fetch_offers(
                            asset="USDT",
                            fiat=fiat,
                            trade_type=trade_type,
                            country=country_param,
                            platform_code=platform_code,
                            use_cache=False,
                        )
                        key = lambda o: (o.get("adjusted_price") or o.get("price") or 0)
                        offers = sorted(offers, key=key, reverse=(trade_type == "SELL"))
                        top3 = offers[:3]

                        BestRate.objects.filter(
                            fiat=fiat,
                            trade_type=trade_type,
                            country=country,
                            platform=platform_code,
                        ).delete()

                        for offer in top3:
                            rate = offer.get("adjusted_price") or offer.get("price") or 0
                            BestRate.objects.create(
                                fiat=fiat,
                                trade_type=trade_type,
                                country=country,
                                platform=platform_code,
                                rate=Decimal(str(rate)),
                            )
                            updated += 1

                        logger.info(
                            "refresh_best_rates: %s %s %s %s — %s offres → top 3 enregistrés",
                            platform_code, fiat, country_label, trade_type, len(offers),
                        )
                    except Exception as e:
                        msg = f"{platform_code} {fiat} {country or 'all'} {trade_type}: {e}"
                        errors.append(msg)
                        logger.exception("refresh_best_rates: %s", msg)

    logger.info("refresh_best_rates: fin — total updated=%s, errors=%s", updated, len(errors))
    return {"updated": updated, "errors": errors}
