#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Campagne d'enrôlement Stripe : un mail personnalisé par propriétaire, avec son
lien d'invitation permanent (voir liens_proprietaires.py).

Envoi depuis tbenoit@sh-developpement.fr via l'API Gmail (GMAIL_REFRESH_TOKEN
de ~/Downloads/.env). Rien n'est envoyé sans --send.

  python3 mail_stripe_proprietaires.py                    # dry-run : qui recevrait quoi
  python3 mail_stripe_proprietaires.py --preview          # aperçu HTML dans le navigateur
  python3 mail_stripe_proprietaires.py --send --only a@b  # un seul envoi (test réel)
  python3 mail_stripe_proprietaires.py --send             # toute la campagne
  python3 mail_stripe_proprietaires.py --send --limit 5   # par vagues

Journal envois_stripe.json : un propriétaire déjà servi n'est jamais réexpédié
(sauf --force).
"""
import os, sys, csv, json, base64, html as H, webbrowser, urllib.request, urllib.parse, time
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE_LINKS = os.path.join(HERE, "liens_proprietaires.live.csv")
LINKS = LIVE_LINKS if os.path.exists(LIVE_LINKS) else os.path.join(HERE, "liens_proprietaires.csv")
LOG = os.path.join(HERE, "envois_stripe.json")
ENV = os.path.expanduser("~/Downloads/.env")
FROM = "tbenoit@sh-developpement.fr"
SUJET = "Réservations en direct : votre compte de versement (5 minutes)"

BRUN, BRUN_F, OR, OR_V, FOND = "#463618", "#2E2410", "#E0AE2C", "#FFD549", "#fbf9f4"


def env(k):
    if not os.environ.get(k) and os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                a, b = line.split("=", 1)
                os.environ.setdefault(a.strip(), b.strip().strip('"').strip("'"))
    return os.environ.get(k)


# ---------------------------------------------------------------- contenu ----
FORMES = ("SCI", "SARL", "SAS", "SASU", "SNC", "EURL", "SCCV", "IMO", "HOLDING")


def appel(nom):
    """« Bonjour Dupont Jean, » pour une personne, « Bonjour, » pour une société :
    écrire « Bonjour SCI Okaïna » ferait trop publipostage."""
    n = (nom or "").strip()
    mots = {m.strip(" -.,").upper() for m in n.replace("-", " ").split()}
    if not n or mots & set(FORMES):
        return "Bonjour,"
    return f"Bonjour {n},"


def texte(nom, nb, url):
    logements = "votre logement" if nb <= 1 else f"vos {nb} logements"
    return f"""{appel(nom)}

Nous ouvrons la réservation en direct sur notre site sh-developpement.fr : les voyageurs pourront réserver et payer {logements} sans passer par Airbnb ni Booking.

Pourquoi c'est intéressant pour vous
Sur une réservation directe, il n'y a pas de commission de plateforme (environ 15 à 18 % du séjour sur Booking, prélevés côté voyageur et côté hôte sur Airbnb). Ce qui n'est plus pris par la plateforme reste dans le séjour : meilleur prix affiché pour le voyageur, meilleure rentabilité pour vous. Nous avons aussi une clientèle qui revient (plus de 160 voyageurs déjà venus plusieurs fois) et qu'il est dommage de repayer à une plateforme à chaque séjour.

Pourquoi vous avez besoin de votre propre compte de versement
Nous ne voulons pas, et n'avons pas le droit, de détenir l'argent de vos locations sur notre compte. L'encaissement est donc confié à Stripe, un établissement de paiement agréé, qui répartit automatiquement chaque paiement :

  . votre part de la location part directement sur VOTRE compte bancaire ;
  . nous ne recevons que notre commission de gestion et le ménage.

Concrètement, vous êtes payé automatiquement par Stripe, sans attendre le relevé mensuel, et vous voyez chaque versement dans votre espace. Votre IBAN est saisi chez Stripe : nous ne le voyons jamais.

Ce que nous vous demandons : 5 minutes
1. Ouvrez votre lien personnel : {url}
2. Renseignez le formulaire Stripe : identité, adresse, IBAN, et pièce d'identité (SIRET si le bien est détenu par une société ou une SCI).
3. C'est terminé. La validation est en général immédiate, parfois 24 h.

Gardez ce lien : il reste valable et vous ramène toujours au bon endroit, même plusieurs jours plus tard.

Quelques précisions
. Rien ne change pour vos réservations Airbnb et Booking : même fonctionnement, même relevé mensuel.
. Tant que ce compte n'est pas créé, votre logement reste réservable sur notre site, mais uniquement en demande de réservation, sans paiement en ligne : nous perdons une partie des réservations directes.
. Stripe est le prestataire de paiement de très nombreuses plateformes de réservation. Il gère la sécurité de la carte, la vérification d'identité imposée par la réglementation et les virements.
. Aucun frais supplémentaire pour vous : les frais bancaires sont à notre charge.

Une question, un doute sur le lien ? Répondez simplement à ce message ou appelez-nous.

Terence Benoit
SH Développement
contact@sh-developpement.fr
"""


def corps_html(nom, nb, url):
    logements = "votre logement" if nb <= 1 else f"vos {nb} logements"
    puce = ('<tr><td style="padding:3px 0;font-size:15px;line-height:1.55;">'
            '<span style="color:%s;font-weight:700;">&#8226;</span>&nbsp;%s</td></tr>')
    return f"""<div style="margin:0;background:{FOND};padding:24px 12px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#3a2f25;">
<div style="max-width:620px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,.06);">
  <div style="background:{BRUN};padding:26px 28px;">
    <div style="color:{OR_V};font-size:12px;letter-spacing:.10em;text-transform:uppercase;">SH Développement</div>
    <div style="color:#f4ead6;font-size:22px;font-weight:700;margin-top:8px;line-height:1.3;">La réservation en direct arrive</div>
    <div style="color:{OR};font-size:14px;margin-top:6px;">5 minutes pour créer votre compte de versement</div>
  </div>

  <div style="padding:24px 28px;font-size:15px;line-height:1.62;">
    <p style="margin:0 0 14px;">{H.escape(appel(nom))}</p>
    <p style="margin:0 0 16px;">Nous ouvrons la réservation en direct sur notre site
      <a href="https://www.sh-developpement.fr" style="color:{BRUN};font-weight:600;">sh-developpement.fr</a> :
      les voyageurs pourront réserver et payer {logements} sans passer par Airbnb ni Booking.</p>

    <div style="background:{FOND};border-left:3px solid {OR};padding:14px 16px;border-radius:0 8px 8px 0;margin:0 0 18px;">
      <div style="font-weight:700;color:{BRUN};margin-bottom:6px;">Pourquoi c'est intéressant pour vous</div>
      Sur une réservation directe, il n'y a pas de commission de plateforme (environ 15 à 18 % du séjour).
      Ce qui n'est plus pris par la plateforme reste dans le séjour : meilleur prix pour le voyageur,
      meilleure rentabilité pour vous. Nous avons aussi une clientèle fidèle, plus de 160 voyageurs
      déjà venus plusieurs fois, qu'il est dommage de repayer à une plateforme à chaque séjour.
    </div>

    <div style="font-weight:700;color:{BRUN};margin:0 0 8px;">Pourquoi votre propre compte de versement</div>
    <p style="margin:0 0 10px;">Nous ne souhaitons pas détenir l'argent de vos locations sur notre compte, et la
      réglementation ne nous le permet pas. L'encaissement est donc confié à <b>Stripe</b>, un établissement de
      paiement agréé, qui répartit automatiquement chaque paiement :</p>
    <table style="width:100%;border-collapse:collapse;margin:0 0 12px;">
      {puce % (OR, "votre part de la location part <b>directement sur votre compte bancaire</b> ;")}
      {puce % (OR, "nous ne recevons que <b>notre commission de gestion et le ménage</b>.")}
    </table>
    <p style="margin:0 0 20px;">Vous êtes donc payé automatiquement, sans attendre le relevé mensuel, et chaque
      versement est visible dans votre espace. Votre IBAN est saisi chez Stripe : <b>nous ne le voyons jamais</b>.</p>

    <div style="font-weight:700;color:{BRUN};margin:0 0 10px;">Ce que nous vous demandons : 5 minutes</div>
    <table style="width:100%;border-collapse:collapse;margin:0 0 18px;font-size:15px;line-height:1.55;">
      <tr><td style="padding:4px 0;"><b>1.</b> Ouvrez votre lien personnel ci-dessous.</td></tr>
      <tr><td style="padding:4px 0;"><b>2.</b> Renseignez le formulaire Stripe : identité, adresse, IBAN, pièce d'identité (SIRET si le bien est au nom d'une société ou d'une SCI).</td></tr>
      <tr><td style="padding:4px 0;"><b>3.</b> C'est terminé. La validation est en général immédiate, parfois 24 h.</td></tr>
    </table>

    <div style="text-align:center;margin:0 0 8px;">
      <a href="{H.escape(url)}" style="display:inline-block;background:{BRUN};color:{OR_V};text-decoration:none;
        font-weight:700;font-size:16px;padding:14px 30px;border-radius:8px;">Créer mon compte de versement</a>
    </div>
    <div style="text-align:center;color:#9a8a78;font-size:12px;margin:0 0 22px;">
      Lien personnel, valable en permanence : vous pouvez y revenir plus tard.
    </div>

    <div style="font-weight:700;color:{BRUN};margin:0 0 8px;">Quelques précisions</div>
    <table style="width:100%;border-collapse:collapse;margin:0 0 6px;">
      {puce % (OR, "Rien ne change pour vos réservations Airbnb et Booking : même fonctionnement, même relevé mensuel.")}
      {puce % (OR, "Sans ce compte, votre logement reste visible sur notre site mais seulement en demande de réservation, sans paiement en ligne : une partie des réservations directes est perdue.")}
      {puce % (OR, "Stripe est le prestataire de paiement de très nombreuses plateformes de réservation : sécurité de la carte, vérification d'identité imposée par la réglementation, virements.")}
      {puce % (OR, "Aucun frais supplémentaire pour vous : les frais bancaires sont à notre charge.")}
    </table>

    <p style="margin:18px 0 0;">Une question, un doute sur ce lien ? Répondez simplement à ce message ou appelez-nous.</p>
    <p style="margin:16px 0 0;">Terence Benoit<br><span style="color:#6b5b4a;">SH Développement</span></p>
  </div>

  <div style="padding:16px 28px;background:{FOND};color:#9a8a78;font-size:12px;">
    SH Développement &#183; contact@sh-developpement.fr &#183;
    <a href="https://www.sh-developpement.fr" style="color:#9a8a78;">sh-developpement.fr</a>
  </div>
</div></div>"""


# ------------------------------------------------------------------ envoi ----
def access_token():
    data = urllib.parse.urlencode({
        "client_id": env("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": env("GOOGLE_OAUTH_CLIENT_SECRET"),
        "refresh_token": env("GMAIL_REFRESH_TOKEN"),
        "grant_type": "refresh_token"}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data), timeout=30)
    return json.loads(r.read())["access_token"]


def envoyer(tok, to, nom, nb, url):
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = f"Terence Benoit (SH Développement) <{FROM}>"
    msg["Reply-To"] = FROM
    msg["Subject"] = SUJET
    msg.set_content(texte(nom, nb, url))
    msg.add_alternative(corps_html(nom, nb, url), subtype="html")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode(),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=45).read())


def main():
    a = sys.argv[1:]
    send, force, preview = "--send" in a, "--force" in a, "--preview" in a
    only = a[a.index("--only") + 1] if "--only" in a else None
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else None

    rows = list(csv.DictReader(open(LINKS, encoding="utf-8")))
    if only:
        rows = [r for r in rows if r["email"].lower() == only.lower()]
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {}
    if not force:
        rows = [r for r in rows if r["email"] not in log]
    if limit:
        rows = rows[:limit]

    if preview:
        r = rows[0] if rows else {"nom": "Exemple", "nb_logements": "2", "url": "https://exemple"}
        p = os.path.join(HERE, "apercu_mail_stripe.html")
        open(p, "w", encoding="utf-8").write(corps_html(r["nom"], int(r["nb_logements"]), r["url"]))
        print("Aperçu :", p)
        webbrowser.open("file://" + p)
        return

    print(f"{len(rows)} propriétaire(s) à servir · objet : {SUJET}")
    if not send:
        for r in rows[:10]:
            print(f"  {r['nom']:38.38} {r['email']:34.34} {r['nb_logements']} logement(s)")
        if len(rows) > 10:
            print(f"  … et {len(rows) - 10} autres")
        print("\nDRY-RUN : rien n'a été envoyé. Ajouter --send pour envoyer.")
        return

    if LINKS != LIVE_LINKS:
        sys.exit("STOP : seuls les liens de TEST existent (liens_proprietaires.csv).\n"
                 "Envoyer ces liens ferait saisir aux propriétaires leur véritable IBAN dans un\n"
                 "formulaire Stripe de test, sans aucun effet. Passer d'abord en live :\n"
                 "  python3 onboard_proprietaires.py --live   (avec la clé sk_live_…)\n"
                 "  python3 liens_proprietaires.py --live")

    tok = access_token()
    for i, r in enumerate(rows, 1):
        try:
            res = envoyer(tok, r["email"], r["nom"], int(r["nb_logements"]), r["url"])
            log[r["email"]] = {"id": res.get("id"), "nom": r["nom"], "quand": time.strftime("%Y-%m-%d %H:%M")}
            print(f"  [{i}/{len(rows)}] envoyé -> {r['email']}")
        except Exception as e:
            print(f"  [{i}/{len(rows)}] ÉCHEC {r['email']} : {e}")
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.2)


if __name__ == "__main__":
    main()
