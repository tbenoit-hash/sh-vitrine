# Serveur de paiement SH-Développement (Stripe Connect + Hostaway)

Serveur (Cloudflare Worker) qui permet au voyageur de **payer sa réservation
directement sur sh-developpement.fr** avec **paiement scindé** : la part
« location » va **directement sur le compte bancaire du propriétaire**, SH
reçoit uniquement **commission + frais de dossier + ménage**. La réservation est
ensuite créée **automatiquement dans Hostaway**.

> **Conformité** : SH ne détient jamais l'argent des propriétaires. C'est Stripe
> (établissement de paiement agréé) qui encaisse et répartit. Un logement dont le
> propriétaire n'est pas enrôlé **ne peut pas être payé en ligne** (le site garde
> alors le flux « demande de réservation »). Faire valider le montage une fois
> par le conseil juridique avant la mise en production.

## La répartition (décision du 06/08/2026)

Pour un séjour de 3 nuits × 200 € avec 300 € de ménage (frais de dossier 5 %) :

| Qui | Reçoit | Détail |
|---|---|---|
| Voyageur paie | 930 € | 600 € hébergement × 1,05 + 300 € ménage |
| → Propriétaire | 480 € | hébergement × (1 − commission 20 %) · **virement direct Stripe** |
| → SH | 450 € | 120 € commission + 30 € frais de dossier + 300 € ménage |

Les commissions par logement (20 % par défaut, 2 % Beguet…) sont dans
`split-config.json` (**jamais committé**, poussé dans Cloudflare KV).

> ⚠️ **État** : code **écrit et testé en local** (`npm test` = 25/25). Rien n'est
> branché sur le site tant que `PAY_API` (logement.html) est vide.

## Étapes de mise en service

### 1. Activer Stripe Connect (action Terence, une fois, ~5 min)
Dashboard Stripe → **Connect** → Get started (plateforme, France). C'est là que
les conditions Connect sont acceptées ; personne d'autre ne peut le faire.

### 2. Enrôler les propriétaires
Créer `proprietaires.csv` (colonnes `email,nom,listings,commission` ;
`listings` = IDs Hostaway séparés par des espaces ; `commission` vide = 20 %) puis :
```bash
STRIPE_SECRET_KEY=sk_test_… python3 onboard_proprietaires.py
```
→ crée les comptes Express + écrit `split-config.json` + `onboarding_links.csv`
(un lien par proprio, à envoyer par email : chacun renseigne identité + IBAN
chez Stripe, SH ne voit jamais l'IBAN). Liens valides ~15 min → regénérer au
besoin avec `--links`.

### 3. Déployer le worker
```bash
cd paiement
wrangler login
wrangler kv namespace create SPLIT_KV        # coller l'id dans wrangler.toml
wrangler kv key put --binding SPLIT_KV config --path split-config.json --remote
wrangler secret put STRIPE_SECRET_KEY        # sk_test_… d'abord
wrangler secret put HOSTAWAY_ACCOUNT_ID      # 136426
wrangler secret put HOSTAWAY_API_KEY
wrangler deploy                              # → noter l'URL, la mettre dans WORKER_URL, redéployer
```
Puis dashboard Stripe → Développeurs → **Webhooks** → ajouter
`https://…workers.dev/webhook` (événement `checkout.session.completed`) et :
```bash
wrangler secret put STRIPE_WEBHOOK_SECRET    # whsec_…
```

### 4. Brancher le site
Dans `logement.html` : `const PAY_API = "https://…workers.dev";` puis rebuild +
push. Le bouton devient « Payer et réserver » pour les logements enrôlés.

### 5. Tester puis passer en production
Mode test (sk_test, carte 4242 4242 4242 4242) de bout en bout : paiement →
webhook → réservation Hostaway → répartition visible dans Stripe. Ensuite
remplacer par `sk_live_…` + webhook live, **après validation juridique**.

## Endpoints
- `POST /create-payment` — appelé par la fiche logement → `{ payment_url }` (Stripe Checkout).
  Refuse (`409 owner_not_onboarded`) si le propriétaire n'est pas enrôlé.
- `POST /webhook` — Stripe → vérification (signature + re-fetch GET) → réservation Hostaway.
- `GET /health` — test de vie.

## Garanties intégrées
- Prix **recalculé côté serveur** depuis le calendrier Hostaway (anti-fraude),
  disponibilité revérifiée au moment du paiement.
- 3-D Secure demandé systématiquement.
- Webhook : signature Stripe vérifiée (si `STRIPE_WEBHOOK_SECRET` posé) **et**
  re-lecture authentifiée de la session (on ne fait jamais confiance au POST).
- Page de retour voyageur : `/merci-reservation.html` (dédiée, ≠ merci.html propriétaires).

## À vérifier sur le compte Hostaway
`createHostawayReservation` utilise `channelId: 2000` (réservation directe) — à
confirmer en mode test. La caution (empreinte) reste gérée comme aujourd'hui par
l'équipe ; automatisation possible ensuite (Stripe `setup_future_usage`).
