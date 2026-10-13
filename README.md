# PyBlade UI · Éditeur de thèmes

Un éditeur de thèmes pour [PyBlade UI](https://github.com/princelulinda/pyblade-ui), fait avec Django, PyBlade et PyBlade UI, dans l'esprit de tweakcn.

- **Préréglages** : 9 thèmes de départ, ou n'importe quelle base × couleur de la bibliothèque.
- **Chaque variable** modifiable, en mode clair et en mode sombre : sélecteur de couleur et champ texte (hex, `rgb()`, `hsl()`, `oklch()`…), regroupées comme dans l'aperçu (couleur principale, cartes, bordures, graphiques, sidebar…).
- **Contraste WCAG** en direct pour chaque texte sur son fond.
- **Annuler / rétablir** (Ctrl Z, Ctrl Maj Z), réinitialiser.
- **Importer** un `theme.css` PyBlade UI ou shadcn/ui (y compris les canaux HSL bruts de shadcn).
- **Exporter** : la commande `pyblade-ui theme set …` et le `theme.css`. Les variables modifiées sont écrites sous le marqueur `pyblade-ui:custom`, la partie que `theme set` conserve : le thème survit à une régénération.
- **Enregistrer et partager** : le thème est stocké et reçoit un lien court, `/t/<code>/`. Son CSS est servi à `/t/<code>.css`.

Le CSS exporté vient de `pyblade_ui.themes.render_theme`, la fonction du CLI.

## Lancer en local

```bash
uv sync
npm install && npm run css          # compile static/css/app.css
uv run python manage.py migrate
uv run python manage.py runserver
```

Puis http://127.0.0.1:8000/ (français) ou http://127.0.0.1:8000/en/ (anglais). `?preset=ocean` ouvre un préréglage.

## Organisation

| Fichier | Rôle |
|---|---|
| `templates/editor.html` | La page, rendue par PyBlade |
| `templates/partials/preview.html` | L'aperçu : de vrais composants PyBlade UI |
| `static/js/editor.js` | L'éditeur dans le navigateur (Alpine) : aperçu en direct, historique, contraste, import |
| `generator/themes.py` | Le thème côté serveur : validation, différences avec le préréglage, `theme.css` |
| `generator/presets.py` | Les préréglages |
| `generator/models.py` | `SavedTheme`, les thèmes partagés |
| `generator/i18n.py` | Les textes FR / EN et les données de l'aperçu |

| Route | Rôle |
|---|---|
| `/`, `/en/` | L'éditeur |
| `/t/<code>/`, `/en/t/<code>/` | Un thème enregistré, ouvert dans l'éditeur |
| `/t/<code>.css` | Son `theme.css` |
| `GET /api/preset?base=…&color=…` | Les valeurs de la bibliothèque pour une base et une couleur |
| `POST /api/export` | Le `theme.css` et la commande du thème en cours |
| `POST /api/themes` | Enregistre le thème et renvoie son lien |

Les valeurs reçues sont validées : seules les variables connues et des couleurs CSS sans `;`, `{`, `}` sont acceptées.

## Tests

```bash
uv run python manage.py test generator
```

## Mettre en ligne sur Vercel

Vercel reconnaît le projet Django tout seul (`manage.py`, `WSGI_APPLICATION`), installe les dépendances depuis `uv.lock` et lance `collectstatic` (les fichiers statiques sont servis par son CDN). `static/css/app.css` est commité : relancez `npm run css` avant de committer un changement de style.

Variables d'environnement du projet Vercel :

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | La clé secrète de Django. À définir (une longue chaîne aléatoire). |
| `DATABASE_URL` | Une base PostgreSQL (Neon, Supabase… via le Marketplace Vercel). Sans elle, l'éditeur fonctionne mais « Enregistrer et partager » est désactivé. |
| `DJANGO_ALLOWED_HOSTS` | Vos domaines en plus de `*.vercel.app`, séparés par des virgules. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Les mêmes domaines avec `https://`, si vous en ajoutez. |

Après avoir ajouté `DATABASE_URL`, créez les tables une fois depuis votre machine :

```bash
vercel env pull .env.local
set -a && . ./.env.local && set +a && uv run python manage.py migrate
```
