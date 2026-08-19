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

---

## Enrôlement des propriétaires : la campagne mail (19/08/2026)

### Le lien d'invitation est PERMANENT
Un lien Stripe (`AccountLink`) expire en quelques minutes : impossible de
l'envoyer par mail. Le propriétaire reçoit donc une URL stable du worker :

```
https://sh-paiement.sh-developpement.workers.dev/onboard?k=<jeton>
```

`GET /onboard` lit le jeton dans le KV (`onb:<jeton>` = `{acct, nom}`), fabrique
un lien Stripe **frais** et redirige. Stripe rappelle lui-même cette URL
(`refresh_url`) si la session expire en cours de route : le propriétaire ne voit
jamais « lien expiré ». Si son compte est déjà vérifié, il tombe sur une page
« votre compte est déjà validé » au lieu du formulaire.

### Les trois scripts
```bash
python3 onboard_proprietaires.py            # comptes Stripe + split-config.json
python3 liens_proprietaires.py              # jetons + liens permanents + bulk KV
npx wrangler kv bulk put --binding SPLIT_KV --remote kv_onboard_bulk.json
python3 mail_stripe_proprietaires.py            # dry-run : qui recevrait quoi
python3 mail_stripe_proprietaires.py --preview  # aperçu HTML du mail
python3 mail_stripe_proprietaires.py --send --only untel@mail.fr   # 1 envoi réel
python3 mail_stripe_proprietaires.py --send --limit 10             # par vagues
```
`envois_stripe.json` mémorise les envois : personne n'est servi deux fois
(sauf `--force`). Envoi depuis tbenoit@ via l'API Gmail.

### ⚠️ Test et réel ne se mélangent pas
Les 84 comptes créés le 19/08 sont des comptes **de test** (`sk_test_…`). Envoyer
ces liens ferait saisir aux propriétaires leur véritable identité et leur IBAN
dans un formulaire de test, pour rien. `mail_stripe_proprietaires.py --send`
refuse donc de partir tant que `liens_proprietaires.live.csv` n'existe pas.

Bascule en réel (chaque mode a ses propres fichiers, suffixe `.live`) :
```bash
read -rs "K?Clé Stripe LIVE (sk_live_…) : " && printf '%s' "$K" > .stripe_key && chmod 600 .stripe_key && unset K
python3 onboard_proprietaires.py --live        # recrée les 84 comptes en réel
python3 liens_proprietaires.py --live
npx wrangler kv bulk put --binding SPLIT_KV --remote kv_onboard_bulk.live.json
npx wrangler kv key put --binding SPLIT_KV config --path split-config.live.json --remote
npx wrangler secret put STRIPE_SECRET_KEY      # sk_live_…
npx wrangler secret put STRIPE_WEBHOOK_SECRET  # whsec_… du webhook LIVE (à recréer sur /webhook)
npx wrangler deploy
python3 mail_stripe_proprietaires.py --send --only <ton adresse>   # relecture grandeur nature
python3 mail_stripe_proprietaires.py --send --limit 10             # puis vagues
```
Le site ne bascule que lorsque `PAY_API` est renseigné dans `logement.html` :
tant qu'il est vide, aucun voyageur ne peut payer, y compris pour un
propriétaire déjà enrôlé.
