# Guide pour tester le projet

## 1. Installer et lancer (première fois)

Ouvre un terminal dans le dossier du projet :

```bash
cd /Users/pc/usdt_aggregator

# Créer un environnement virtuel
python3 -m venv venv

# L'activer (Mac/Linux)
source venv/bin/activate

# Sur Windows : venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Créer la base de données (tables)
python manage.py migrate

# Créer un compte admin (pour le dashboard et l'API)
# Tu choisis : email ou username, et un mot de passe
python manage.py createsuperuser

# Lancer le serveur
python manage.py runserver
```

Le serveur tourne sur **http://127.0.0.1:8000/**.

---

## 2. Tester le Dashboard (HTML)

1. Ouvre **http://127.0.0.1:8000/dashboard/**  
   → Tu seras redirigé vers la page de connexion si tu n’es pas connecté.

2. Connecte-toi avec le compte **superuser** que tu viens de créer.

3. Tu peux tester :
   - **Accueil** : vue d’ensemble et lien vers les configs.
   - **Liquidité** : définir min/max pour BUY et SELL (ex. min 10, max 5000 USDT).
   - **Ajustements de taux** : ajouter un markup (ex. +2 % global).
   - **Plateformes** : voir Binance et cliquer sur « Définir par défaut ».

---

## 3. Tester l’API (avec de vraies offres Binance)

L’API exige une **authentification** (JWT ou clé API).

### Option A : JWT (token)

1. Récupérer un token (remplace `ton_username` et `ton_password`) :

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ton_username","password":"ton_password"}'
```

Tu reçois quelque chose comme : `{"access":"eyJ...", "refresh":"eyJ..."}`.

2. Utiliser le token pour appeler l’API (remplace `TON_TOKEN` par le `access` reçu) :

```bash
# Liste des offres USDT en XOF (vente)
curl "http://127.0.0.1:8000/api/v1/offers/?fiat=XOF&trade_type=SELL" \
  -H "Authorization: Bearer TON_TOKEN"

# Taux USDT pour le XOF
curl "http://127.0.0.1:8000/api/v1/rates/usdt/?fiat=XOF&trade_type=SELL" \
  -H "Authorization: Bearer TON_TOKEN"

# Taux croisé XOF → GHS
curl "http://127.0.0.1:8000/api/v1/rates/cross/?from_currency=XOF&to_currency=GHS" \
  -H "Authorization: Bearer TON_TOKEN"

# Pays disponibles pour le XOF
curl "http://127.0.0.1:8000/api/v1/xof-countries/" \
  -H "Authorization: Bearer TON_TOKEN"
```

### Option B : Clé API

1. Dans l’admin : **http://127.0.0.1:8000/admin/** → **Core** → **Clés API** → **Ajouter**.
2. Donne un nom (ex. "Test") et génère une clé :
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
   Colle le résultat dans le champ "Key", enregistre.

3. Appels avec la clé (remplace `TA_CLE_API`) :

```bash
curl "http://127.0.0.1:8000/api/v1/offers/?fiat=XOF&trade_type=SELL" \
  -H "X-API-Key: TA_CLE_API"
```

### Swagger (navigateur)

- Ouvre **http://127.0.0.1:8000/api/docs/**  
- Clique sur **Authorize** → JWT : saisis `Bearer TON_TOKEN` (ou seulement le token selon l’interface)  
- Tu peux tester chaque endpoint directement dans la page.

---

## 4. Tester sans Binance (mode Sandbox)

Si tu veux tester **sans appeler Binance** (données fictives) :

1. Lance le serveur avec la variable d’environnement :
   ```bash
   SANDBOX_API=1 python manage.py runserver
   ```
   Ou sur Windows (PowerShell) : `$env:SANDBOX_API="1"; python manage.py runserver`

2. Les mêmes appels API renverront des **données mock** (offres et taux factices). Les réponses contiendront `"sandbox": true`.

---

## 5. Ordre des tests recommandé

1. **migrate** + **createsuperuser** + **runserver**
2. Connexion au **dashboard** et config **Liquidité** (min/max)
3. **Swagger** : http://127.0.0.1:8000/api/docs/ → **Authorize** avec ton JWT → tester **GET /api/v1/offers/** avec `fiat=XOF`, `trade_type=SELL`
4. Tester **GET /api/v1/rates/usdt/** et **GET /api/v1/rates/cross/**
5. (Optionnel) **SANDBOX_API=1** pour vérifier que tout fonctionne sans réseau Binance

---

## Dépannage rapide

- **"Module not found"** → bien activer le venv (`source venv/bin/activate`) et refaire `pip install -r requirements.txt`.
- **401 Unauthorized** sur l’API → vérifier que le token est valide ou que la clé API est active.
- **Offres vides** → vérifier que la config liquidité (min/max) ne filtre pas tout ; ou tester avec `SANDBOX_API=1`.
