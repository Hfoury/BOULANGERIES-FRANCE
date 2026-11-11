import csv
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# Découpage géographique : les rectangles se chevauchent légèrement.
# Les identifiants OSM servent à éliminer les doublons.
REGIONS = [
    ("Auvergne-Rhône-Alpes", 44.0, 2.0, 46.8, 7.2),
    ("Bourgogne-Franche-Comté", 46.0, 3.3, 48.5, 7.2),
    ("Bretagne", 47.2, -5.3, 48.9, -1.0),
    ("Centre-Val de Loire", 46.3, 0.0, 48.9, 3.0),
    ("Corse", 41.3, 8.4, 43.1, 9.7),
    ("Grand Est", 47.3, 4.8, 50.3, 8.3),
    ("Hauts-de-France", 49.5, 1.3, 51.3, 4.3),
    ("Normandie", 48.1, -1.9, 50.2, 1.9),
    ("Nouvelle-Aquitaine", 42.7, -1.8, 47.2, 1.5),
    ("Occitanie", 42.3, -0.2, 45.1, 4.9),
    ("Pays de la Loire", 46.2, -2.0, 48.6, 0.9),
    ("Provence-Alpes-Côte d'Azur", 42.9, 4.2, 45.2, 7.8),
    ("Île-de-France", 48.1, 1.4, 49.3, 3.6),
    ("Guadeloupe", 15.8, -61.9, 16.6, -60.9),
    ("Martinique", 14.3, -61.3, 14.9, -60.7),
    ("Guyane", 2.0, -54.7, 5.9, -51.6),
    ("La Réunion", -21.4, 55.2, -20.8, 55.9),
    ("Mayotte", -13.1, 45.0, -12.6, 45.3),
]

OVERPASS_SERVERS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def download_region(session, name, south, west, north, east):
    query = f"""
    [out:json][timeout:90];
    (
      nwr["shop"="bakery"]({south},{west},{north},{east});
    );
    out center tags;
    """
    errors = []
    for server in OVERPASS_SERVERS:
        try:
            print(f"Région {name} — interrogation {server}", flush=True)
            response = session.post(
                server,
                data={"data": query},
                timeout=(20, 90),
            )
            response.raise_for_status()
            elements = response.json().get("elements", [])
            print(f"Région {name} : {len(elements)} objets reçus", flush=True)
            return elements
        except Exception as exc:
            message = f"{server}: {type(exc).__name__}: {exc}"
            errors.append(message)
            print(f"Échec {name} — {message}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"Collecte impossible pour {name}. " + " | ".join(errors))


def download_bakeries():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "BOULANGERIES-FRANCE/2.0 (OpenStreetMap data updater)"
    })
    unique = {}
    for index, (name, south, west, north, east) in enumerate(REGIONS, 1):
        print(f"=== {index}/{len(REGIONS)} : {name} ===", flush=True)
        elements = download_region(session, name, south, west, north, east)
        for element in elements:
            unique[f'{element["type"]}:{element["id"]}'] = element
    if not unique:
        raise RuntimeError("Aucune boulangerie reçue : données précédentes conservées")
    print(f"Collecte terminée : {len(unique)} objets uniques", flush=True)
    return list(unique.values())


def main():
    elements = download_bakeries()
    now = datetime.now(timezone.utc)
    oldfile = DATA / "_previous.json"
    old = None
    if oldfile.exists():
        try:
            old = {item["id"] for item in json.loads(oldfile.read_text(encoding="utf-8"))}
        except (OSError, ValueError, KeyError, TypeError):
            print("Historique précédent illisible : les nouveautés ne seront pas calculées.", flush=True)

    rows = []
    for element in elements:
        tags = element.get("tags", {})
        center = element.get("center", {})
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        if lat is None or lon is None:
            continue
        rows.append({
            "id": f'{element["type"]}:{element["id"]}',
            "nom": tags.get("name", "Boulangerie sans nom"),
            "adresse": ", ".join(filter(None, [
                tags.get("addr:housenumber"), tags.get("addr:street"),
                tags.get("addr:postcode"), tags.get("addr:city"),
            ])),
            "code_postal": tags.get("addr:postcode", ""),
            "commune": tags.get("addr:city", ""),
            "latitude": lat,
            "longitude": lon,
            "telephone": tags.get("phone", tags.get("contact:phone", "")),
            "horaires": tags.get("opening_hours", ""),
            "site": tags.get("website", tags.get("contact:website", "")),
            "osm_url": f'https://www.openstreetmap.org/{element["type"]}/{element["id"]}',
        })

    rows.sort(key=lambda item: (item["code_postal"], item["commune"], item["nom"]))
    if not rows:
        raise RuntimeError("Aucune boulangerie exploitable : données précédentes conservées")

    output = {
        "generated_at": now.isoformat(),
        "source": "OpenStreetMap / Overpass",
        "count": len(rows),
        "items": rows,
    }
    (DATA / "boulangeries.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (DATA / "boulangeries.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    fresh = [] if old is None else [item for item in rows if item["id"] not in old]
    channel = ET.Element("channel")
    for key, value in [
        ("title", "Boulangeries France - nouvelles entrées"),
        ("link", "https://github.com/Hfoury/BOULANGERIES-FRANCE"),
        ("description", "Nouvelles boulangeries repérées dans OpenStreetMap. Une nouvelle entrée ne prouve pas une ouverture commerciale."),
        ("lastBuildDate", now.strftime("%a, %d %b %Y %H:%M:%S +0000")),
    ]:
        ET.SubElement(channel, key).text = value
    root = ET.Element("rss", version="2.0")
    root.append(channel)
    for item in fresh:
        rss_item = ET.SubElement(channel, "item")
        ET.SubElement(rss_item, "title").text = item["nom"] + " - " + (item["commune"] or item["code_postal"])
        ET.SubElement(rss_item, "link").text = item["osm_url"]
        ET.SubElement(rss_item, "guid", isPermaLink="false").text = item["id"]
        ET.SubElement(rss_item, "description").text = item["adresse"]
    ET.ElementTree(root).write(DATA / "flux.rss", encoding="utf-8", xml_declaration=True)
    oldfile.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} boulangeries ; {len(fresh)} nouvelles entrées", flush=True)


if __name__ == "__main__":
    main()
