"""
Agrégation des meilleures offres et stockage des meilleurs taux USDT/fiat
par devise, type (BUY/SELL), pays et plateforme.
country="" = tous les pays (global) ; sinon code pays (ex. BJ, CI).
À lancer à intervalle régulier (cron).
"""
import logging
from decimal import Decimal

from core.constants import SUPPORTED_FIAT, FIAT_COUNTRIES
from core.models import BestRate
from offers.services import fetch_offers
from platforms.registry import init_platforms, get_all_platforms

logger = logging.getLogger(__name__)


def _country_list_for_fiat(fiat: str):
    """Retourne [""] (global = tous les pays) puis les codes pays pour la devise."""
    result = [""]
    for code, _ in FIAT_COUNTRIES.get(fiat, [("", "Global")]):
        if code:
            result.append(code)
    return result


def refresh_best_rates() -> dict:
    """
    Récupère les offres pour chaque (plateforme, devise, pays, BUY/SELL),
    calcule les 3 meilleurs taux et les enregistre. country="" = sans filtre pays.
    Meilleur SELL = prix le plus élevé ; meilleur BUY = prix le plus bas.
    """
    init_platforms()
    platforms = get_all_platforms()
    if not platforms:
        logger.warning("Aucune plateforme enregistrée.")
        return {"updated": 0, "errors": ["Aucune plateforme"]}

    updated = 0
    errors = []

    for platform_code, platform in platforms.items():
        for fiat in SUPPORTED_FIAT:
            for country in _country_list_for_fiat(fiat):
                country_param = country if country else None
                for trade_type in ("BUY", "SELL"):
                    try:
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

                    except Exception as e:
                        msg = f"{platform_code} {fiat} {country or 'all'} {trade_type}: {e}"
                        errors.append(msg)
                        logger.exception(msg)

    return {"updated": updated, "errors": errors}
