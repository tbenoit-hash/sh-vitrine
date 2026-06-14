#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère data.json pour le site vitrine SH à partir de l'API Hostaway.
Tourné chaque jour par GitHub Actions : un logement ajouté sur Hostaway met
à jour automatiquement le compteur, les loyers du simulateur et la galerie.

Identifiants : variables d'env HOSTAWAY_ACCOUNT_ID / HOSTAWAY_API_KEY
(en local : lit le fichier ../.env s'il existe).
"""
import os, re, json, statistics, urllib.parse, urllib.request

API = "https://api.hostaway.com/v1"
# Pépites hors région (section « Évasion »)
EXTRA_IDS = [497952, 496304]

AMENITY_FR = {
    'Internet': 'Wifi', 'Wireless': 'Wifi', 'Wifi': 'Wifi', 'Pocket wifi': 'Wifi',
    'Kitchen': 'Cuisine équipée', 'Free parking on premises': 'Parking gratuit',
    'Free parking': 'Parking gratuit', 'Parking': 'Parking', 'Washer': 'Lave-linge',
    'Dryer': 'Sèche-linge', 'Dishwasher': 'Lave-vaisselle', 'Air conditioning': 'Climatisation',
    'Heating': 'Chauffage', 'TV': 'Télévision', 'Cable TV': 'Télévision', 'Hot tub': 'Jacuzzi',
    'Jacuzzi': 'Jacuzzi', 'Swimming pool': 'Piscine', 'Pool': 'Piscine', 'Sauna': 'Sauna',
    'Balcony': 'Balcon', 'Garden or backyard': 'Jardin', 'Patio or balcony': 'Terrasse',
    'Elevator': 'Ascenseur', 'Iron': 'Fer à repasser', 'Hair dryer': 'Sèche-cheveux',
    'Coffee maker': 'Cafetière', 'Microwave': 'Micro-ondes', 'Refrigerator': 'Réfrigérateur',
    'Oven': 'Four', 'BBQ grill': 'Barbecue', 'Fireplace': 'Cheminée', 'Gym': 'Salle de sport',
    'Pets allowed': 'Animaux acceptés', 'Essentials': 'Linge & nécessaire', 'Crib': 'Lit bébé',
    'Free street parking': 'Parking dans la rue', 'Private entrance': 'Entrée privée',
    'Long term stays allowed': 'Séjours longue durée', 'Self check-in': 'Arrivée autonome',
}
PRIORITY_AM = ['Wifi', 'Cuisine équipée', 'Parking gratuit', 'Parking', 'Jacuzzi', 'Piscine',
               'Sauna', 'Climatisation', 'Lave-linge', 'Sèche-linge', 'Lave-vaisselle',
               'Télévision', 'Chauffage', 'Jardin', 'Balcon', 'Terrasse', 'Barbecue',
               'Cheminée', 'Ascenseur', 'Arrivée autonome', 'Entrée privée']

# Projection sur la carte illustrée de Bourgogne (carte-bourgogne.svg, viewBox 1500x1180)
MAP = dict(minlon=2.845190, maxlat=48.399390, kx=0.678446, scale=490.3163, offx=500.351, offy=40.0, W=1500.0, H=1180.0)
def map_pos(lat, lon):
    if lat is None or lon is None or not (45.8 <= lat <= 48.5 and 2.7 <= lon <= 5.7):
        return (None, None)
    x = MAP['offx'] + (lon - MAP['minlon']) * MAP['kx'] * MAP['scale']
    y = MAP['offy'] + (MAP['maxlat'] - lat) * MAP['scale']
    return (round(x / MAP['W'] * 100, 2), round(y / MAP['H'] * 100, 2))
SKI_CITIES = {"Les Belleville", "Demi-Quartier", "Megève"}
SEA_CITIES = {"La Londe-les-Maures"}


def load_env():
    for k in ("HOSTAWAY_ACCOUNT_ID", "HOSTAWAY_API_KEY"):
        if os.environ.get(k):
            continue
        envp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
        if os.path.exists(envp):
            for line in open(envp, encoding="utf-8"):
                line = line.strip()
                if line.startswith(k + "="):
                    os.environ[k] = line.split("=", 1)[1].strip().strip('"').strip("'")


def get_token():
    acc = os.environ["HOSTAWAY_ACCOUNT_ID"]; key = os.environ["HOSTAWAY_API_KEY"]
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": acc,
        "client_secret": key, "scope": "general"}).encode()
    req = urllib.request.Request(API + "/accessTokens", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-control": "no-cache"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]


def api_get(path, tok, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


def clean_name(s):
    s = (s or "").replace("\xa0", " ").strip().strip('"').strip("«»").strip().strip('"').strip()
    return re.sub(r"\s+", " ", s)


def cover_url(l):
    imgs = [i for i in (l.get("listingImages") or []) if i.get("url")]
    imgs.sort(key=lambda i: (i.get("sortOrder") or 0))
    return imgs[0]["url"] if imgs else (l.get("thumbnailUrl") or "")


def type_of(bedrooms):
    return {0: "Studio", 1: "T2", 2: "T3", 3: "T4", 4: "T5"}.get(bedrooms, "T6+")


def prop_record(l):
    imgs = [i for i in (l.get("listingImages") or []) if i.get("url")]
    imgs.sort(key=lambda i: (i.get("sortOrder") or 0))
    photos = [i["url"] for i in imgs][:12]
    am_fr, seen = [], set()
    for a in (l.get("listingAmenities") or []):
        fr = AMENITY_FR.get(a.get("amenityName", ""))
        if fr and fr not in seen:
            seen.add(fr); am_fr.append(fr)
    am_fr.sort(key=lambda x: PRIORITY_AM.index(x) if x in PRIORITY_AM else 99)
    desc = re.sub(r"\s+", " ", (l.get("description") or "")).strip()
    mx, my = map_pos(l.get("lat"), l.get("lng"))
    return {
        "id": l.get("id"),
        "name": clean_name(l.get("name") or l.get("internalListingName") or f"Logement {l.get('id')}"),
        "city": l.get("city") or "",
        "guests": l.get("personCapacity") or 0,
        "bedrooms": l.get("bedroomsNumber") or 0,
        "bathrooms": l.get("bathroomsNumber") or 0,
        "price": int(round(l.get("price") or 0)),
        "rating": l.get("averageReviewRating"),
        "cover": (photos[0] if photos else cover_url(l)),
        "photos": photos,
        "description": desc[:1400],
        "amenities": am_fr[:14],
        "lat": l.get("lat"),
        "lng": l.get("lng"),
        "mapx": mx,
        "mapy": my,
    }


def clean_review(t):
    t = t or ""
    m = re.search(r"Positive\s*:\s*(.+?)(?:Negative\s*:|$)", t, re.S | re.I)
    if m:
        t = m.group(1)
    return re.sub(r"\s+", " ", t).strip().strip("-").strip()


def is_french(t):
    tl = " " + t.lower() + " "
    fr = sum(w in tl for w in (" le ", " la ", " les ", " très ", " est ", " et ", " avec ",
                               " logement", " séjour", " propre", " bien ", " nous ", " tout ", " sur "))
    es = sum(w in tl for w in (" muy ", " está ", " habitac", " apartamento", " bonito", " ubicaci",
                               " todo ", " buena", " grande ", " casa "))
    return fr >= 2 and fr > es


def first_name(n):
    n = (n or "").strip().split(" ")[0]
    return (n[:1].upper() + n[1:].lower()) if n else "Voyageur"


def pick_reviews(tok, byid, n=6):
    res = api_get("/reviews", tok, {"limit": 500}).get("result", [])
    cands = []
    for r in res:
        if r.get("type") != "guest-to-host" or r.get("status") != "published":
            continue
        txt = clean_review(r.get("publicReview"))
        if not (45 <= len(txt) <= 230) or "negative" in txt.lower() or not is_french(txt):
            continue
        listing = byid.get(r.get("listingMapId"))
        city = (listing.get("city") if listing else "") or ""
        cands.append({
            "rating": r.get("rating") or 9,
            "name": first_name(r.get("guestName")),
            "place": city or "Séjour vérifié",
            "text": txt,
        })
    cands.sort(key=lambda x: (-x["rating"], -len(x["text"])))
    seen, out = set(), []
    for c in cands:
        if c["name"] in seen:
            continue
        seen.add(c["name"]); out.append({k: c[k] for k in ("name", "place", "text")})
        if len(out) >= n:
            break
    return out


def family_key(name):
    """Clé de regroupement par « famille » de logement (évite d'afficher 4 fois le même château)."""
    n = (name or "").strip()
    n = re.split(r'\s+[-–—·]\s+', n)[0]   # avant un séparateur « - »
    n = re.sub(r'\s*\(\d+\)\s*$', '', n)  # « (2) » final
    n = re.sub(r'\s+\d+\s*$', '', n)       # numéro final
    return (n.strip() or (name or "")).lower()


def main():
    load_env()
    tok = get_token()
    listings = api_get("/listings", tok, {"limit": 500}).get("result", [])
    listings = [l for l in listings if l.get("price")]

    # Loyers médians par type (pour le simulateur)
    by_type = {}
    for l in listings:
        t = type_of(l.get("bedroomsNumber") or 0)
        by_type.setdefault(t, []).append(int(round(l["price"])))
    adr = {t: int(statistics.median(v)) for t, v in by_type.items() if v}

    # Tous les enregistrements (réutilisés pour la galerie ET le catalogue)
    records = [prop_record(l) for l in listings]
    byrec = {r["id"]: r for r in records}

    # Galerie « nos biens d'exception » : sélection CURÉE par le client (8 logements choisis à la
    # main), données rafraîchies chaque jour depuis Hostaway. Affichée par prix décroissant ;
    # complétée par les plus chers si un id venait à manquer (logement retiré / sans prix).
    FEATURED_PINNED = [
        470939,  # Le Verger Secret (Saint-Loup-de-Varennes)
        465573,  # Chalon Hacienda
        468351,  # Belle maison rénovée avec jacuzzi (Saint-Rémy)
        465755,  # Les Vagastines 2
        475670,  # La Cave des Miracles (Dracy)
        468463,  # Les Vignes Rouges (Givry / Russilly)
        474343,  # Charmant gîte 3* — 25 Russilly (Givry)
        465404,  # Château de Dracy – L'Élégante
    ]
    featured = [byrec[i] for i in FEATURED_PINNED if i in byrec]
    if len(featured) < 8:  # filet de sécurité : compléter avec les plus chers
        have = {r["id"] for r in featured} | set(EXTRA_IDS)
        fillers = sorted((r for r in records if r["id"] not in have and r.get("cover") and (r.get("price") or 0) > 0),
                         key=lambda r: -(r.get("price") or 0))
        featured += fillers[:8 - len(featured)]
    featured.sort(key=lambda r: (-(r.get("price") or 0), r.get("name") or ""))
    extras = [byrec[i] for i in EXTRA_IDS if i in byrec]
    byid = {l.get("id"): l for l in listings}

    communes = sorted({(l.get("city") or "").strip() for l in listings if l.get("city")})
    try:
        reviews = pick_reviews(tok, byid)
    except Exception as e:
        print("avis non récupérés:", e); reviews = []
    out = {
        "count": len(listings),
        "communes": len(communes),
        "adr": adr,
        "featured": featured,
        "extras": extras,
        "reviews": reviews,
    }
    if os.environ.get("BUILD_DATE"):
        out["updated"] = os.environ["BUILD_DATE"]

    # Catalogue complet (toutes les fiches, pour le site sans dépendance Hostaway)
    catalogue = list(records)
    catalogue.sort(key=lambda x: (-(x.get("rating") or 0), x.get("name") or ""))

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(here, "catalogue.json"), "w", encoding="utf-8") as f:
        json.dump({"count": len(catalogue), "listings": catalogue}, f, ensure_ascii=False)
    print(f"data.json écrit : {out['count']} logements, {out['communes']} communes, "
          f"types={adr}, {len(featured)} en vedette, {len(reviews)} avis réels ; "
          f"catalogue.json : {len(catalogue)} fiches complètes")


if __name__ == "__main__":
    main()
