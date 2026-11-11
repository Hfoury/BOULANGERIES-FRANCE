import os
import re
import tempfile
from pathlib import Path

import osmium
import requests

EXTRACTS = {
    "Bretagne": "https://download.geofabrik.de/europe/france/bretagne-latest.osm.pbf",
    "Pays de la Loire": "https://download.geofabrik.de/europe/france/pays-de-la-loire-latest.osm.pbf",
}

class CountHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.bakeries = set()
        self.total_stations = set()
        self.objects_with_location = 0

    @staticmethod
    def is_total(tags):
        label = " ".join((tags.get("brand", ""), tags.get("name", ""), tags.get("operator", "")))
        return re.search(r"total", label, re.I) is not None

    def node(self, obj):
        self.inspect(obj, obj.location if obj.location.valid() else None)

    def way(self, obj):
        coords = []
        for node in obj.nodes:
            if node.location.valid():
                coords.append(node.location)
        location = None
        if coords:
            location = (sum(p.lat for p in coords) / len(coords),
                        sum(p.lon for p in coords) / len(coords))
        self.inspect(obj, location)

    def inspect(self, obj, location):
        tags = obj.tags
        if tags.get("shop") == "bakery":
            self.bakeries.add(f"{obj.__class__.__name__}:{obj.id}")
        if tags.get("amenity") == "fuel" and self.is_total(tags):
            self.total_stations.add(f"{obj.__class__.__name__}:{obj.id}")
        if location is not None:
            self.objects_with_location += 1

def download(url, destination):
    headers = {"User-Agent": "FR-OSM-data-validation/1.0 (GitHub Actions)"}
    with requests.get(url, headers=headers, stream=True, timeout=(20, 180)) as response:
        response.raise_for_status()
        total = 0
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
                    total += len(chunk)
        if total < 1024 * 1024:
            raise RuntimeError(f"Extrait anormalement petit ({total} octets): {url}")
        print(f"Téléchargé: {destination.name} ({total / 1024 / 1024:.1f} Mio)", flush=True)

def main():
    totals = {"bakeries": 0, "total_stations": 0}
    with tempfile.TemporaryDirectory() as temp:
        for region, url in EXTRACTS.items():
            path = Path(temp) / (region.lower().replace(" ", "-") + ".osm.pbf")
            print(f"=== {region} ===", flush=True)
            download(url, path)
            handler = CountHandler()
            handler.apply_file(str(path), locations=True)
            bakery_count = len(handler.bakeries)
            station_count = len(handler.total_stations)
            print(f"{region}: boulangeries={bakery_count}, stations Total candidates={station_count}, objets géolocalisés={handler.objects_with_location}", flush=True)
            if handler.objects_with_location == 0:
                raise RuntimeError(f"Aucune géométrie exploitable dans l'extrait {region}")
            totals["bakeries"] += bakery_count
            totals["total_stations"] += station_count
            path.unlink()
    print(f"TEST OK — total régional: {totals['bakeries']} boulangeries; {totals['total_stations']} stations Total candidates", flush=True)

if __name__ == "__main__":
    main()
