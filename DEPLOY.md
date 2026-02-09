# Déploiement USDT Aggregator sur un serveur

Guide pas à pas pour déployer l’application en production (Linux).

---

## 1. Prérequis sur le serveur

- **OS** : Linux (Ubuntu 22.04 / Debian 12 par exemple).
- **Python** : 3.10 ou 3.11.
- **Optionnel** : Redis (pour le cache), Nginx (reverse proxy).

```bash
# Exemple Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
# Optionnel
sudo apt install -y redis-server nginx
```

---

## 2. Récupérer le code

Cloner le dépôt ou copier les fichiers sur le serveur (ex. dans `/var/www/usdt_aggregator` ou `/home/deploy/usdt_aggregator`).

```bash
cd /var/www
sudo git clone <url-du-repo> usdt_aggregator
# ou scp/rsync depuis ta machine
cd usdt_aggregator
```

---

## 3. Environnement virtuel et dépendances

**Exécuter les commandes ci‑dessous avec l’utilisateur qui fera tourner l’app (pas en `sudo`)** : sinon le venv sera propriété de root et tu n’auras pas les droits pour l’utiliser.

Si tu as **Permission denied** en créant le venv, le répertoire du projet appartient sans doute à root. À faire **une fois** (en root ou avec sudo) pour donner la propriété à ton utilisateur (remplace `classified` par ton user si besoin) :
```bash
sudo chown -R classified:classified /var/www/usdt_aggregator
```
Ensuite, **sans sudo** :
```bash
cd /var/www/usdt_aggregator
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Si tu as déjà créé le venv en root par erreur, reprendre uniquement la propriété du venv :
```bash
sudo chown -R classified:classified /var/www/usdt_aggregator/.venv
```

---

## 4. Variables d’environnement (production)

Créer un fichier `.env` à la racine du projet (ou exporter les variables dans le système / le service qui lance Gunicorn).

**À faire absolument :**

| Variable | Exemple | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | Chaîne longue aléatoire | Obligatoire en prod (générer une nouvelle clé). |
| `DEBUG` | `0` | Mettre à `0` en production. |
| `ALLOWED_HOSTS` | `exchange.pals.africa,82.29.179.215` | Host(s) autorisé(s) : sous-domaine ou IP. Plusieurs valeurs séparées par des virgules. |

**Optionnel :**

| Variable | Exemple | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://127.0.0.1:6379/1` | Cache Redis (sinon cache mémoire). |
| `DEFAULT_P2P_PLATFORM` | `binance` | Plateforme P2P par défaut. |
| `TIMEZONE_DISPLAY` | `Africa/Abidjan` | Fuseau affiché. |
| `SANDBOX_API` | `0` | `0` en prod pour les vrais taux. |

Exemple `.env` minimal en prod :

```bash
# .env (ne pas commiter, ajouter à .gitignore si besoin)
DEBUG=0
ALLOWED_HOSTS=exchange.pals.africa,82.29.179.215
DJANGO_SECRET_KEY=genere-une-longue-cle-aleatoire-ici
```

Pour charger le `.env` automatiquement, tu peux utiliser `django-environ` dans `settings.py` ou exporter les variables avant de lancer Gunicorn (voir plus bas).

---

## 5. Base de données et migrations

Par défaut le projet utilise **SQLite** (`db.sqlite3`). En production légère, ça suffit. Pour plus de charge, passer à **PostgreSQL** (adapter `DATABASES` dans `settings.py` et installer `psycopg2`).

```bash
source .venv/bin/activate
cd /var/www/usdt_aggregator
export DEBUG=0
export ALLOWED_HOSTS=exchange.pals.africa,82.29.179.215
export DJANGO_SECRET_KEY=ta-secret-key

python manage.py migrate
python manage.py createsuperuser   # pour admin + dashboard
```

---

## 6. Fichiers statiques (si tu sers les static Django)

```bash
python manage.py collectstatic --noinput
```

Le répertoire `staticfiles/` sera utilisé par Nginx (ou par WhiteNoise si tu l’ajoutes). Sans Nginx, Gunicorn ne sert pas les static en prod ; il vaut mieux un reverse proxy.

---

## 7. Lancer l’application avec Gunicorn

Ne pas utiliser `runserver` en production. Utiliser **Gunicorn** :

```bash
source .venv/bin/activate
cd /var/www/usdt_aggregator

export DEBUG=0
export ALLOWED_HOSTS=exchange.pals.africa,82.29.179.215
export DJANGO_SECRET_KEY=ta-secret-key

gunicorn usdt_aggregator.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

Pour la prod, il vaut mieux lancer Gunicorn via **systemd** (voir section 9).

---

## 8. Cron : refresh des best rates

Pour que les meilleurs taux se mettent à jour selon l’intervalle configuré dans le dashboard :

```bash
crontab -e
```

Ajouter une ligne (adapter le chemin et le venv) :

```cron
* * * * * cd /var/www/usdt_aggregator && .venv/bin/python manage.py refresh_best_rates
```

La fréquence réelle du refresh (1, 5, 10, 15 ou 30 min) se règle dans le **Dashboard > Refresh taux** ou dans l’**admin Django**.

---

## 9. Service systemd (recommandé)

Créer un fichier service pour que l’app tourne en permanence et redémarre après un crash.

Fichier : `/etc/systemd/system/usdt-aggregator.service`

```ini
[Unit]
Description=USDT Aggregator Gunicorn
After=network.target

[Service]
Type=simple
User=classified
Group=classified
WorkingDirectory=/var/www/usdt_aggregator
Environment=PATH=/var/www/usdt_aggregator/.venv/bin
EnvironmentFile=/var/www/usdt_aggregator/.env
ExecStart=/var/www/usdt_aggregator/.venv/bin/gunicorn usdt_aggregator.wsgi:application --bind 127.0.0.1:8000 --workers 2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- `User=classified` / `Group=classified` : même utilisateur que le propriétaire du projet (comme ton déploiement Connect Pro). Si tu préfères faire tourner sous `www-data`, change et assure-toi que ce user a les droits sur `/var/www/usdt_aggregator` et le `.venv`.
- `EnvironmentFile` : charge le `.env` (DEBUG, ALLOWED_HOSTS, DJANGO_SECRET_KEY, etc.) avant de lancer Gunicorn.
- Logs : `journalctl -u usdt-aggregator -f` pour suivre en direct.

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable usdt-aggregator
sudo systemctl start usdt-aggregator
sudo systemctl status usdt-aggregator
```

---

## 10. Nginx (reverse proxy, optionnel mais recommandé)

Nginx écoute sur 80/443 et envoie les requêtes à Gunicorn (port 8000). Même style que ton déploiement Connect Pro (favicon, cache static, HTTPS avec Certbot).

Fichier : `/etc/nginx/sites-available/usdt-aggregator`

**Sans HTTPS (pour tester d’abord) :**

```nginx
server {
    listen 80;
    server_name exchange.pals.africa;

    client_max_body_size 100M;

    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static/ {
        alias /var/www/usdt_aggregator/staticfiles/;
        expires 30d;
        add_header Pragma public;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

**Étapes à suivre :**

1. **Créer le fichier** (avec sudo) :  
   `sudo nano /etc/nginx/sites-available/usdt-aggregator`  
   Colle le bloc `server { ... }` ci‑dessus, sauvegarde (Ctrl+O, Entrée, Ctrl+X).

2. **Activer le site et recharger Nginx :**
   ```bash
   sudo ln -s /etc/nginx/sites-available/usdt-aggregator /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. **Tester en HTTP** : ouvre `http://exchange.pals.africa` dans le navigateur (admin, dashboard, API). Vérifie que le DNS pointe bien vers ton serveur (82.29.179.215).

4. **Activer HTTPS avec Certbot** (quand le site répond correctement en HTTP) :
   ```bash
   sudo apt update
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d exchange.pals.africa
   ```
   - Certbot te demandera une adresse e‑mail (pour rappels de renouvellement).
   - Il te proposera d’accepter les conditions d’utilisation : oui.
   - Il modifiera lui‑même le fichier Nginx pour ajouter le SSL (certificat Let’s Encrypt) et la redirection HTTP → HTTPS.
   - À la fin, recharge Nginx si ce n’est pas fait automatiquement.

5. **Vérifier** : ouvre `https://exchange.pals.africa`. Tu dois avoir le cadenas et la redirection depuis `http://` vers `https://`.

**Après Certbot (HTTPS), ta config ressemblera à ceci :**

```nginx
server {
    server_name exchange.pals.africa;

    client_max_body_size 100M;

    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static/ {
        alias /var/www/usdt_aggregator/staticfiles/;
        expires 30d;
        add_header Pragma public;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:8000;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/exchange.pals.africa/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/exchange.pals.africa/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if ($host = exchange.pals.africa) {
        return 301 https://$host$request_uri;
    }

    server_name exchange.pals.africa;
    listen 80;
    return 404;
}
```

(Rappel : activer le site et Certbot sont détaillés dans les **Étapes à suivre** ci‑dessus.)

---

## 11. Checklist récap

- [ ] Code déployé sur le serveur
- [ ] Python 3.10+ et venv, `pip install -r requirements.txt`
- [ ] Variables d’environnement : `DEBUG=0`, `ALLOWED_HOSTS`, `DJANGO_SECRET_KEY`
- [ ] `python manage.py migrate`
- [ ] `python manage.py createsuperuser`
- [ ] `python manage.py collectstatic` (si Nginx sert les static)
- [ ] Gunicorn lancé (manuel ou via systemd)
- [ ] Cron ajouté pour `refresh_best_rates` (toutes les 1 min)
- [ ] (Optionnel) Nginx + HTTPS
- [ ] Firewall : ouvrir 80, 443 (et éventuellement 22 pour SSH)

---

## 12. Après déploiement

- **Admin** : `https://exchange.pals.africa/admin/`
- **Dashboard** : `https://exchange.pals.africa/dashboard/`
- **API** : `https://exchange.pals.africa/api/v1/` (JWT ou API Key)
- **Swagger** : `https://exchange.pals.africa/api/docs/`

Configurer l’intervalle de refresh dans **Dashboard > Refresh taux** (ou Admin > Config refresh best rates).
