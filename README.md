# Carnet de voyage Maine — site web

Site statique avec mise à jour automatique de la météo toutes les 4 heures
jusqu'au lundi 18 mai 2026 au soir, après quoi le script s'arrête tout seul
(plus de commits, plus de bruit).

## Déploiement (~5 min)

### 1. Créer le repo GitHub

Sur github.com, clique **New** repository :
- **Repository name** : `maine-trip` (ou ce que tu veux)
- **Public** (obligatoire pour GitHub Pages gratuit)
- **Add a README** : laisser décoché (on en a déjà un)
- Clique **Create repository**

### 2. Pousser les fichiers

Depuis le dossier `web-bundle/`, dans un terminal :

```bash
cd web-bundle
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TON-USER/maine-trip.git
git push -u origin main
```

(Remplace `TON-USER` par ton nom d'utilisateur GitHub.)

### 3. Activer GitHub Pages

Dans le repo sur github.com :
- **Settings** → onglet **Pages** (dans la barre latérale gauche)
- **Source** : `Deploy from a branch`
- **Branch** : `main` / `/ (root)` → **Save**

GitHub te donnera une URL du style :
`https://TON-USER.github.io/maine-trip/`

(2-3 minutes de propagation au premier déploiement.)

### 4. Vérifier que les Actions tournent

- Onglet **Actions** du repo → tu devrais voir le workflow
  *Update weather forecast*
- Clique **Run workflow** une première fois pour forcer un premier update,
  ou attends la prochaine échéance cron (toutes les 4h pile + 5 min).

C'est tout. La page se mettra à jour seule jusqu'au mardi 19 mai au matin.

## Comment ça marche

- **`index.html`** : page statique servie par GitHub Pages
- **`scripts/update_weather.py`** : récupère la prévision NWS pour Belfast ME,
  met à jour le tableau météo + l'horodatage dans `index.html`
- **`.github/workflows/update.yml`** : cron GitHub Actions
  (`5 */4 * * *` = à h+5min toutes les 4h UTC), pousse les changements
- L'API NWS (api.weather.gov) est **gratuite, sans clé**, juste un User-Agent
- Le script ne dépend que de la stdlib Python (zero `pip install`)
- Après le 19 mai 04:00 UTC, le script détecte la date et ne fait rien

## Notes

- **Cron GitHub Actions** : pas garanti à la minute près (peut traîner
  10-15 min en heure de pointe). Ce n'est pas grave pour de la météo.
- **Coût** : 0 $. GitHub Pages public + Actions sont gratuits.
- **Limites** : 2000 min/mois d'Actions sur le free tier. Notre run prend
  ~20 secondes × 6 runs/jour × 5 jours = 10 min total. Aucun risque.
- **Si tu veux modifier le contenu** : édite `index.html` directement et
  push. Le workflow ne touche qu'aux blocs entre les marqueurs
  `<!-- WEATHER_TABLE_START -->` et `<!-- LAST_UPDATE_START -->`.
- **PDF** : `maine-trip-book.pdf` est inclus à la racine pour le bouton
  *Télécharger PDF* dans le topbar.

## Si quelque chose foire

- Le workflow Actions échoue ? Onglet **Actions** → clique sur le run rouge
  → regarde les logs. Le plus probable : l'API NWS qui flanche
  ponctuellement. Le prochain run dans 4h reprendra.
- La page n'apparaît pas ? Vérifie **Settings** → **Pages** que la source
  est bien `main` / root.
- Tu veux tester le script en local ?
  `python3 scripts/update_weather.py` (Python 3.9+ requis).
