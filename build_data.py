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
SITE = "https://www.sh-developpement.fr"
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
        "type": type_of(l.get("bedroomsNumber") or 0),
        "cleaningFee": int(round(l.get("cleaningFee") or 0)),
        "deposit": int(round(l.get("refundableDamageDeposit") or 0)),
        "markup": round(float(l.get("bookingEngineMarkup") or 1.0), 4),
        "minNights": int(l.get("minNights") or 1),
        "currency": l.get("currencyCode") or "EUR",
        "instant": 1 if l.get("instantBookable") else 0,
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


def fetch_all_reviews(tok, max_pages=12):
    """Récupère tous les avis (paginés, 500/page)."""
    out = []
    for p in range(max_pages):
        res = api_get("/reviews", tok, {"limit": 500, "offset": p * 500}).get("result", []) or []
        out.extend(res)
        if len(res) < 500:
            break
    return out


def aggregate_listing_reviews(all_reviews, per=3):
    """Par logement : nombre d'avis publiés + meilleurs commentaires FR (prénom + texte)."""
    counts, cands = {}, {}
    for r in all_reviews:
        if r.get("type") != "guest-to-host" or r.get("status") != "published":
            continue
        lid = r.get("listingMapId")
        if lid is None:
            continue
        counts[lid] = counts.get(lid, 0) + 1
        txt = clean_review(r.get("publicReview"))
        if 40 <= len(txt) <= 240 and "negative" not in txt.lower() and is_french(txt):
            cands.setdefault(lid, []).append({"rating": r.get("rating") or 0,
                                              "name": first_name(r.get("guestName")), "text": txt})
    out = {}
    for lid, c in counts.items():
        items = sorted(cands.get(lid, []), key=lambda x: (-(x["rating"] or 0), -len(x["text"])))
        seen, picked = set(), []
        for it in items:
            if it["name"] in seen:
                continue
            seen.add(it["name"]); picked.append({"name": it["name"], "text": it["text"]})
            if len(picked) >= per:
                break
        out[lid] = {"count": c, "reviews": picked}
    return out


def pick_reviews(res, byid, n=6):
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


def fetch_availability(tok, records, days=400):
    """Pré-charge dispo + prix/nuit par logement via /listings/{id}/calendar.
    Écrit avail/{id}.json compact (jours dispo → prix de base). Le token reste
    côté CI : il n'est JAMAIS exposé au navigateur (site statique)."""
    import time, datetime
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "avail")
    os.makedirs(out_dir, exist_ok=True)
    start = datetime.date.today()
    end = start + datetime.timedelta(days=days)
    ok = 0
    for r in records:
        lid = r["id"]
        try:
            cal = api_get(f"/listings/{lid}/calendar", tok,
                          {"startDate": start.isoformat(), "endDate": end.isoformat()})
            rows = cal.get("result", []) or []
        except Exception as e:
            print(f"  calendrier {lid} échoué: {e}")
            continue
        days_map, ms_map = {}, {}
        for row in rows:
            d = row.get("date")
            if not d:
                continue
            status = (row.get("status") or "").lower()
            if not row.get("isAvailable") or status in ("reserved", "blocked", "unavailable"):
                continue
            price = row.get("price")
            if price is None:
                continue
            days_map[d] = int(round(price))
            mstay = row.get("minimumStay") or 0
            if mstay and mstay > 1:
                ms_map[d] = int(mstay)
        payload = {
            "id": lid, "name": r.get("name"),
            "currency": r.get("currency") or "EUR",
            "cleaningFee": r.get("cleaningFee") or 0,
            "deposit": r.get("deposit") or 0,
            "markup": r.get("markup") or 1.0,
            "minNights": r.get("minNights") or 1,
            "instant": r.get("instant") or 0,
            "guests": r.get("guests") or 0,
            "updated": os.environ.get("BUILD_DATE", start.isoformat()),
            "days": days_map,
        }
        if ms_map:
            payload["minStay"] = ms_map
        with open(os.path.join(out_dir, f"{lid}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        ok += 1
        time.sleep(0.12)
    print(f"avail/ : {ok}/{len(records)} calendriers pré-chargés")
    return ok


def write_seo(records):
    """robots.txt + sitemap.xml (accueil, catalogue, propriétaires, légal + 1 URL/logement)."""
    import datetime
    here = os.path.dirname(os.path.abspath(__file__))
    today = os.environ.get("BUILD_DATE", datetime.date.today().isoformat())
    with open(os.path.join(here, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    urls = []
    def u(loc, prio, freq):
        urls.append(f"  <url><loc>{SITE}/{loc}</loc><lastmod>{today}</lastmod>"
                    f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
    u("", "1.0", "daily")
    u("catalogue.html", "0.9", "daily")
    u("proprietaires.html", "0.8", "weekly")
    u("a-propos.html", "0.6", "monthly")
    u("guides.html", "0.6", "weekly")
    u("guide-week-end-vignobles.html", "0.5", "monthly")
    u("guide-saone-et-loire-en-famille.html", "0.5", "monthly")
    u("guide-cote-chalonnaise.html", "0.5", "monthly")
    u("mentions-legales.html", "0.2", "yearly")
    u("confidentialite.html", "0.2", "yearly")
    for r in records:
        u(f"bien/{r['id']}/", "0.7", "weekly")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(here, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"sitemap.xml : {len(urls)} URLs ; robots.txt écrit")


def build_dispo_index(days=400):
    """Consolide les dispos de tous les avail/{id}.json en UN seul dispo.json (bitmap compact)
    → recherche par dates sur le catalogue sans charger 122 fichiers côté navigateur."""
    import datetime, glob
    here = os.path.dirname(os.path.abspath(__file__))
    base = datetime.date.today()
    idx = {}
    for fp in glob.glob(os.path.join(here, "avail", "*.json")):
        try:
            data = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        lid = str(data.get("id") or os.path.splitext(os.path.basename(fp))[0])
        daymap = data.get("days") or {}
        # prix de base par nuit (0 = indisponible) → sert au filtre ET au calcul du prix du séjour
        idx[lid] = [int(daymap.get((base + datetime.timedelta(days=i)).isoformat()) or 0) for i in range(days)]
    with open(os.path.join(here, "dispo.json"), "w", encoding="utf-8") as f:
        json.dump({"base": base.isoformat(), "days": days, "listings": idx}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"dispo.json : {len(idx)} logements (fenêtre {days} j)")


def generate_listing_pages(records):
    """Génère bien/{id}/index.html à partir du gabarit logement.html : title/description
    uniques, Open Graph, JSON-LD LodgingBusiness, repli <noscript>. Chaque logement a ainsi
    une URL propre indexable (≠ logement.html?id= rendu 100 % en JavaScript)."""
    import html as _h
    here = os.path.dirname(os.path.abspath(__file__))
    tpl_path = os.path.join(here, "logement.html")
    if not os.path.exists(tpl_path):
        print("logement.html introuvable — pages logement non générées"); return
    tpl = open(tpl_path, encoding="utf-8").read()
    e = lambda s: _h.escape(str(s), quote=True)
    n = 0
    for r in records:
        lid = r["id"]
        name = r.get("name") or f"Logement {lid}"
        city = r.get("city") or "Bourgogne"
        typ = r.get("type") or ""
        url = f"{SITE}/bien/{lid}/"
        cover = r.get("cover") or ""
        cover_abs = cover if str(cover).startswith("http") else (SITE + cover if cover else "")
        photo0 = ((r.get("photos") or [None])[0]) or cover
        desc = re.sub(r"\s+", " ", (r.get("description") or "")).strip()
        if len(desc) > 158:
            desc = desc[:158].rsplit(" ", 1)[0] + "…"
        if not desc:
            desc = (f"{name} à {city} : jusqu'à {r.get('guests') or 2} voyageurs. Location de "
                    f"tourisme en Bourgogne, réservation en direct sans frais de plateforme.")
        title = f"{name} · {city}" + (f" · {typ}" if typ else "") + " | SH Développement"
        ld = {
            "@context": "https://schema.org", "@type": "LodgingBusiness",
            "name": name, "url": url, "image": ([cover_abs] if cover else []),
            "address": {"@type": "PostalAddress", "addressLocality": city,
                        "addressRegion": "Bourgogne-Franche-Comté", "addressCountry": "FR"},
            "priceRange": (f"À partir de {r.get('price')} € / nuit" if r.get("price") else "€€"),
            "telephone": "+33659327710",
        }
        if r.get("lat") and r.get("lng"):
            ld["geo"] = {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lng"]}
        if r.get("rating"):
            ld["aggregateRating"] = {"@type": "AggregateRating",
                                     "ratingValue": round(float(r["rating"]) / 2, 1),
                                     "bestRating": 5, "worstRating": 0}
            if r.get("reviewCount"):
                ld["aggregateRating"]["reviewCount"] = r["reviewCount"]
        if r.get("amenities"):
            ld["amenityFeature"] = [{"@type": "LocationFeatureSpecification", "name": a}
                                    for a in r["amenities"][:12]]
        head = (
            f'<title>{e(title)}</title>\n'
            f'<meta name="description" content="{e(desc)}">\n'
            f'<link rel="canonical" href="{url}">\n'
            '<meta property="og:type" content="website">\n'
            '<meta property="og:site_name" content="SH Développement">\n'
            '<meta property="og:locale" content="fr_FR">\n'
            f'<meta property="og:title" content="{e(title)}">\n'
            f'<meta property="og:description" content="{e(desc)}">\n'
            f'<meta property="og:url" content="{url}">\n'
            + (f'<meta property="og:image" content="{e(cover_abs)}">\n' if cover else '')
            + '<meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:title" content="{e(title)}">\n'
            f'<meta name="twitter:description" content="{e(desc)}">\n'
            + (f'<meta name="twitter:image" content="{e(cover_abs)}">\n' if cover else '')
            + (f'<link rel="preload" as="image" href="{e(photo0)}" fetchpriority="high">\n' if photo0 else '')
            + '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + '</script>'
        )
        page = tpl.replace('<title>Logement | SH Développement</title>', head)
        emb = json.dumps(r, ensure_ascii=False).replace('</', '<\\/')
        page = page.replace(
            "const id = parseInt(new URLSearchParams(location.search).get('id'), 10);",
            f"window.__PREL = {emb};\nconst id = {lid};")
        # chemins absolus (la page vit dans /bien/{id}/)
        page = page.replace('src="img/', 'src="/img/').replace('href="index.html', 'href="/index.html')
        noscript = (
            f'<noscript><div class="py-8"><h1 class="font-display text-4xl font-600">{e(name)}</h1>'
            f'<p class="text-muted mt-2">{e(city)}, Bourgogne · {r.get("guests") or 2} voyageurs</p>'
            + (f'<img src="{e(cover)}" alt="{e(name)}" class="rounded-2xl mt-4 w-full max-w-2xl">' if cover else '')
            + f'<p class="mt-4 max-w-2xl leading-relaxed">{e(desc)}</p>'
            '<p class="mt-4"><a class="underline" href="/catalogue.html">Voir toutes nos locations</a> · '
            '<a class="underline" href="tel:+33659327710">06 59 32 77 10</a></p></div></noscript>')
        page = page.replace('<div id="content" class="hidden"></div>',
                            '<div id="content" class="hidden"></div>\n  ' + noscript)
        out_dir = os.path.join(here, "bien", str(lid))
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
        n += 1
    print(f"bien/ : {n} pages logement statiques générées (SEO + Open Graph + JSON-LD)")


def build_cities(records):
    """cities.json — villes + nb de logements, pour l'autocomplétion du champ Destination."""
    cnt = {}
    for r in records:
        c = (r.get("city") or "").strip()
        if c:
            cnt[c] = cnt.get(c, 0) + 1
    cities = [{"name": k, "n": v} for k, v in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))]
    with open("cities.json", "w", encoding="utf-8") as f:
        json.dump({"cities": cities}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"cities.json : {len(cities)} villes")




def localize_images(records):
    """Auto-héberge en WebP optimisé la couverture + les 5 premières photos de chaque logement
    (S3 Hostaway sert ~500 Ko/photo en HTTP/1.1 ; on sert ~60-120 Ko depuis notre domaine en HTTP/2).
    Les URLs des records sont réécrites vers /img/l/{id}-{k}.webp ; le reste de la galerie reste sur S3."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow absent : photos laissées sur S3"); return
    import io, urllib.request
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "img", "l")
    os.makedirs(d, exist_ok=True)
    wanted, done, fail = set(), 0, 0
    for r in records:
        jobs = []
        if r.get("cover"):
            jobs.append(("c", r["cover"], 800))
        for i, u in enumerate((r.get("photos") or [])[:5]):
            jobs.append((str(i), u, 1200 if i == 0 else 700))
        for k, u, width in jobs:
            if not str(u).startswith("http"):
                wanted.add(os.path.basename(str(u))); continue
            name = f"{r['id']}-{k}.webp"
            out = os.path.join(d, name)
            if not os.path.exists(out):
                try:
                    data = urllib.request.urlopen(u, timeout=30).read()
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                    if im.width > width:
                        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                    im.save(out, "WEBP", quality=78, method=6)
                    done += 1
                except Exception:
                    fail += 1
                    continue
            wanted.add(name)
            path = f"/img/l/{name}"
            if k == "c":
                small = out.replace("-c.webp", "-c480.webp")
                if not os.path.exists(small):
                    try:
                        im = Image.open(out)
                        if im.width > 480:
                            im = im.resize((480, round(im.height * 480 / im.width)), Image.LANCZOS)
                        im.save(small, "WEBP", quality=76, method=6)
                    except Exception:
                        pass
                if os.path.exists(small):
                    wanted.add(os.path.basename(small))
                r["cover"] = path
            else:
                r["photos"][int(k)] = path
    for fn in os.listdir(d):
        if fn.endswith(".webp") and fn not in wanted:
            os.remove(os.path.join(d, fn))
    print(f"img/l : {done} nouvelles images optimisées, {fail} échecs, {len(wanted)} référencées")




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
    localize_images(records)

    # Galerie « nos biens d'exception » : sélection CURÉE par le client (8 logements choisis à la
    # main), données rafraîchies chaque jour depuis Hostaway. Affichée par prix décroissant ;
    # complétée par les plus chers si un id venait à manquer (logement retiré / sans prix).
    FEATURED_PINNED = [
        470939,  # Le Verger Secret (Saint-Loup-de-Varennes)
        465573,  # Chalon Hacienda
        570611,  # Le Chai des Écluses gîtes 4* (Saint-Léger-sur-Dheune / CHASSIGNEUX)
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
        all_reviews = fetch_all_reviews(tok)
        reviews = pick_reviews(all_reviews, byid)
        per_listing_reviews = aggregate_listing_reviews(all_reviews)
        for r in records:
            pr = per_listing_reviews.get(r["id"])
            if pr:
                r["reviewCount"] = pr["count"]
                r["reviews"] = pr["reviews"]
        print(f"avis : {len(all_reviews)} récupérés, {len(per_listing_reviews)} logements notés")
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

    # Réservation directe : pré-chargement dispo/prix (token côté CI) + socle SEO + pages statiques
    if os.environ.get("SKIP_AVAIL") != "1":
        try:
            fetch_availability(tok, records)
        except Exception as e:
            print("disponibilités échouées:", e)
    write_seo(records)
    build_dispo_index()
    build_cities(records)
    generate_listing_pages(records)


if __name__ == "__main__":
    main()
