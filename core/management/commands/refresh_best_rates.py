"""
Rafraîchit les 3 meilleurs taux (best rates) selon la config admin.

La fréquence est définie dans l'admin Django : Core > Config refresh best rates
(interval_minutes : 1, 5, 10, 15 ou 30 min). Le cron doit appeler cette commande
toutes les minutes ; la commande n'exécute le refresh que si l'intervalle configuré
est écoulé depuis last_run_at.

Déploiement (cron à lancer toutes les 1 min) :
  * * * * * cd /chemin/vers/usdt_aggregator && .venv/bin/python manage.py refresh_best_rates
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BestRatesRefreshConfig
from core.best_rates import refresh_best_rates

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rafraîchit les best rates si l'intervalle configuré (admin) est écoulé."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forcer l'exécution même si l'intervalle n'est pas écoulé.",
        )

    def handle(self, *args, **options):
        logger.info("refresh_best_rates: démarrage de la commande")
        config = BestRatesRefreshConfig.objects.first()
        if not config:
            config = BestRatesRefreshConfig.objects.create(interval_minutes=5, is_active=True)
            self.stdout.write("Config refresh créée (5 min, actif).")
            logger.info("refresh_best_rates: config créée (interval=%s min, actif)", config.interval_minutes)

        if not config.is_active:
            self.stdout.write("Refresh désactivé dans l'admin. Rien à faire.")
            logger.info("refresh_best_rates: ignoré (refresh désactivé dans l'admin)")
            return

        now = timezone.now()
        if not options["force"] and config.last_run_at:
            delta = now - config.last_run_at
            if delta.total_seconds() < config.interval_minutes * 60:
                remaining = config.interval_minutes * 60 - int(delta.total_seconds())
                self.stdout.write(f"Prochain refresh dans {remaining} s.")
                logger.info("refresh_best_rates: ignoré (intervalle non écoulé, prochain dans %s s)", remaining)
                return

        logger.info("refresh_best_rates: lancement du refresh (intervalle écoulé ou --force)")
        self.stdout.write("Rafraîchissement des meilleurs taux...")
        result = refresh_best_rates()
        config.last_run_at = now
        config.save(update_fields=["last_run_at"])
        logger.info("refresh_best_rates: terminé — updated=%s, errors=%s", result["updated"], len(result["errors"]))
        self.stdout.write(self.style.SUCCESS(f"Mis à jour: {result['updated']} enregistrements."))
        if result["errors"]:
            for err in result["errors"]:
                self.stderr.write(self.style.WARNING(err))
                logger.warning("refresh_best_rates: erreur — %s", err)
