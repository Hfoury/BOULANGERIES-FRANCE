import csv
import json
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import osmium
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
BASE = "https://download.geofabrik.de/europe/france"
# Geofabrik publie encore la France par anciennes régions administratives.
# Leur union couvre la métropole ; les DOM sont fournis séparément.
REGIONS = [
    "alsace", "aquitaine", "auvergne", "basse-normandie", "bourgogne",
    "bretagne", "centre", "champagne-ardenne", "corse", "franche-comte",
    "haute-normandie", "ile-de-france", "languedoc-roussillon", "limousin",
    "lorraine", "midi-pyrenees", "nord-pas-de-calais", "pays-de-la-loire",
    "picardie", "poitou-charentes", "provence-alpes-cote-d-azur", "rhone-alpes",
]

def tags_dict(tags):
    return {tag.k: tag.v for tag in tags}

def coordinates(obj):
    if isinstance(obj, osmium.osm.Node):
        return (obj.location.lat, obj.location.lon) if obj.location.valid() else None
    points = [(n.lat, n.lon) for n in obj.nodes if n.location.valid()]
    if not points:
        return None
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points))

class BakeryHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.items = {}

    def inspect(self, obj):
        tags = tags_dict(obj.tags)
        if tags.get("shop") != "bakery":
            return
        location = coordinates(obj)
        if location is None:
            return
        kind = "node" if isinstance(obj, osmium.osm.Node) else "way"
        osm_id = f"{kind}:{obj.id}"
        self.items[osm_id] = {
            "id": osm_id,
            "nom": tags.get("name", "Boulangerie sans nom"),
            "adresse": ", ".join(filter(None, [
                tags.get("addr:housenumber"), tags.get("addr:street"),
                tags.get("addr:postcode"), tags.get("addr:city"),
            ])),
            "code_postal": tags.get("addr:postcode", ""),
            "commune": tags.get("addr:city", ""),
            "latitude": location[0],
            "longitude": location[1],
            "telephone": tags.get("phone", tags.get("contact:phone", "")),
            "horaires": tags.get("opening_hours", ""),
            "site": tags.get("website", tags.get("contact:website", "")),
            "osm_url": f"https://www.openstreetmap.org/{kind}/{obj.id}",
        }

    def node(self, obj):
        self.inspect(obj)

    def way(self, obj):
        self.inspect(obj)

def download(url, path):
    """Télécharge un extrait Geofabrik avec reprises sur erreurs temporaires."""
    headers = {"User-Agent": "BOULANGERIES-FRANCE/3.0 (OpenStreetMap data updater)"}
    temporary_path = path.with_suffix(path.suffix + ".part")
    max_attempts = 6
    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(1, max_attempts + 1):
        try:
            size = 0
            with requests.get(url, headers=headers, stream=True, timeout=(30, 300)) as response:
                if response.status_code in retryable_statuses:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(int(retry_after), 180) if retry_after else min(15 * (2 ** (attempt - 1)), 180)
                    except ValueError:
                        delay = min(15 * (2 ** (attempt - 1)), 180)
                    raise requests.exceptions.HTTPError(
                        f"Erreur HTTP temporaire {response.status_code}; nouvelle tentative dans {delay}s",
                        response=response,
                    )
                response.raise_for_status()
                with temporary_path.open("wb") as out:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            out.write(chunk)
                            size += len(chunk)

            if size < 1024 * 1024:
                raise RuntimeError(f"Extrait anormalement petit : {url}")

            temporary_path.replace(path)
            print(f"Téléchargé {path.name}: {size / 1024 / 1024:.1f} Mio", flush=True)
            return

        except requests.exceptions.RequestException as error:
            if temporary_path.exists():
                temporary_path.unlink()
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status is not None and status not in retryable_statuses:
                raise
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Échec du téléchargement après {max_attempts} tentatives : {url} ({error})"
                ) from error

            retry_after = getattr(getattr(error, "response", None), "headers", {}).get("Retry-After")
            try:
                delay = min(int(retry_after), 180) if retry_after else min(15 * (2 ** (attempt - 1)), 180)
            except ValueError:
                delay = min(15 * (2 ** (attempt - 1)), 180)
            print(
                f"Téléchargement temporairement indisponible ({error}). "
                f"Tentative {attempt + 1}/{max_attempts} dans {delay}s.",
                flush=True,
            )
            time.sleep(delay)
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()
            raise

def main():
    unique = {}
    with tempfile.TemporaryDirectory() as temp:
        for index, region in enumerate(REGIONS, 1):
            print(f"=== {index}/{len(REGIONS)} {region} ===", flush=True)
            path = Path(temp) / f"{region}.osm.pbf"
            download(f"{BASE}/{region}-latest.osm.pbf", path)
            handler = BakeryHandler()
            handler.apply_file(str(path), locations=True)
            unique.update(handler.items)
            print(f"{region}: {len(handler.items)} boulangeries géolocalisées; cumul {len(unique)}", flush=True)
            path.unlink()
    rows = sorted(unique.values(), key=lambda x: (x["code_postal"], x["commune"], x["nom"]))
    if len(rows) < 5000:
        raise RuntimeError(f"Collecte incomplète ou anormale ({len(rows)} boulangeries) : anciennes données conservées")
    now = datetime.now(timezone.utc)
    previous_file = DATA / "_previous.json"
    old_ids = None
    if previous_file.exists():
        try:
            old_ids = {x["id"] for x in json.loads(previous_file.read_text(encoding="utf-8"))}
        except (OSError, ValueError, KeyError, TypeError):
            print("Historique précédent illisible : nouveautés RSS non calculées.", flush=True)
    payload = {
        "generated_at": now.isoformat(),
        "source": "OpenStreetMap / Geofabrik (extraits régionaux)",
        "count": len(rows),
        "items": rows,
    }
    (DATA / "boulangeries.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (DATA / "boulangeries.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    fresh = [] if old_ids is None else [x for x in rows if x["id"] not in old_ids]
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    for key, value in [
        ("title", "Boulangeries France - nouvelles entrées"),
        ("link", "https://github.com/Hfoury/BOULANGERIES-FRANCE"),
        ("description", "Nouvelles boulangeries repérées dans OpenStreetMap. Une nouvelle entrée ne prouve pas une ouverture commerciale."),
        ("lastBuildDate", now.strftime("%a, %d %b %Y %H:%M:%S +0000")),
    ]:
        ET.SubElement(channel, key).text = value
    for item in fresh:
        entry = ET.SubElement(channel, "item")
        ET.SubElement(entry, "title").text = item["nom"] + " - " + (item["commune"] or item["code_postal"])
        ET.SubElement(entry, "link").text = item["osm_url"]
        ET.SubElement(entry, "guid", isPermaLink="false").text = item["id"]
        ET.SubElement(entry, "description").text = item["adresse"]
    ET.ElementTree(root).write(DATA / "flux.rss", encoding="utf-8", xml_declaration=True)
    previous_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"PUBLICATION PRÊTE: {len(rows)} boulangeries; {len(fresh)} nouvelles entrées RSS", flush=True)

if __name__ == "__main__":
    main()
