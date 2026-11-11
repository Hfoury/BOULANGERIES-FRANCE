import csv,json,os,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; DATA.mkdir(exist_ok=True)
URL=os.getenv("OVERPASS_URL","https://overpass-api.de/api/interpreter")
Q='[out:json][timeout:240];area["ISO3166-1"="FR"][admin_level=2]->.fr;(nwr["shop"="bakery"](area.fr););out center tags;'
def main():
 r=requests.post(URL,data={"data":Q},headers={"User-Agent":"BOULANGERIES-FRANCE/1.0"},timeout=300);r.raise_for_status()
 now=datetime.now(timezone.utc); oldfile=DATA/"_previous.json"
 old={x["id"] for x in json.loads(oldfile.read_text())} if oldfile.exists() else None
 rows=[]
 for e in r.json().get("elements",[]):
  t=e.get("tags",{}); c=e.get("center",{}); lat=e.get("lat",c.get("lat")); lon=e.get("lon",c.get("lon"))
  if lat is None or lon is None: continue
  rows.append({"id":f'{e["type"]}:{e["id"]}',"nom":t.get("name","Boulangerie sans nom"),"adresse":", ".join(filter(None,[t.get("addr:housenumber"),t.get("addr:street"),t.get("addr:postcode"),t.get("addr:city")])),"code_postal":t.get("addr:postcode",""),"commune":t.get("addr:city",""),"latitude":lat,"longitude":lon,"telephone":t.get("phone",t.get("contact:phone","")),"horaires":t.get("opening_hours",""),"site":t.get("website",t.get("contact:website","")),"osm_url":f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}'})
 rows.sort(key=lambda x:(x["code_postal"],x["commune"],x["nom"]))
 if not rows: raise RuntimeError("Réponse vide : données non remplacées")
 (DATA/"boulangeries.json").write_text(json.dumps({"generated_at":now.isoformat(),"source":"OpenStreetMap / Overpass","count":len(rows),"items":rows},ensure_ascii=False,indent=2),encoding="utf-8")
 with (DATA/"boulangeries.csv").open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=";");w.writeheader();w.writerows(rows)
 fresh=[] if old is None else [x for x in rows if x["id"] not in old]
 ch=ET.Element("channel")
 for k,v in [("title","Boulangeries France - nouvelles entrées"),("link","https://github.com/Hfoury/BOULANGERIES-FRANCE"),("description","Nouvelles boulangeries repérées dans OpenStreetMap. Une nouvelle entrée ne prouve pas une ouverture commerciale."),("lastBuildDate",now.strftime("%a, %d %b %Y %H:%M:%S +0000"))]: ET.SubElement(ch,k).text=v
 root=ET.Element("rss",version="2.0");root.append(ch)
 for x in fresh:
  it=ET.SubElement(ch,"item");ET.SubElement(it,"title").text=x["nom"]+" - "+(x["commune"] or x["code_postal"]);ET.SubElement(it,"link").text=x["osm_url"];ET.SubElement(it,"guid",isPermaLink="false").text=x["id"];ET.SubElement(it,"description").text=x["adresse"]
 ET.ElementTree(root).write(DATA/"flux.rss",encoding="utf-8",xml_declaration=True)
 oldfile.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
 print(f"{len(rows)} boulangeries ; {len(fresh)} nouvelles entrées")
if __name__=="__main__": main()
