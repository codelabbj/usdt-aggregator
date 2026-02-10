"""
Script pour récupérer les données du taux croisé (ex. XOF → GHS) et vérifier le calcul.

Utilisation:
  python manage.py check_cross_rate
  python manage.py check_cross_rate XOF GHS
  python manage.py check_cross_rate XOF GHS --country_from BJ --country_to GH

Résumé:
  - Taux croisé 1 from_currency = X to_currency via USDT.
  - On prend la meilleure offre BUY pour la devise source (XOF) : prix = XOF pour 1 USDT (meilleur = plus bas).
  - On prend la meilleure offre SELL pour la devise cible (GHS) : prix = GHS pour 1 USDT (meilleur = plus haut).
  - Formule: rate = price_sell_to / price_buy_from  →  1 XOF = rate GHS.

Si une des deux listes d'offres est vide (snapshot ou live), le taux n'est pas disponible (API renvoie 404).
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from offers.services import get_offers_from_snapshot, fetch_offers_raw
from core.majoration import apply_cross_adjustment
from platforms.registry import get_default_platform, init_platforms


class Command(BaseCommand):
    help = "Vérifie le calcul du taux croisé (ex. XOF → GHS) en affichant les données récupérées."

    def add_arguments(self, parser):
        parser.add_argument("from_currency", nargs="?", default="XOF", help="Devise source (ex. XOF)")
        parser.add_argument("to_currency", nargs="?", default="GHS", help="Devise cible (ex. GHS)")
        parser.add_argument("--country_from", default="", help="Pays devise source (vide = tous)")
        parser.add_argument("--country_to", default="", help="Pays devise cible (vide = tous)")

    def handle(self, *args, **options):
        from_c = (options.get("from_currency") or "XOF").strip().upper()
        to_c = (options.get("to_currency") or "GHS").strip().upper()
        country_from = (options.get("country_from") or "").strip() or None
        country_to = (options.get("country_to") or "").strip() or None

        self.stdout.write("=" * 60)
        self.stdout.write(f"Taux croisé : 1 {from_c} = ? {to_c} (via USDT)")
        self.stdout.write("=" * 60)

        if from_c == to_c:
            self.stdout.write(self.style.SUCCESS("Même devise → rate = 1.0"))
            return

        use_refresh = getattr(settings, "USE_REFRESH_AS_SOURCE", False)
        self.stdout.write(f"\n1) Source des offres : {'OffersSnapshot (refresh)' if use_refresh else 'Appel direct plateforme (live)'}")

        init_platforms()
        platform = get_default_platform()
        code = platform.code if platform else None

        if use_refresh and not code:
            self.stdout.write(self.style.ERROR("Aucune plateforme par défaut → pas d'offres."))
            self.stdout.write("   Le taux XOF → GHS sera donc non disponible (vide).")
            return

        # Récupérer offres FROM (devise source) : BUY = "vendre USDT contre from_c"
        if use_refresh and code:
            offers_from = get_offers_from_snapshot(code, from_c, "BUY", country_from)
        else:
            offers_from = fetch_offers_raw(
                asset="USDT", fiat=from_c, trade_type="BUY",
                country=country_from, platform_code=code, use_cache=False,
            )
        for o in offers_from:
            o.setdefault("fiat", from_c)

        # Récupérer offres TO (devise cible) : SELL = "vendre USDT contre to_c"
        if use_refresh and code:
            offers_to = get_offers_from_snapshot(code, to_c, "SELL", country_to)
        else:
            offers_to = fetch_offers_raw(
                asset="USDT", fiat=to_c, trade_type="SELL",
                country=country_to, platform_code=code, use_cache=False,
            )
        for o in offers_to:
            o.setdefault("fiat", to_c)

        self.stdout.write(f"\n2) Offres {from_c} BUY (combien de {from_c} pour 1 USDT) : {len(offers_from)} offre(s)")
        if not offers_from:
            self.stdout.write(self.style.WARNING(f"   Aucune offre → le taux {from_c} → {to_c} ne peut pas être calculé (réponse API = 404 / vide)."))
            self.stdout.write("   Vérifier que le refresh a bien rempli le snapshot pour cette devise/type/pays.")
            return
        offers_from_sorted = sorted(offers_from, key=lambda x: (x.get("price") or 0))
        best_from = offers_from_sorted[0]
        price_buy_from = float(best_from.get("price") or 0)
        self.stdout.write(f"   Meilleure (prix le plus bas) : price = {price_buy_from}")

        self.stdout.write(f"\n3) Offres {to_c} SELL (combien de {to_c} pour 1 USDT) : {len(offers_to)} offre(s)")
        if not offers_to:
            self.stdout.write(self.style.WARNING(f"   Aucune offre → le taux {from_c} → {to_c} ne peut pas être calculé (réponse API = 404 / vide)."))
            self.stdout.write("   Vérifier que le refresh a bien rempli le snapshot pour cette devise/type/pays.")
            return
        offers_to_sorted = sorted(offers_to, key=lambda x: (x.get("price") or 0), reverse=True)
        best_to = offers_to_sorted[0]
        price_sell_to = float(best_to.get("price") or 0)
        self.stdout.write(f"   Meilleure (prix le plus haut) : price = {price_sell_to}")

        if price_buy_from <= 0:
            self.stdout.write(self.style.ERROR("   price_buy_from <= 0 → taux non disponible."))
            return

        # Calcul brut : 1 from_c = (price_sell_to / price_buy_from) to_c
        rate_brut = price_sell_to / price_buy_from
        self.stdout.write(f"\n4) Calcul brut : rate = price_sell_to / price_buy_from = {price_sell_to} / {price_buy_from} = {rate_brut:.8f}")

        rate_ajuste = apply_cross_adjustment(price_buy_from, price_sell_to, from_c, to_c)
        self.stdout.write(f"5) Après ajustement cross (admin) : rate = {rate_ajuste}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Résultat : 1 {from_c} = {rate_ajuste:.8f} {to_c}"))
        self.stdout.write("")
        self.stdout.write("Si tu recevais « vide » ou pas de montant côté client, vérifier :")
        self.stdout.write("  - que USE_REFRESH_AS_SOURCE est cohérent (True = lire OffersSnapshot) ;")
        self.stdout.write("  - que le refresh a bien tourné pour (XOF, BUY) et (GHS, SELL) ;")
        self.stdout.write("  - que les devises/pays sont bien configurés dans l'admin (Core > Devises / Pays).")
