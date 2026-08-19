#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liens d'invitation PERMANENTS pour l'enrôlement Stripe des propriétaires.

Pourquoi : les liens Stripe (AccountLink) écrits dans onboarding_links.csv
expirent en quelques minutes. Envoyés par mail, ils sont morts avant d'être
cliqués. On envoie donc une URL stable du worker :

    https://sh-paiement.sh-developpement.workers.dev/onboard?k=<jeton>

Le worker fabrique un lien Stripe frais à chaque clic (et Stripe le régénère
tout seul via refresh_url si la session expire en cours de route).

Entrées : proprietaires.csv (email,nom,listings,…) + split-config.json (acct par logement)
Sorties : onboard_tokens.json      mémoire jeton -> compte (idempotent, à conserver)
          kv_onboard_bulk.json     à pousser dans Cloudflare KV (clés onb:<jeton>)
          liens_proprietaires.csv  email,nom,nb_logements,url  (pour l'envoi du mail)

Usage :
  python3 liens_proprietaires.py            # génère / complète
  python3 liens_proprietaires.py --push     # rappelle la commande wrangler
"""
import os, sys, csv, json, secrets

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_IN = os.path.join(HERE, "proprietaires.csv")
LIVE = "--live" in sys.argv
SUF = ".live" if LIVE else ""
CONFIG = os.path.join(HERE, f"split-config{SUF}.json")
TOKENS = os.path.join(HERE, f"onboard_tokens{SUF}.json")
BULK = os.path.join(HERE, f"kv_onboard_bulk{SUF}.json")
OUT = os.path.join(HERE, f"liens_proprietaires{SUF}.csv")
WORKER = os.environ.get("WORKER_URL", "https://sh-paiement.sh-developpement.workers.dev")


def main():
    if "--push" in sys.argv:
        print("wrangler kv bulk put --binding SPLIT_KV --remote " + os.path.basename(BULK))
        return

    if not os.path.exists(CONFIG):
        sys.exit(f"{os.path.basename(CONFIG)} absent : lancer d'abord "
                 f"`python3 onboard_proprietaires.py{' --live' if LIVE else ''}`.")
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    tokens = json.load(open(TOKENS, encoding="utf-8")) if os.path.exists(TOKENS) else {}
    by_acct = {v["acct"]: k for k, v in tokens.items() if isinstance(v, dict) and v.get("acct")}

    rows, manquants = [], []
    for r in csv.DictReader(open(CSV_IN, encoding="utf-8")):
        email = (r.get("email") or "").strip()
        nom = (r.get("nom") or "").strip()
        listings = [l for l in (r.get("listings") or "").split() if l]
        accts = {cfg[l]["acct"] for l in listings if isinstance(cfg.get(l), dict) and cfg[l].get("acct")}
        if len(accts) != 1:
            manquants.append((email, nom, sorted(accts)))
            continue
        acct = accts.pop()
        token = by_acct.get(acct)
        if not token:
            token = secrets.token_hex(16)
            tokens[token] = {"acct": acct, "nom": nom, "email": email}
            by_acct[acct] = token
        rows.append({"email": email, "nom": nom, "nb_logements": len(listings),
                     "url": f"{WORKER}/onboard?k={token}"})

    json.dump(tokens, open(TOKENS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump([{"key": f"onb:{t}", "value": json.dumps({"acct": v["acct"], "nom": v["nom"]}, ensure_ascii=False)}
               for t, v in tokens.items()],
              open(BULK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["email", "nom", "nb_logements", "url"])
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} propriétaires -> {os.path.basename(OUT)}")
    if manquants:
        print(f"⚠️ {len(manquants)} sans compte unique (à vérifier) :")
        for e, n, a in manquants:
            print(f"   {n} <{e}> : {a or 'aucun compte'}")
    print("Pousser dans le KV :")
    print("  wrangler kv bulk put --binding SPLIT_KV --remote " + os.path.basename(BULK))


if __name__ == "__main__":
    main()
