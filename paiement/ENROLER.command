#!/bin/bash
# Enrôlement des propriétaires SH sur Stripe Connect.
# Double-clique ce fichier : il fait tout, y compris vérifier que la clé
# correspond bien au compte sur lequel tourne le serveur de paiement.

cd "$(dirname "$0")" || exit 1
PLATEFORME="acct_1OH9dWDCZCsOrNRp"   # SH-développement (compte du worker)

printf '\n=== Enrôlement des propriétaires · SH Développement ===\n\n'

# 1) Récupérer la clé : fichier existant, sinon presse-papiers, sinon saisie
if [ -s .stripe_key ]; then
  KEY=$(cat .stripe_key)
  echo "Clé déjà enregistrée, je la réutilise."
else
  CLIP=$(pbpaste 2>/dev/null | tr -d '[:space:]')
  case "$CLIP" in
    sk_test_*|sk_live_*)
      echo "J'ai trouvé une clé Stripe dans ton presse-papiers."
      printf "L'utiliser ? [O/n] "
      read -r REP
      case "$REP" in [Nn]*) KEY="" ;; *) KEY="$CLIP" ;; esac
      ;;
  esac
  if [ -z "$KEY" ]; then
    printf "Colle ta clé Stripe puis Entrée (rien ne s'affichera) : "
    stty -echo; read -r KEY; stty echo; printf '\n'
  fi
fi

case "$KEY" in
  sk_test_*|sk_live_*) : ;;
  *) printf '\n❌ Ce n'"'"'est pas une clé secrète Stripe (elle doit commencer par sk_test_ ou sk_live_).\n'; printf '\nAppuie sur Entrée pour fermer.'; read -r _; exit 1 ;;
esac

# 2) Vérifier que la clé pointe vers le bon compte
printf '\nVérification du compte Stripe…\n'
COMPTE=$(curl -s https://api.stripe.com/v1/account -u "$KEY:" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id') or ('ERREUR: '+str((d.get('error') or {}).get('message'))))" 2>/dev/null)

case "$COMPTE" in
  ERREUR*) printf '\n❌ Stripe refuse cette clé.\n   %s\n' "$COMPTE"
           printf '\nAppuie sur Entrée pour fermer.'; read -r _; exit 1 ;;
esac

if [ "$COMPTE" != "$PLATEFORME" ]; then
  printf '\n⚠️  ATTENTION : cette clé appartient au compte %s\n' "$COMPTE"
  printf '   Or le serveur de paiement tourne sur %s (SH-développement).\n' "$PLATEFORME"
  printf '   Les comptes propriétaires seraient créés sur la mauvaise plateforme\n'
  printf '   et tous les paiements échoueraient.\n\n'
  printf '   Reprends la clé de test du compte SH-développement.\n'
  printf '\nAppuie sur Entrée pour fermer.'; read -r _; exit 1
fi
printf '✅ Compte %s : c'"'"'est le bon.\n' "$COMPTE"

# 3) Mémoriser la clé pour les prochaines fois
printf '%s' "$KEY" > .stripe_key
chmod 600 .stripe_key

# 4) Lancer l'enrôlement
printf '\nCréation des comptes propriétaires…\n\n'
STRIPE_SECRET_KEY="$KEY" python3 onboard_proprietaires.py
CODE=$?

printf '\n'
if [ $CODE -eq 0 ]; then
  printf '✅ Terminé. Préviens Claude, il prend la suite.\n'
else
  printf '❌ Échec (code %s). Envoie cet écran à Claude.\n' "$CODE"
fi
printf '\nAppuie sur Entrée pour fermer cette fenêtre.'
read -r _
