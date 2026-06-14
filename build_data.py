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
# Logements mis en avant dans la galerie « plus belles » (ordre conservé)
FEATURED_IDS = [465405, 475670, 465573, 468463, 470948, 465755]
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

    # Galerie : logements mis en avant, données rafraîchies depuis Hostaway
    byid = {l.get("id"): l for l in listings}
    featured = []
    for lid in FEATURED_IDS:
        l = byid.get(lid)
        if not l:
            continue
        featured.append({
            "id": lid,
            "name": clean_name(l.get("name") or l.get("internalListingName") or f"Logement {lid}"),
            "city": l.get("city") or "",
            "guests": l.get("personCapacity") or 0,
            "bedrooms": l.get("bedroomsNumber") or 0,
            "price": int(round(l.get("price") or 0)),
            "rating": l.get("averageReviewRating"),
            "cover": cover_url(l),
        })

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
        "reviews": reviews,
    }
    if os.environ.get("BUILD_DATE"):
        out["updated"] = os.environ["BUILD_DATE"]

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"data.json écrit : {out['count']} logements, {out['communes']} communes, "
          f"types={adr}, {len(featured)} en vedette, {len(reviews)} avis réels")


if __name__ == "__main__":
    main()
