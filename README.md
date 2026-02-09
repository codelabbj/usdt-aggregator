# USDT Aggregator – Django

Agrégation des offres P2P USDT (XOF, GHS, XAF), filtrage par liquidité, ajustement des taux (markup/markdown), calcul des taux croisés, API REST sécurisée et dashboard HTML.

## Installation

```bash
cd usdt_aggregator
python3 -m venv venv
source venv/bin/activate   # ou `venv\Scripts\activate` sur Windows
pip install -r requirements.txt
```

## Base de données et cache

- **DB** : SQLite par défaut (`db.sqlite3`). Pour PostgreSQL, modifier `DATABASES` dans `usdt_aggregator/settings.py`.
- **Redis** : optionnel. Si Redis n’est pas disponible, le cache Django utilisera un fallback en mémoire (configurable). Pour Redis : `REDIS_URL=redis://127.0.0.1:6379/1`.

## Lancement

```bash
python manage.py migrate
python manage.py createsuperuser   # pour accéder au dashboard et à l’admin
python manage.py runserver
```

- **Dashboard (HTML)** : http://127.0.0.1:8000/dashboard/ (réservé au staff)
- **Admin Django** : http://127.0.0.1:8000/admin/
- **API Swagger** : http://127.0.0.1:8000/api/docs/
- **Schéma OpenAPI** : http://127.0.0.1:8000/api/schema/

## API REST (v1)

- Authentification : JWT via `POST /api/v1/auth/token/` (username + password) puis `Authorization: Bearer <token>`.
- **GET /api/v1/offers/** – Offres filtrées (query: `fiat`, `trade_type`, `country`, `platform`).
- **GET /api/v1/best-rates/** – Meilleurs taux USDT/fiat (alimenté par le refresh périodique ; query: `fiat`, `trade_type`, `country`).
- **GET /api/v1/rates/cross/** – Taux croisé (query: `from_currency`, `to_currency` ; utilise les best rates).
- **GET /api/v1/platforms/** – Liste des plateformes.

## Spécifications couvertes

Voir **SPECS_CONFORMITE.md** pour le détail point par point.

- **1. Offres Buy/Sell** – XOF, GHS, XAF ; segmentation par pays pour XOF (`country` + `GET /api/v1/xof-countries/`).
- **2. Filtrage liquidité** – Min/max BUY/SELL dans le dashboard ; exclusion automatique.
- **3. Ajustement des taux** – % ou montant fixe ; global, par devise, pays (XOF), type d’offre.
- **4. Taux croisés** – Calcul automatique, cache, historique.
- **5. API** – REST, versionnée, **JWT + API Key**, Swagger/OpenAPI.
- **6. Multi-plateformes** – Binance par défaut ; choix de la plateforme par défaut dans le dashboard.
- **7. Compléments** – Cache Redis, logs et alerte variation > 10 %, fallback plateforme, historique des taux, mode sandbox (`SANDBOX_API=1`), fuseaux.

## Déploiement – Rafraîchissement des best rates

La fréquence de refresh des meilleurs taux se configure dans **Admin Django** :  
**Core > Config refresh best rates** (intervalle : 1, 5, 10, 15 ou 30 min ; actif/inactif).

Sur le serveur, configurer un **cron** qui appelle la commande **toutes les minutes** (la commande n’exécute le refresh que si l’intervalle configuré est écoulé) :

```bash
* * * * * cd /chemin/vers/usdt_aggregator && .venv/bin/python manage.py refresh_best_rates
```

Remplacer `/chemin/vers/usdt_aggregator` par le chemin réel du projet et `.venv` par le nom du venv si différent. Pour forcer un refresh immédiat sans attendre l’intervalle : `python manage.py refresh_best_rates --force`.

## Structure

- `core` – Modèles : liquidité, ajustements, plateformes (config), config refresh best rates.
- `platforms` – Récupération offres (Binance P2P API interne), registry pour ajouter d’autres plateformes.
- `offers` – Filtrage liquidité, application des ajustements, cache.
- `rates` – Calcul des taux croisés.
- `api` – Endpoints REST v1, JWT, Swagger.
- `dashboard` – Pages HTML (config liquidité, ajustements, plateformes).
