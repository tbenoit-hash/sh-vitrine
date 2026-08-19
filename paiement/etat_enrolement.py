#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Où en sont les propriétaires dans leur inscription Stripe ?

  python3 etat_enrolement.py            # mode test
  python3 etat_enrolement.py --live     # comptes réels
  python3 etat_enrolement.py --live --relance   # liste des adresses à relancer

Trois états :
  PRÊT      capacité de virement active, le logement peut être payé en ligne
  EN COURS  formulaire commencé, Stripe attend encore des pièces
  RIEN      lien jamais ouvert (aucune info fournie)
"""
import os, sys, csv, json, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = "--live" in sys.argv
SUF = ".live" if LIVE else ""
CONFIG = os.path.join(HERE, f"split-config{SUF}.json")
LINKS = os.path.join(HERE, f"liens_proprietaires{SUF}.csv")


def key():
    k = os.environ.get("STRIPE_SECRET_KEY")
    if not k and os.path.exists(os.path.join(HERE, ".stripe_key")):
        k = open(os.path.join(HERE, ".stripe_key"), encoding="utf-8").read().strip()
    if not k:
        sys.exit("Clé Stripe absente (.stripe_key ou STRIPE_SECRET_KEY).")
    if LIVE and not k.startswith("sk_live"):
        sys.exit("--live demandé mais la clé est une clé de test.")
    return k


def compte(k, acct):
    req = urllib.request.Request(f"https://api.stripe.com/v1/accounts/{acct}",
                                 headers={"Authorization": "Bearer " + k})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        return {"_erreur": str(e)}


def main():
    if not os.path.exists(CONFIG):
        sys.exit(f"{os.path.basename(CONFIG)} absent.")
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    noms = {r["email"]: r for r in csv.DictReader(open(LINKS, encoding="utf-8"))} \
        if os.path.exists(LINKS) else {}
    k = key()

    lignes, relance = [], []
    for memo, o in (cfg.get("_owners") or {}).items():
        email = memo.split("|")[0]
        acct = o.get("acct")
        if not acct:
            continue
        a = compte(k, acct)
        caps = (a.get("capabilities") or {})
        due = (a.get("requirements") or {}).get("currently_due") or []
        pret = caps.get("transfers") == "active"
        commence = bool(a.get("details_submitted")) or len(due) < 8
        etat = "PRÊT" if pret else ("EN COURS" if commence else "RIEN")
        nb = len(noms.get(email, {}).get("nb_logements", "") or "") and noms[email]["nb_logements"]
        lignes.append((etat, o.get("nom") or email, email, nb or "?", len(due)))
        if not pret:
            relance.append(email)

    ordre = {"RIEN": 0, "EN COURS": 1, "PRÊT": 2}
    lignes.sort(key=lambda x: (ordre[x[0]], x[1]))
    for etat, nom, email, nb, due in lignes:
        print(f"  {etat:9} {nom:34.34} {email:32.32} {nb:>3} logt  {due} info(s) manquante(s)")
    tot = len(lignes)
    prets = sum(1 for l in lignes if l[0] == "PRÊT")
    print(f"\n{prets}/{tot} propriétaires prêts" + ("  (mode TEST)" if not LIVE else ""))
    if "--relance" in sys.argv and relance:
        print("\nÀ relancer :\n" + ",".join(relance))


if __name__ == "__main__":
    main()
