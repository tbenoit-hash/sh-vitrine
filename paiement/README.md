# Serveur de paiement SH-Développement (Payplug + Hostaway)

Petit serveur (Cloudflare Worker) qui permet au voyageur de **payer sa réservation
directement sur sh-developpement.fr**, puis crée **automatiquement la réservation
dans Hostaway**. Les clés ne sont jamais dans le navigateur ; le prix est **recalculé
côté serveur** (anti-fraude) ; la carte est gérée par Payplug (certifié PCI-DSS).

> ⚠️ **État** : code **écrit et testé en local** (`npm test` = 18/18). Il devient
> **actif une fois déployé avec tes clés**. Rien n'est encore branché sur le site
> (l'interrupteur `PAY_API` dans `logement.html` est vide → le site reste sur le flux
> « demande de réservation » actuel tant que tu n'as pas déployé).

## Pré-requis (à obtenir)
1. **Compte Payplug** + clés API : `sk_test_…` (test) puis `sk_live_…` (production)
   → via la Caisse d'Épargne / Payplug (cf. mémo Payplug). Idéalement l'offre
   **marketplace (Mangopay)** pour le paiement scindé (voir « Conformité » plus bas).
2. **Compte Cloudflare** (gratuit) — héberge ce worker.
3. **Node.js** (déjà présent en local).

## Tester en local (sans aucune clé)
```bash
cd paiement
npm test          # simule Payplug + Hostaway et vérifie tout le flux
```

## Déployer (≈ 15 min, une fois les comptes ouverts)
```bash
cd paiement
npm i -g wrangler            # ou: npx wrangler ...
wrangler login              # connecte ton compte Cloudflare

# 1) Secrets (chiffrés, jamais dans le code) :
wrangler secret put PAYPLUG_SECRET_KEY     # colle sk_test_… (puis sk_live_… en prod)
wrangler secret put HOSTAWAY_ACCOUNT_ID    # 136426
wrangler secret put HOSTAWAY_API_KEY       # clé Hostaway

# 2) Déploie une 1re fois pour obtenir l'URL du worker :
wrangler deploy
# → note l'URL renvoyée (ex. https://sh-paiement.toncompte.workers.dev)

# 3) Mets cette URL dans wrangler.toml (WORKER_URL) puis redéploie :
wrangler deploy
```

## Brancher le site
Dans `logement.html`, renseigne l'URL du worker :
```js
const PAY_API = "https://sh-paiement.toncompte.workers.dev";
```
Puis régénère + publie (`python3 build_data.py` puis commit/push). Le bouton de la
fenêtre de réservation devient **« Payer et réserver »** et encaisse sur le site.

> Astuce : tu peux mapper un domaine propre `paiement.sh-developpement.fr` sur le worker
> (Cloudflare → Triggers → Custom Domains) ; mets alors cette URL dans `PAY_API` **et** `WORKER_URL`.

## Conformité — le paiement scindé (important)
Pour rester **hors carte G**, l'argent du propriétaire ne doit pas transiter par le
compte de SH. Avec l'offre **Payplug marketplace / Mangopay**, le paiement est **scindé** :
part propriétaire → son compte, commission → SH. Le branchement se fait dans
`worker.js → buildPaymentPayload()` (bloc `payment_split`, marqué TODO) une fois que tu
connais la structure exacte de l'offre, et après avoir **enregistré chaque propriétaire**
comme bénéficiaire (identité + IBAN). Tant que `SPLIT_ENABLED="0"`, le paiement est
encaissé en **simple** → **mode test uniquement** (à valider juridiquement avant la prod).

## À vérifier sur le compte Hostaway
La création de réservation (`worker.js → createHostawayReservation`) utilise
`channelId: 2000` (réservation directe) et un jeu de champs standard. À confirmer/ajuster
selon la configuration Hostaway (en mode test d'abord).

## Endpoints du worker
- `POST /create-payment` — appelé par le site → renvoie `{ payment_url }`.
- `POST /webhook` — appelé par Payplug → vérifie le paiement (GET re-fetch) puis crée la résa Hostaway.
- `GET /health` — test de vie.
