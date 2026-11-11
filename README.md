# BOULANGERIES-FRANCE
Référentiel national des boulangeries référencées dans OpenStreetMap, avec exports JSON, CSV et flux RSS.

## Données
- Source : OpenStreetMap via Overpass, France entière, objets `shop=bakery`.
- Mise à jour automatique quotidienne à 04:20 UTC.
- Les informations de contact et horaires dépendent de leur présence dans OpenStreetMap.
- Une nouvelle entrée RSS signifie « nouvellement repérée dans le référentiel », pas nécessairement une ouverture commerciale.
- Attribution : contributeurs OpenStreetMap, licence ODbL.

## Flux et exports
- RSS : https://raw.githubusercontent.com/Hfoury/BOULANGERIES-FRANCE/main/data/flux.rss
- JSON : https://raw.githubusercontent.com/Hfoury/BOULANGERIES-FRANCE/main/data/boulangeries.json
- CSV : https://raw.githubusercontent.com/Hfoury/BOULANGERIES-FRANCE/main/data/boulangeries.csv

Le premier passage constitue l'historique de référence et ne publie pas toutes les boulangeries comme des ouvertures nouvelles.

## Exécution manuelle
GitHub → Actions → Actualisation quotidienne → Run workflow.
