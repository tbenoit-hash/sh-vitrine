#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit partners.json : les logements de conciergeries PARTENAIRES
(cross-listing « vitrine + renvoi »), tirés de LEUR compte Hostaway via un token
en LECTURE qu'elles nous transmettent.

Chaque fiche partenaire porte :
  - partner  : { slug, label, area, url }   -> badge affiché sur la carte
  - external : 1                            -> le front n'affiche PAS le moteur SH
  - bookUrl  : lien « Réserver » qui RENVOIE vers le moteur du partenaire
               (la résa tombe dans SON Hostaway -> aucune double réservation,
                aucun paiement géré de notre côté)

Config : partners.config.json (slug, noms des variables d'env des identifiants,
gabarit d'URL de réservation). Les identifiants par partenaire vivent dans
l'environnement (ou ../.env en local) — JAMAIS commités, JAMAIS exposés au
navigateur (site statique : le token reste côté CI).

No-op sûr : si aucun partenaire n'a d'identifiants présents, écrit un partners.json
vide (count 0). Le build quotidien ne casse jamais.
"""
import os, json, urllib.parse, urllib.request
import build_data as bd   # réutilise API / api_get / prop_record / AMENITY_FR…

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "partners.config.json")


def load_env_keys(keys):
    """Charge KEY=VALUE depuis ../.env (local) pour les clés demandées."""
    envp = os.path.join(HERE, "..", ".env")
    if not os.path.exists(envp):
        return
    wanted = set(k for k in keys if k)
    for line in open(envp, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k in wanted and not os.environ.get(k):
            os.environ[k] = v.strip().strip('"').strip("'")


def get_token(acc, key):
    """Token Hostaway du compte PARTENAIRE (client_credentials, lecture)."""
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": acc,
        "client_secret": key, "scope": "general"}).encode()
    req = urllib.request.Request(bd.API + "/accessTokens", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-control": "no-cache"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]


def book_url(p, lid):
    """Lien « Réserver » sortant : map explicite > gabarit {id} > repli site partenaire."""
    m = (p.get("book_url_map") or {})
    if str(lid) in m:
        return m[str(lid)]
    tpl = p.get("book_url_template") or ""
    if tpl:
        return tpl.format(id=lid)
    return p.get("fallback_book_url") or p.get("url") or ""


def fetch_feed(url):
    """Flux JSON public publié par le partenaire (même schéma que notre catalogue.json).
    Aucune clé échangée : chacun publie ses logements, l'autre les lit."""
    req = urllib.request.Request(url, headers={"User-Agent": "SH-partners/1.0"})
    raw = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if isinstance(raw, dict):
        return raw.get("listings") or raw.get("result") or []
    return raw if isinstance(raw, list) else []


def record_from_item(it, p, meta):
    """Fiche partenaire à partir d'un item de flux ; recalcule la position carte."""
    lid = it.get("id")
    r = dict(it)
    lat, lng = it.get("lat"), it.get("lng")
    if lat is not None and lng is not None:
        r["mapx"], r["mapy"] = bd.map_pos(lat, lng)
    r["partner"] = meta
    r["external"] = 1
    r["bookUrl"] = it.get("bookUrl") or book_url(p, lid)
    r["uid"] = f"{p['slug']}-{lid}"
    return r


def fetch_partner(p):
    meta = {"slug": p["slug"], "label": p.get("label", p["slug"]),
            "area": p.get("area", ""), "url": p.get("url", "")}

    # Mode préféré : flux public publié par le partenaire (aucune clé partagée)
    feed = p.get("feed_url")
    if feed:
        items = fetch_feed(feed)
        items = [it for it in items if it.get("id") and (it.get("price") or it.get("cover"))]
        recs = [record_from_item(it, p, meta) for it in items]
        print(f"  {p['slug']}: {len(recs)} logements (flux {feed})")
        return meta, recs

    # Repli : token Hostaway en lecture du partenaire
    acc = os.environ.get(p.get("account_env", ""))
    key = os.environ.get(p.get("key_env", ""))
    if not acc or not key:
        print(f"  {p['slug']}: ni feed_url, ni identifiants ({p.get('account_env')}/{p.get('key_env')}) — ignoré")
        return None, []
    tok = get_token(acc, key)
    listings = bd.api_get("/listings", tok, {"limit": 500}).get("result", [])
    listings = [l for l in listings if l.get("price")]
    recs = []
    for l in listings:
        r = bd.prop_record(l)
        r["partner"] = meta            # badge « Partenaire · <label> »
        r["external"] = 1              # CTA sortant, pas de moteur SH
        r["bookUrl"] = book_url(p, r["id"])
        r["uid"] = f"{p['slug']}-{r['id']}"   # évite toute collision d'id avec les fiches SH
        recs.append(r)
    print(f"  {p['slug']}: {len(recs)} logements (token Hostaway)")
    return meta, recs


def main():
    cfg = {"partners": []}
    if os.path.exists(CONFIG):
        cfg = json.load(open(CONFIG, encoding="utf-8"))
    else:
        print("partners.config.json absent — partners.json vide")
    partners = cfg.get("partners", [])

    # identifiants éventuels depuis ../.env (en local ; en CI ce sont des secrets)
    keys = []
    for p in partners:
        keys += [p.get("account_env", ""), p.get("key_env", "")]
    load_env_keys(keys)

    metas, listings = [], []
    for p in partners:
        try:
            meta, recs = fetch_partner(p)
        except Exception as e:
            print(f"  {p.get('slug')}: échec {e}")
            continue
        if meta and recs:
            metas.append({**meta, "count": len(recs)})
            listings += recs

    out = {"count": len(listings), "partners": metas, "listings": listings}
    if os.environ.get("BUILD_DATE"):
        out["updated"] = os.environ["BUILD_DATE"]
    with open(os.path.join(HERE, "partners.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"partners.json écrit : {len(listings)} logements, {len(metas)} partenaire(s)")


if __name__ == "__main__":
    main()
