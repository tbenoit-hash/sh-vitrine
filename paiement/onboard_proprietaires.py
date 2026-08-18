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


STRIPE_V2 = "https://api.stripe.com/v2/core"
STRIPE_V2_VERSION = "2026-07-29.preview"


def stripe_v2(path, payload):
    """Appel Accounts v2 : corps JSON + en-tête de version, contrairement à v1."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        sys.exit("STRIPE_SECRET_KEY manquant (sk_test_… pour commencer).")
    req = urllib.request.Request(
        STRIPE_V2 + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + key,
                 "Stripe-Version": STRIPE_V2_VERSION,
                 "Content-Type": "application/json"},
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b"{}")
        msg = (err.get("error") or {}).get("message") or err
        sys.exit(f"Stripe v2 {path} → {e.code} : {msg}")


def load_config():
    if os.path.exists(CONFIG):
        return json.load(open(CONFIG, encoding="utf-8"))
    return {"default_commission": DEFAULT_COMMISSION}


def _load_key():
    """Clé Stripe : variable d'environnement, sinon fichier local .stripe_key
    (jamais committé). Permet de la déposer une fois et de relancer le script
    sans la retaper — y compris depuis un outil qui ne peut pas la saisir."""
    k = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if k:
        return k
    path = os.path.join(HERE, ".stripe_key")
    if os.path.exists(path):
        k = open(path, encoding="utf-8").read().strip()
        if k:
            os.environ["STRIPE_SECRET_KEY"] = k
            return k
    return ""


def main():
    make_links = "--links" in sys.argv
    if not _load_key():
        sys.exit("Clé Stripe absente. Dépose-la une fois avec :\n"
                 "  read -rs \"K?Clé Stripe : \" && printf '%s' \"$K\" > .stripe_key && chmod 600 .stripe_key && unset K")
    if "--push" in sys.argv:
        print("Pour pousser la config dans Cloudflare KV (après `wrangler kv namespace create SPLIT_KV`) :")
        print(f"  wrangler kv key put --binding SPLIT_KV config --path {CONFIG} --remote")
        return

    if not os.path.exists(CSV_IN):
        sys.exit(f"{CSV_IN} manquant. Colonnes attendues : email,nom,listings,commission")
    cfg = load_config()
    # Clé = (email, nom) et NON l'email seul : une même adresse peut porter
    # plusieurs entités juridiques (ex. Savalli en perso + sa SCI), qui doivent
    # recevoir sur deux comptes bancaires distincts. Regrouper par email seul
    # écraserait silencieusement une des deux et perdrait ses logements.
    owners = {}   # (email, nom) -> {nom, listings[], commission, acct}
    for row in csv.DictReader(open(CSV_IN, encoding="utf-8")):
        email = (row.get("email") or "").strip().lower()
        nom = (row.get("nom") or "").strip()
        if not email:
            continue
        raw = (row.get("commission") or "").strip()
        commission = float(raw) if raw else DEFAULT_COMMISSION
        if not (0 <= commission < 1):
            sys.exit(f"Commission invalide pour {nom} <{email}> : {raw!r}. "
                     f"Le taux s'écrit en décimal (0.02 pour 2 %, 0.20 pour 20 %), pas en pourcentage.")
        key = (email, nom)
        if key in owners:
            sys.exit(f"Ligne en double dans {CSV_IN} pour {nom} <{email}> : fusionne-les d'abord.")
        owners[key] = {
            "nom": nom,
            "email": email,
            "listings": [s for s in (row.get("listings") or "").split() if s.isdigit()],
            "commission": commission,
        }
    attendus = sum(len(o["listings"]) for o in owners.values())
    print(f"[i] {len(owners)} entités, {attendus} logements à couvrir")

    # comptes déjà créés (mémoire = split-config.json, champ _owners)
    known = cfg.get("_owners", {})
    links = []
    for key, o in owners.items():
        email = o["email"]
        memo = email + "|" + o["nom"]
        acct = known.get(memo, {}).get("acct")
        if not acct:
            # Accounts v2, configuration « recipient » : le propriétaire reçoit des
            # virements depuis le solde de la plateforme (paiement à destination).
            # On ne demande PAS la configuration « merchant » : inutile ici, et elle
            # allongerait l'onboarding.
            a = stripe_v2("/accounts", {
                "contact_email": email,
                "display_name": o["nom"][:100],
                "dashboard": "express",
                "identity": {"country": "fr"},
                "defaults": {"responsibilities": {
                    "fees_collector": "application",   # SH supporte les frais Stripe
                    "losses_collector": "application", # SH supporte les soldes négatifs
                }},
                "configuration": {"recipient": {"capabilities": {
                    "stripe_balance": {"stripe_transfers": {"requested": True}}
                }}},
                "include": ["configuration.recipient", "identity", "requirements"],
            })
            acct = a["id"]
            print(f"[OK] compte créé {acct} · {o['nom']} <{email}>")
        known[memo] = {"acct": acct, "nom": o["nom"]}
        for lid in o["listings"]:
            cfg[lid] = {"acct": acct, "commission": o["commission"]}
        if make_links or not known[memo].get("linked"):
            # Onboarding « en amont » (eventually_due) : on collecte tout de suite
            # tout ce que Stripe finira par exiger, pour éviter qu'un virement se
            # bloque des mois plus tard faute d'une pièce manquante.
            link = stripe_v2("/account_links", {
                "account": acct,
                "use_case": {
                    "type": "account_onboarding",
                    "account_onboarding": {
                        "configurations": ["recipient"],
                        "collection_options": {"fields": "eventually_due"},
                        "refresh_url": SITE + "/proprietaires.html",
                        "return_url": SITE + "/merci.html",
                    },
                },
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
