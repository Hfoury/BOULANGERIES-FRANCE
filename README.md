# BOULANGERIES-FRANCE

Référentiel des boulangeries référencées dans OpenStreetMap, avec exports JSON, CSV et flux RSS.

## Données et actualisation
- Source : OpenStreetMap via les extraits régionaux Geofabrik au format PBF, traités localement avec PyOsmium.
- La collecte couvre les 22 anciennes régions métropolitaines publiées séparément par Geofabrik ; les découpages sont historiques et non les 18 régions administratives actuelles.
- Actualisation automatique quotidienne à 04:20 UTC.
- Les informations de contact et horaires dépendent de leur présence dans OpenStreetMap.
- Une nouvelle entrée RSS signifie « nouvellement repérée dans le référentiel », pas nécessairement une ouverture commerciale.
- Les fichiers existants ne sont remplacés qu'après une collecte complète et un contrôle minimal du volume.
- Attribution : contributeurs OpenStreetMap, licence ODbL. Extraits : Geofabrik.

## Flux et exports
- RSS : https://raw.githubusercontent.com/Hfoury/BOULANGERIES-FRANCE/main/data/flux.rss
- JSON : https://raw.githubusercontent.com/Hfoury/BOULANGERIES-FRANCE/main/data/boulangeries.json
- CSV : https://raw.githubusercontent.com/Hfoury/BOULANGERIES-FRANCE/main/data/boulangeries.csv

Le premier passage constitue l'historique de référence et ne publie pas toutes les boulangeries comme des ouvertures nouvelles.

## Exécution manuelle
GitHub → Actions → Actualisation quotidienne → Run workflow.
