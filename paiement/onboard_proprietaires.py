#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrôlement des propriétaires dans Stripe Connect (comptes Express) pour le
paiement scindé du site : chaque propriétaire renseigne LUI-MÊME son identité
et son IBAN via un lien Stripe (KYC géré par Stripe, SH ne voit jamais l'IBAN).

Entrée  : proprietaires.csv (colonnes : email,nom,listings,commission)
          - listings   = IDs Hostaway séparés par des espaces (ex. "465400 465401")
          - commission = taux décimal, vide = 0.20 (ex. Beguet : 0.02)
Sorties : split-config.json      (config du worker, à pousser dans Cloudflare KV)
          onboarding_links.csv   (email,nom,url — liens à envoyer aux proprios)

État idempotent : split-config.json sert de mémoire (un proprio déjà doté d'un
compte acct_… n'est pas recréé ; son lien d'onboarding est simplement regénéré
si --links est passé).

Usage :
  STRIPE_SECRET_KEY=sk_test_…  python3 onboard_proprietaires.py            # crée les comptes
  STRIPE_SECRET_KEY=sk_test_…  python3 onboard_proprietaires.py --links    # (re)génère les liens
  python3 onboard_proprietaires.py --push   # affiche la commande wrangler pour pousser la config

⚠️ Pré-requis côté Terence (une fois) : activer Stripe Connect sur le dashboard
   (stripe.com → Connect → Get started, plateforme France) — je ne peux pas
   accepter les conditions Connect à ta place.
⚠️ Ne JAMAIS committer split-config.json ni proprietaires.csv (dans .gitignore) :
   taux de commission par logement = confidentiel.
"""
import os, sys, csv, json, urllib.parse, urllib.request

STRIPE_API = "https://api.stripe.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
CSV_IN = os.path.join(HERE, "proprietaires.csv")
CONFIG = os.path.join(HERE, "split-config.json")
LINKS = os.path.join(HERE, "onboarding_links.csv")
SITE = "https://www.sh-developpement.fr"
DEFAULT_COMMISSION = 0.20


def stripe(path, params=None):
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        sys.exit("STRIPE_SECRET_KEY manquant (sk_test_… pour commencer).")
    data = urllib.parse.urlencode(params).encode() if params is not None else None
    req = urllib.request.Request(STRIPE_API + path, data=data,
                                 headers={"Authorization": "Bearer " + key})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b"{}")
        sys.exit(f"Stripe {path} → {e.code} : {err.get('error', {}).get('message', err)}")


def load_config():
    if os.path.exists(CONFIG):
        return json.load(open(CONFIG, encoding="utf-8"))
    return {"default_commission": DEFAULT_COMMISSION}


def main():
    make_links = "--links" in sys.argv
    if "--push" in sys.argv:
        print("Pour pousser la config dans Cloudflare KV (après `wrangler kv namespace create SPLIT_KV`) :")
        print(f"  wrangler kv key put --binding SPLIT_KV config --path {CONFIG} --remote")
        return

    if not os.path.exists(CSV_IN):
        sys.exit(f"{CSV_IN} manquant. Colonnes attendues : email,nom,listings,commission")
    cfg = load_config()
    owners = {}   # email -> {nom, listings[], commission, acct}
    for row in csv.DictReader(open(CSV_IN, encoding="utf-8")):
        email = (row.get("email") or "").strip().lower()
        if not email:
            continue
        owners[email] = {
            "nom": (row.get("nom") or "").strip(),
            "listings": [s for s in (row.get("listings") or "").split() if s.isdigit()],
            "commission": float(row.get("commission")) if (row.get("commission") or "").strip() else DEFAULT_COMMISSION,
        }

    # comptes déjà créés (mémoire = split-config.json, champ _owners)
    known = cfg.get("_owners", {})
    links = []
    for email, o in owners.items():
        acct = known.get(email, {}).get("acct")
        if not acct:
            a = stripe("/accounts", {
                "type": "express", "country": "FR", "email": email,
                "capabilities[transfers][requested]": "true",
                "business_profile[product_description]": "Location meublée de tourisme (part propriétaire, plateforme SH Développement)",
                "metadata[nom]": o["nom"],
            })
            acct = a["id"]
            print(f"[OK] compte créé {acct} · {o['nom']} <{email}>")
        known[email] = {"acct": acct, "nom": o["nom"]}
        for lid in o["listings"]:
            cfg[lid] = {"acct": acct, "commission": o["commission"]}
        if make_links or not known[email].get("linked"):
            link = stripe("/account_links", {
                "account": acct, "type": "account_onboarding",
                "refresh_url": SITE + "/proprietaires.html",
                "return_url": SITE + "/merci.html",
            })
            links.append({"email": email, "nom": o["nom"], "url": link["url"]})
            known[email]["linked"] = True

    cfg["_owners"] = known
    cfg["default_commission"] = DEFAULT_COMMISSION
    json.dump(cfg, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] {CONFIG} écrit ({sum(1 for k in cfg if k.isdigit())} logements mappés)")

    if links:
        with open(LINKS, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["email", "nom", "url"])
            w.writeheader(); w.writerows(links)
        print(f"[OK] {LINKS} écrit ({len(links)} liens d'inscription, valides ~15 min : à envoyer vite ou regénérer avec --links)")


if __name__ == "__main__":
    main()
