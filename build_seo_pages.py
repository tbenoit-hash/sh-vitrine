#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère les pages SEO « propriétaires » du site SH Développement :
  - 6 pages villes/secteurs  (conciergerie-<slug>.html)
  - 4 articles conseils      (conseils/<slug>.html)
  - 1 hub des conseils       (conseils-proprietaires.html)

Les chiffres (nombre de logements, prix médians, notes) sont recalculés à
chaque exécution depuis catalogue.json : aucune donnée n'est écrite en dur.
Lancé par le workflow quotidien après build_data.py.
"""
import json
import os
import statistics as st
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://www.sh-developpement.fr"
TEL = "+33659327710"
TEL_H = "06 59 32 77 10"
MAIL = "contact@sh-developpement.fr"
TODAY = date.today().isoformat()

# Part réellement reversée au propriétaire dans le simulateur du site
# (net plateforme, après commission de conciergerie).
OWNER_SHARE = 0.72
NIGHTS_MONTH = 30.4


# ─────────────────────────────────────────────────────────────────────────────
#  Données réelles
# ─────────────────────────────────────────────────────────────────────────────
def load_stats():
    with open(os.path.join(HERE, "catalogue.json"), encoding="utf-8") as f:
        listings = json.load(f)["listings"]

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    by_city = defaultdict(list)
    by_type = defaultdict(list)
    for l in listings:
        p = num(l.get("price"))
        if p:
            by_city[l.get("city", "")].append(l)
            by_type[l.get("type", "")].append(p)

    global_med = {t: st.median(v) for t, v in by_type.items() if v}
    return listings, by_city, global_med


def city_block(cities, by_city, global_med):
    """Agrège les stats réelles d'un secteur (une ou plusieurs communes)."""
    items = [l for c in cities for l in by_city.get(c, [])]
    prices = [float(l["price"]) for l in items if l.get("price")]
    ratings = [float(l["rating"]) for l in items if l.get("rating")]
    per_type = defaultdict(list)
    for l in items:
        per_type[l.get("type", "")].append(float(l["price"]))

    rows = []
    for t in ("Studio", "T2", "T3", "T4", "T5", "T6+"):
        local = per_type.get(t, [])
        if len(local) >= 2:
            med, src = st.median(local), "local"
        elif global_med.get(t):
            med, src = global_med[t], "parc"
        else:
            continue
        rows.append({
            "type": t,
            "adr": round(med),
            "src": src,
            "n": len(local),
            "m55": round(med * NIGHTS_MONTH * 0.55 * OWNER_SHARE),
            "m70": round(med * NIGHTS_MONTH * 0.70 * OWNER_SHARE),
        })

    return {
        "n": len(items),
        "median": round(st.median(prices)) if prices else None,
        "rating": round(st.mean(ratings), 1) if ratings else None,
        "nrated": len(ratings),
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Gabarit (repris de proprietaires.html)
# ─────────────────────────────────────────────────────────────────────────────
NAV = """<header id="nav" class="fixed top-0 inset-x-0 z-50 transition-all duration-300">
  <div class="max-w-[1200px] mx-auto px-5 sm:px-8 flex items-center justify-between h-20">
    <a href="/" class="flex items-center gap-3 group" aria-label="SH Développement, accueil">
      <img src="/img/logo_gold.png" alt="" class="h-9 w-auto" id="logo-img">
      <span class="font-display text-2xl font-700 leading-none text-cream" id="logo-txt">SH&nbsp;<span class="text-cream" id="logo-sub">Développement</span></span>
    </a>
    <nav class="hidden lg:flex items-center gap-9 text-sm font-500 text-cream" id="nav-links">
      <a href="/" class="hover:text-bronze">Accueil</a>
      <a href="/proprietaires.html" class="hover:text-bronze">Propriétaires</a>
      <a href="/conseils-proprietaires.html" class="hover:text-bronze">Conseils</a>
      <a href="/catalogue.html" class="hover:text-bronze">Nos locations</a>
      <a href="/proprietaires.html#estimation" class="hover:text-bronze">Simulateur</a>
    </nav>
    <div class="flex items-center gap-2">
      <a href="tel:__TEL__" class="hidden md:inline-flex items-center p-2 -m-1 text-cream hover:text-bronze" id="nav-phone" aria-label="Nous appeler au __TELH__">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
      </a>
      <a href="/proprietaires.html#contact" class="hidden sm:inline-flex items-center gap-2 rounded-full bg-ink text-cream px-5 py-2.5 text-sm font-600 hover:bg-brown cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-cream">
        Demander une estimation
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </a>
      <button id="menu-btn" type="button" aria-label="Ouvrir le menu" aria-expanded="false" aria-controls="mobile-menu" class="lg:hidden inline-flex items-center justify-center w-11 h-11 rounded-xl text-cream hover:bg-cream/10 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-gold">
        <svg id="icon-open" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
        <svg id="icon-close" class="hidden" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
  </div>
  <div id="mobile-menu" class="hidden lg:hidden border-t border-ecru/60 bg-cream/95 backdrop-blur">
    <nav class="max-w-[1200px] mx-auto px-5 py-4 flex flex-col">
      <a href="/" class="py-3 border-b border-ecru/40 font-500 text-ink hover:text-bronze">Accueil</a>
      <a href="/proprietaires.html" class="py-3 border-b border-ecru/40 font-500 text-ink hover:text-bronze">Propriétaires</a>
      <a href="/conseils-proprietaires.html" class="py-3 border-b border-ecru/40 font-500 text-ink hover:text-bronze">Conseils</a>
      <a href="/catalogue.html" class="py-3 border-b border-ecru/40 font-500 text-ink hover:text-bronze">Nos locations</a>
      <a href="tel:__TEL__" class="py-3 border-b border-ecru/40 font-500 text-ink hover:text-bronze">Nous appeler</a>
      <a href="/proprietaires.html#contact" class="mt-4 inline-flex items-center justify-center gap-2 rounded-full bg-ink text-cream px-5 py-3 font-600 hover:bg-brown cursor-pointer">Demander une estimation</a>
    </nav>
  </div>
</header>""".replace("__TEL__", TEL).replace("__TELH__", TEL_H)

FOOTER = """<footer class="bg-ink text-cream/70 mt-16">
  <div class="max-w-[1200px] mx-auto px-5 sm:px-8 pt-14 pb-8">
    <div class="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <a href="/" class="inline-flex items-center gap-3" aria-label="SH Développement, accueil">
          <img src="/img/logo_gold.png" alt="" width="294" height="445" class="h-9 w-auto">
          <span class="font-display text-xl font-700 text-cream leading-none">SH&nbsp;Développement</span>
        </a>
        <p class="text-sm leading-relaxed mt-4 max-w-xs">L'art de séjourner en Bourgogne : locations d'exception et conciergerie sur mesure en Saône-et-Loire.</p>
      </div>
      <nav aria-label="Conciergerie par ville">
        <p class="text-cream/60 text-xs font-600 uppercase tracking-wide mb-4">Conciergerie</p>
        <ul class="space-y-2.5 text-sm">__CITYLINKS__</ul>
      </nav>
      <nav aria-label="Propriétaires">
        <p class="text-cream/60 text-xs font-600 uppercase tracking-wide mb-4">Propriétaires</p>
        <ul class="space-y-2.5 text-sm">
          <li><a href="/proprietaires.html" class="hover:text-gold">Devenir partenaire</a></li>
          <li><a href="/proprietaires.html#estimation" class="hover:text-gold">Estimer mes revenus</a></li>
          <li><a href="/conseils-proprietaires.html" class="hover:text-gold">Conseils propriétaires</a></li>
          <li><a href="/catalogue.html" class="hover:text-gold">Nos locations</a></li>
        </ul>
      </nav>
      <div>
        <p class="text-cream/60 text-xs font-600 uppercase tracking-wide mb-4">Contact</p>
        <ul class="space-y-2.5 text-sm">
          <li><a href="tel:__TEL__" class="hover:text-gold">__TELH__</a></li>
          <li><a href="mailto:__MAIL__" class="hover:text-gold">__MAIL__</a></li>
          <li><span>1 rue Georges Duny<br>71100 Chalon-sur-Saône</span></li>
        </ul>
      </div>
    </div>
    <div class="mt-12 pt-6 border-t border-cream/15 flex flex-col sm:flex-row items-center justify-between gap-3 text-[13px] text-cream/60">
      <p>© 2026 SH Développement · Conciergerie en Bourgogne</p>
      <nav class="flex flex-wrap items-center justify-center gap-x-6 gap-y-2" aria-label="Liens légaux">
        <a href="/mentions-legales.html" class="hover:text-cream">Mentions légales</a>
        <a href="/cgv.html" class="hover:text-cream">CGV</a>
        <a href="/confidentialite.html" class="hover:text-cream">Confidentialité</a>
      </nav>
    </div>
  </div>
</footer>""".replace("__TEL__", TEL).replace("__TELH__", TEL_H).replace("__MAIL__", MAIL)

SCRIPTS = """<script>
const io = new IntersectionObserver((e)=>{e.forEach(x=>{if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target);}})},{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const nav=document.getElementById('nav'), links=document.getElementById('nav-links'), lt=document.getElementById('logo-txt'), ls=document.getElementById('logo-sub'), ph=document.getElementById('nav-phone'), mb=document.getElementById('menu-btn');
function onScroll(){const s=window.scrollY>40;
  nav.classList.toggle('bg-cream/95',s); nav.classList.toggle('backdrop-blur',s); nav.classList.toggle('shadow-sm',s);
  [lt,ls].forEach(el=>{if(el){el.classList.toggle('text-cream',!s);el.classList.toggle('text-ink',s);}});
  if(links){links.classList.toggle('text-cream',!s);links.classList.toggle('text-ink',s);}
  if(ph){ph.classList.toggle('text-cream',!s);ph.classList.toggle('text-ink',s);}
  if(mb){mb.classList.toggle('text-cream',!s);mb.classList.toggle('text-ink',s);}
}
onScroll(); window.addEventListener('scroll',onScroll,{passive:true});
const mm=document.getElementById('mobile-menu'), io_=document.getElementById('icon-open'), ic=document.getElementById('icon-close');
mb&&mb.addEventListener('click',()=>{const o=mm.classList.toggle('hidden');mb.setAttribute('aria-expanded',String(!o));io_.classList.toggle('hidden',!o);ic.classList.toggle('hidden',o);});
</script>
<script defer src="/analytics.js"></script>
<script defer src="/lang.js"></script>"""

HEAD_CSS = """<link rel="preload" as="font" type="font/woff2" href="/fonts/marcellus-latin.woff2" crossorigin>
<link rel="preload" as="font" type="font/woff2" href="/fonts/figtree-latin.woff2" crossorigin>
<link rel="stylesheet" href="/site.css">
<style>
  html { scroll-behavior: smooth; }
  .tracking-luxe { letter-spacing: .28em; }
  .reveal { opacity: 0; transform: translateY(24px); transition: opacity .7s ease-out, transform .7s ease-out; }
  .reveal.in { opacity: 1; transform: none; }
  a, button { transition: color .2s ease, background-color .2s ease, border-color .2s ease, box-shadow .2s ease, transform .2s ease; }
  details.faq > summary { list-style: none; cursor: pointer; }
  details.faq > summary::-webkit-details-marker { display: none; }
  details.faq[open] .faq-chev { transform: rotate(180deg); }
  .faq-chev { transition: transform .25s ease; }
  .prose-sh p { margin-bottom: 1.05rem; line-height: 1.75; }
  .prose-sh h2 { font-family: Marcellus, Georgia, serif; font-size: 1.9rem; margin: 2.6rem 0 1rem; line-height: 1.25; }
  .prose-sh h3 { font-family: Marcellus, Georgia, serif; font-size: 1.3rem; margin: 1.9rem 0 .7rem; }
  .prose-sh ul { margin: 0 0 1.2rem 1.1rem; list-style: disc; }
  .prose-sh li { margin-bottom: .5rem; line-height: 1.7; }
  .prose-sh a { color: #7A5C1E; text-decoration: underline; text-underline-offset: 3px; }
  .prose-sh a.no-underline, .prose-sh .not-prose a { text-decoration: none; }
  h1, h2, h3 { overflow-wrap: break-word; }
  .prose-sh .not-prose a:hover { text-decoration: none; }
  .prose-sh table { width: 100%; border-collapse: collapse; margin: 1.4rem 0; font-size: .95rem; }
  .prose-sh th, .prose-sh td { border-bottom: 1px solid #E4DDD0; padding: .7rem .6rem; text-align: left; }
  .prose-sh th { font-weight: 600; background: #F7F2E9; }
  @media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
    .reveal { opacity: 1 !important; transform: none !important; transition: none; }
  }
</style>"""


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def faq_html(faq):
    out = ['<section class="mt-14"><h2 class="font-display text-3xl mb-6">Questions fréquentes</h2><div class="divide-y divide-ecru">']
    for q, a in faq:
        out.append(
            f'<details class="faq py-4"><summary class="flex items-start justify-between gap-4 font-600 text-lg">'
            f'<span>{q}</span>'
            f'<svg class="faq-chev shrink-0 mt-1 text-bronze" width="18" height="18" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="m6 9 6 6 6-6"/></svg></summary>'
            f'<div class="pt-3 text-ink/80 leading-relaxed">{a}</div></details>'
        )
    out.append("</div></section>")
    return "".join(out)


def ld_faq(faq):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": strip_tags(q),
             "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}}
            for q, a in faq
        ],
    }


def strip_tags(s):
    out, keep = [], True
    for ch in s:
        if ch == "<":
            keep = False
        elif ch == ">":
            keep = True
        elif keep:
            out.append(ch)
    return "".join(out).replace("&nbsp;", " ").replace("&amp;", "&").strip()


def ld_breadcrumb(trail):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + u}
            for i, (n, u) in enumerate(trail)
        ],
    }


def breadcrumb_html(trail):
    parts = []
    for i, (n, u) in enumerate(trail):
        last = i == len(trail) - 1
        parts.append(f'<span class="text-ink/50">{n}</span>' if last
                     else f'<a href="{u}" class="hover:text-bronze">{n}</a>')
    return ('<nav aria-label="Fil d\'Ariane" class="text-[13px] text-ink/60 mb-6 flex flex-wrap gap-2">'
            + '<span aria-hidden="true">›</span>'.join(parts) + "</nav>")


def page(slug, title, desc, hero_kicker, h1, lede, body, faq, trail, extra_ld=None, image="/img/hero.jpg"):
    url = f"{SITE}/{slug}"
    lds = [ld_breadcrumb(trail)]
    if faq:
        lds.append(ld_faq(faq))
    if extra_ld:
        lds.append(extra_ld)
    ld_html = "\n".join(
        '<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False) + "</script>"
        for x in lds
    )
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{url}">
<link rel="icon" href="/img/logo_gold.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="SH Développement">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE}{image}">
{ld_html}
{HEAD_CSS}
</head>
<body class="bg-cream text-ink antialiased">
<a href="#contenu" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 bg-ink text-cream px-4 py-2 rounded z-50">Aller au contenu</a>
{NAV}
<main id="contenu">

<section class="bg-ink text-cream pt-32 pb-16 sm:pt-40 sm:pb-20">
  <div class="max-w-[860px] mx-auto px-5 sm:px-8">
    <p class="text-gold text-xs uppercase tracking-luxe mb-5">{esc(hero_kicker)}</p>
    <h1 class="font-display text-4xl sm:text-5xl leading-tight mb-6">{h1}</h1>
    <p class="text-cream/80 text-lg leading-relaxed max-w-[62ch]">{lede}</p>
    <div class="mt-9 flex flex-wrap gap-3">
      <a href="/proprietaires.html#contact" class="inline-flex items-center gap-2 rounded-full bg-gold text-ink px-6 py-3 font-600 hover:bg-cream">Demander une estimation gratuite</a>
      <a href="tel:{TEL}" class="inline-flex items-center gap-2 rounded-full border border-cream/40 px-6 py-3 font-600 hover:border-gold hover:text-gold">{TEL_H}</a>
    </div>
  </div>
</section>

<article class="max-w-[860px] mx-auto px-5 sm:px-8 py-14 sm:py-20 prose-sh">
{breadcrumb_html(trail)}
{body}
{faq_html(faq) if faq else ""}

<section class="mt-16 rounded-3xl bg-sand/70 p-8 sm:p-10 text-center">
  <h2 class="font-display text-3xl mt-0 mb-3">Parlons de votre bien</h2>
  <p class="text-ink/75 max-w-[52ch] mx-auto">Estimation gratuite et sans engagement : nous étudions votre logement, son emplacement et son potentiel, puis nous vous envoyons une projection chiffrée.</p>
  <div class="mt-7 flex flex-wrap gap-3 justify-center">
    <a href="/proprietaires.html#contact" class="inline-flex items-center gap-2 rounded-full bg-ink text-cream px-6 py-3 font-600 hover:bg-brown">Demander mon estimation</a>
    <a href="/proprietaires.html#estimation" class="inline-flex items-center gap-2 rounded-full border border-ink/25 px-6 py-3 font-600 hover:border-bronze hover:text-bronze">Utiliser le simulateur</a>
  </div>
</section>
</article>

</main>
{FOOTER}
{SCRIPTS}
</body>
</html>
"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  Blocs de contenu réutilisables
# ─────────────────────────────────────────────────────────────────────────────
def revenue_table(block, place):
    if not block["rows"]:
        return ""
    rows = "".join(
        f"<tr><td>{r['type']}</td><td>{r['adr']} €{'' if r['src'] == 'local' else ' *'}</td>"
        f"<td>{r['m55']} €</td><td>{r['m70']} €</td></tr>"
        for r in block["rows"]
    )
    has_fallback = any(r["src"] != "local" for r in block["rows"])
    star = (f' Les lignes marquées d\'un astérisque reprennent la médiane de notre parc '
            f"départemental, faute d'un nombre suffisant de biens de ce type à {place} pour "
            f"publier un chiffre local honnête." if has_fallback else "")
    return f"""<h3>Ce que cela représente concrètement</h3>
<table>
<thead><tr><th>Type de bien</th><th>Prix médian / nuit</th><th>Revenus nets / mois à 55 % d'occupation</th><th>à 70 % d'occupation</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<p class="text-sm text-ink/60">Prix médians réellement pratiqués sur les logements que nous gérons.{star} Les montants indiqués sont ce qui vous revient <em>après</em> commissions de plateforme et frais de conciergerie, hors charges, taxe de séjour et fiscalité. Ce sont des ordres de grandeur : seule une étude de votre bien permet une projection fiable. <a href="/proprietaires.html#estimation">Affinez avec le simulateur</a>.</p>"""


SERVICES = """<h2>Ce que nous prenons en charge</h2>
<p>Notre modèle est simple : vous gardez la propriété et la maîtrise de votre bien, nous absorbons la totalité de l'exploitation. Concrètement, une fois le mandat signé, vous n'avez plus rien à faire.</p>
<ul>
<li><strong>Création et optimisation de l'annonce</strong> : photographies professionnelles, description rédigée, équipements renseignés, diffusion sur Airbnb, Booking.com, Abritel et sur notre propre site de réservation directe (sans commission de plateforme).</li>
<li><strong>Tarification dynamique</strong> : les prix sont recalculés chaque jour selon la saison, le taux de remplissage, les événements locaux et la concurrence. C'est le levier qui fait le plus de différence sur une année complète.</li>
<li><strong>Gestion des réservations et des voyageurs</strong> : réponse aux demandes, sélection des profils, envoi des instructions, assistance pendant le séjour, 7 jours sur 7.</li>
<li><strong>Accueil et remise des clés</strong> : boîte à clés sécurisée, accueil en personne quand c'est pertinent, état des lieux photographique entre chaque séjour.</li>
<li><strong>Ménage et blanchisserie hôtelière</strong> : équipes formées, linge de lit et de toilette fournis et lavé en pressing professionnel, contrôle qualité après chaque intervention.</li>
<li><strong>Maintenance et réapprovisionnement</strong> : petits travaux, remplacement des consommables, coordination des artisans, suivi des incidents avec photos.</li>
<li><strong>Administratif</strong> : collecte et reversement de la taxe de séjour, relevé mensuel détaillé, facturation, accompagnement sur la déclaration en mairie et le numéro d'enregistrement.</li>
</ul>"""


def why_local(place):
    return f"""<h2>Pourquoi une conciergerie implantée localement change tout</h2>
<p>Beaucoup de plateformes nationales proposent de gérer votre bien à {place} depuis un centre d'appels situé à plusieurs centaines de kilomètres. Sur le papier, l'offre se ressemble. Dans les faits, trois choses les séparent d'une équipe présente sur le terrain.</p>
<p><strong>Le délai d'intervention.</strong> Un chauffe-eau qui lâche un samedi soir, une serrure bloquée, un voyageur qui n'arrive pas à entrer : ce qui coûte un avis à une étoile, ce n'est pas l'incident, c'est le temps de réaction. Nos équipes sont basées à Chalon-sur-Saône et interviennent dans la journée sur tout le secteur.</p>
<p><strong>La connaissance du marché réel.</strong> Savoir qu'un week-end donné remplit la ville, qu'un chantier ou un salon crée une demande professionnelle, qu'un quartier se loue mieux qu'un autre à surface égale : cela ne s'apprend pas dans un tableur. C'est ce qui permet de monter les prix au bon moment plutôt que de brader par sécurité.</p>
<p><strong>Le réseau de prestataires.</strong> Femmes de ménage, lingerie, plombier, électricien, serrurier : nous travaillons avec les mêmes équipes depuis des années. Elles connaissent les logements, elles se déplacent vite, et elles nous facturent des tarifs négociés que nous ne majorons pas.</p>"""


TRANSPARENCE = """<h2>Notre engagement de transparence</h2>
<p>Nous appliquons une commission unique sur le montant encaissé, sans frais de dossier, sans abonnement mensuel et sans frais de mise en service. Le ménage est facturé au voyageur, pas à vous. Vous recevez chaque mois un relevé détaillé qui reprend séjour par séjour le montant encaissé, les frais et ce qui vous est reversé.</p>
<p>Le mandat est sans durée d'engagement contraignante : si le partenariat ne vous convient pas, vous récupérez votre bien et vos annonces. Nous préférons garder des propriétaires qui restent parce qu'ils gagnent plus, pas parce qu'ils sont bloqués par un contrat.</p>"""


# ─────────────────────────────────────────────────────────────────────────────
#  Pages villes
# ─────────────────────────────────────────────────────────────────────────────
CITY_PAGES = [
    {
        "slug": "conciergerie-chalon-sur-saone.html",
        "cities": ["Chalon-sur-Saône"],
        "place": "Chalon-sur-Saône",
        "nav_label": "Chalon-sur-Saône",
        "title": "Conciergerie Airbnb à Chalon-sur-Saône (71100) | SH Développement",
        "desc": "Conciergerie Airbnb et location courte durée à Chalon-sur-Saône. Gestion complète, ménage hôtelier, tarification dynamique. Estimation gratuite de vos revenus.",
        "kicker": "Conciergerie · Chalon-sur-Saône",
        "h1": "Conciergerie Airbnb à Chalon-sur-Saône",
        "intro": """<h2>Louer en courte durée à Chalon-sur-Saône</h2>
<p>Chalon-sur-Saône n'est pas une ville touristique au sens classique du terme, et c'est précisément ce qui en fait un marché intéressant pour la location courte durée. La demande y est double, et elle ne s'effondre jamais complètement hors saison.</p>
<p>Il y a d'abord la demande professionnelle, présente toute l'année : déplacements liés au centre hospitalier William Morey, aux entreprises du bassin industriel chalonnais, aux chantiers, aux formations et aux missions d'intérim. Cette clientèle réserve souvent pour plusieurs nuits en semaine, elle est peu sensible au prix et très sensible à la propreté et à la simplicité d'accès. C'est elle qui remplit les studios et les T2 de novembre à mars, quand les locations purement touristiques restent vides.</p>
<p>Il y a ensuite la demande de séjour : la Côte chalonnaise et ses vignobles à un quart d'heure, la Voie Verte, le port de plaisance, le musée Nicéphore-Niépce et le centre médiéval autour de la place Saint-Vincent. Cette demande culmine de mai à septembre, avec un pic très marqué pendant le festival Chalon dans la Rue, où la ville se remplit et où les tarifs peuvent être multipliés sans que la disponibilité suive.</p>
<p>La conséquence pratique est simple : un logement piloté à prix fixe toute l'année perd de l'argent deux fois. Il est trop cher en février, donc il reste vide ; il est trop bon marché en juillet, donc il se remplit instantanément à un tarif qui aurait pu être bien supérieur. L'essentiel du travail consiste à faire coller le prix à la demande, jour par jour.</p>""",
        "quartiers": """<h2>Quels quartiers fonctionnent le mieux</h2>
<p>À surface égale, l'emplacement fait varier fortement le taux d'occupation. Quelques repères issus de notre parc :</p>
<ul>
<li><strong>Centre-ville et quartier Saint-Vincent</strong> : le secteur le plus demandé, pour la clientèle loisir comme professionnelle. Les commerces, les restaurants et les quais à pied compensent largement l'absence de parking privatif, à condition de l'expliquer clairement dans l'annonce.</li>
<li><strong>Île Saint-Laurent et bords de Saône</strong> : très recherché l'été, avec un vrai argument de vue et de calme. Les séjours y sont plus longs et les notes plus élevées.</li>
<li><strong>Abords de la gare</strong> : idéal pour la clientèle d'affaires qui arrive en train, et pour les séjours d'une ou deux nuits. Le rapport rendement / prix d'achat y est souvent le meilleur de la ville.</li>
<li><strong>Saint-Cosme, Bellevue et périphérie</strong> : moins de demande spontanée, mais un stationnement facile qui séduit les familles et les séjours en voiture. La photographie et le prix d'appel y comptent davantage.</li>
<li><strong>Saint-Rémy, Saint-Marcel, Châtenoy et communes limitrophes</strong> : parfaitement louables dès lors que l'annonce est positionnée sur « Chalon-sur-Saône et ses environs » et que le trajet est indiqué en minutes.</li>
</ul>
<p>Aucun de ces secteurs n'est disqualifiant. Ce qui l'est, en revanche, c'est un logement mal photographié, une annonce sans description sérieuse ou un calendrier qui n'est pas tenu à jour.</p>""",
    },
    {
        "slug": "conciergerie-macon.html",
        "cities": ["Mâcon"],
        "place": "Mâcon",
        "nav_label": "Mâcon",
        "title": "Conciergerie Airbnb à Mâcon (71000) | SH Développement",
        "desc": "Conciergerie Airbnb et gestion locative courte durée à Mâcon. Annonces optimisées, ménage hôtelier, prix pilotés au quotidien. Estimation gratuite.",
        "kicker": "Conciergerie · Mâcon",
        "h1": "Conciergerie Airbnb à Mâcon",
        "intro": """<h2>Louer en courte durée à Mâcon</h2>
<p>Mâcon occupe une position que peu de villes de sa taille peuvent revendiquer : une gare TGV à Mâcon-Loché qui met Paris à moins d'une heure quarante, l'autoroute A6 en bord de ville, et une porte d'entrée directe sur trois territoires viticoles majeurs — le Mâconnais, le Beaujolais et, plus au nord, la Bourgogne des grands crus.</p>
<p>Cette situation crée une demande de passage très régulière. Beaucoup de voyageurs ne viennent pas pour Mâcon en tant que telle : ils y font étape sur l'axe Paris-Méditerranée, ou ils en font leur camp de base pour rayonner vers la Roche de Solutré, les caveaux de Pouilly-Fuissé, Cluny ou la Voie Bleue le long de la Saône. Ce sont des séjours de une à trois nuits, réservés souvent à court terme, et pour lesquels la réactivité de la réponse fait toute la différence.</p>
<p>S'y ajoute une clientèle professionnelle et une demande liée aux événements : salons, congrès, épreuves sportives, vendanges. Le marché mâconnais est moins profond que celui de Chalon en volume, mais les prix moyens y sont légèrement supérieurs et la saison utile s'étire plus longtemps, d'avril à octobre.</p>
<p>Le piège classique à Mâcon est de rester bloqué sur un tarif « moyenne saison » toute l'année. Les week-ends de printemps et les périodes de vendanges supportent des prix nettement plus élevés que ce que la plupart des propriétaires osent afficher.</p>""",
        "quartiers": """<h2>Les secteurs qui marchent à Mâcon</h2>
<ul>
<li><strong>Quais de Saône et centre historique</strong> : la valeur sûre. Vue, restaurants, marché, tout est à pied. C'est le secteur où les tarifs et les notes sont les plus élevés.</li>
<li><strong>Proximité gare Mâcon-Ville</strong> : parfait pour la clientèle d'affaires et les étapes d'une nuit. Séjours courts, rotation rapide, occupation très stable en semaine.</li>
<li><strong>Secteur Mâcon-Loché et sud de la ville</strong> : pratique pour les voyageurs en TGV ou en voiture, et à quelques minutes des vignobles de Pouilly-Fuissé. À valoriser sur l'argument œnotourisme.</li>
<li><strong>Nord de Mâcon, Sancé, Saint-Laurent-sur-Saône</strong> : stationnement facile, bon rapport surface / prix, adapté aux familles et aux séjours en voiture.</li>
</ul>""",
    },
    {
        "slug": "conciergerie-tournus.html",
        "cities": ["Tournus"],
        "place": "Tournus",
        "nav_label": "Tournus",
        "title": "Conciergerie Airbnb à Tournus (71700) | SH Développement",
        "desc": "Conciergerie et gestion de location courte durée à Tournus. Clientèle patrimoine et gastronomie, prix pilotés, ménage hôtelier. Estimation gratuite.",
        "kicker": "Conciergerie · Tournus",
        "h1": "Conciergerie Airbnb à Tournus",
        "intro": """<h2>Louer en courte durée à Tournus</h2>
<p>Tournus est un marché de séjour court à forte valeur ajoutée. La ville concentre deux aimants qui font venir des voyageurs de loin : l'abbaye Saint-Philibert, l'un des ensembles romans les mieux conservés d'Europe, et une densité gastronomique rare pour une commune de cette taille, avec plusieurs tables étoilées et reconnues.</p>
<p>Concrètement, cela signifie une clientèle qui réserve pour une ou deux nuits, souvent le week-end, souvent en couple, et qui accepte un tarif supérieur à la moyenne départementale à condition que le logement soit à la hauteur : literie soignée, propreté irréprochable, décoration cohérente, photographies honnêtes. Sur ce marché, un logement moyen se loue mal ; un logement bien tenu se loue cher.</p>
<p>La sortie d'autoroute A6 et la halte fluviale ajoutent une demande de passage, notamment en été. La saison utile va d'avril à octobre, avec un creux hivernal réel qu'il faut assumer : sur Tournus, l'objectif n'est pas de remplir toute l'année, mais de maximiser le prix moyen sur les mois qui comptent.</p>""",
        "quartiers": """<h2>Ce qui fait la différence à Tournus</h2>
<ul>
<li><strong>Le centre ancien, autour de l'abbaye</strong> : le meilleur emplacement, à condition de traiter sérieusement la question du stationnement dans l'annonce.</li>
<li><strong>Bords de Saône et quais</strong> : très demandé en été, argument de vue fort.</li>
<li><strong>Périphérie et communes voisines</strong> : viables pour les maisons avec extérieur, terrasse ou piscine, qui captent les séjours familiaux plus longs.</li>
</ul>
<p>Sur un marché où le voyageur vient pour la qualité, l'investissement dans un reportage photo professionnel et dans le linge se rentabilise en quelques séjours.</p>""",
    },
    {
        "slug": "conciergerie-beaune-chagny.html",
        "cities": ["Chagny", "Bligny-lès-Beaune"],
        "place": "Beaune et Chagny",
        "nav_label": "Beaune et Chagny",
        "title": "Conciergerie Airbnb à Beaune et Chagny | SH Développement",
        "desc": "Conciergerie Airbnb aux portes de Beaune : Chagny, Bligny-lès-Beaune, Côte de Beaune. Gestion complète et tarification adaptée à un marché sous tension.",
        "kicker": "Conciergerie · Côte de Beaune",
        "h1": "Conciergerie Airbnb à Beaune et Chagny",
        "intro": """<h2>Un marché sous tension permanente</h2>
<p>La Côte de Beaune est l'un des marchés de location courte durée les plus tendus de Bourgogne. La demande est internationale, elle vient pour les Hospices de Beaune, la Route des Grands Crus, les domaines et les tables étoilées, et elle dispose d'un budget que l'on ne retrouve nulle part ailleurs dans la région.</p>
<p>Cette tension a une conséquence directe : à Beaune même, le foncier est cher et l'offre est déjà dense. Chagny, Bligny-lès-Beaune et les villages de la couronne offrent un rapport rendement / prix d'acquisition nettement plus favorable, tout en restant à dix ou quinze minutes des Hospices. La clientèle vient en voiture et raisonne en temps de trajet, pas en code postal.</p>
<p>La saisonnalité y est particulière. Au-delà de la saison estivale classique, deux périodes concentrent une demande exceptionnelle : les vendanges, en septembre, et surtout le troisième week-end de novembre, celui de la vente des vins des Hospices, où la disponibilité s'effondre à des dizaines de kilomètres à la ronde. Un propriétaire qui laisse son tarif habituel sur ces dates laisse tout simplement de l'argent sur la table.</p>
<p>Chagny mérite une mention à part : la commune est desservie par sa gare, elle est traversée par la Voie Verte, et elle abrite une table triplement étoilée qui attire à elle seule une clientèle de séjour.</p>""",
        "quartiers": """<h2>Notre approche sur ce secteur</h2>
<ul>
<li><strong>Calendrier événementiel piloté à l'année</strong> : vente des vins, vendanges, week-ends prolongés et manifestations locales sont positionnés en tarif haut plusieurs mois à l'avance, avant que la concurrence ne se réveille.</li>
<li><strong>Annonces multilingues</strong> : la clientèle est majoritairement étrangère. Nos annonces et nos échanges sont traduits, et l'accueil se fait en plusieurs langues.</li>
<li><strong>Standing et équipement</strong> : sur ce marché, un logement correctement équipé se loue sensiblement plus cher qu'un logement simplement propre. Nous vous indiquons précisément les investissements qui se rentabilisent, et ceux qui ne se rentabilisent pas.</li>
<li><strong>Durée minimale ajustée</strong> : imposer deux ou trois nuits sur les périodes fortes augmente le revenu net et réduit le nombre de ménages.</li>
</ul>""",
    },
    {
        "slug": "conciergerie-givry-cote-chalonnaise.html",
        "cities": ["Givry", "Dracy-le-Fort", "Buxy", "Saint-Désert",
                   "Saint-Léger-sur-Dheune", "Fontaines"],
        "place": "la Côte chalonnaise",
        "nav_label": "Givry et Côte chalonnaise",
        "title": "Conciergerie Airbnb à Givry et en Côte chalonnaise | SH Développement",
        "desc": "Conciergerie Airbnb en Côte chalonnaise : Givry, Mercurey, Rully, Buxy, Dracy-le-Fort. Œnotourisme, cyclotourisme, gestion complète. Estimation gratuite.",
        "kicker": "Conciergerie · Côte chalonnaise",
        "h1": "Conciergerie Airbnb en Côte chalonnaise",
        "intro": """<h2>L'œnotourisme, un marché qui se construit</h2>
<p>La Côte chalonnaise — Givry, Mercurey, Rully, Bouzeron, Buxy, Montagny — a longtemps été le vignoble discret de la Bourgogne. Elle ne l'est plus. À mesure que les prix de la Côte de Nuits et de la Côte de Beaune deviennent inaccessibles, une clientèle œnotouristique exigeante mais moins fortunée descend vers le sud et découvre des appellations d'un excellent rapport qualité-prix, à quinze minutes de Chalon-sur-Saône.</p>
<p>Cette clientèle a un profil précis et très favorable au propriétaire : elle réserve des séjours plus longs que la moyenne, souvent trois à cinq nuits, elle voyage en couple ou entre amis, elle vient en voiture, et elle privilégie systématiquement la maison de village avec extérieur au studio urbain.</p>
<p>Un second flux s'y superpose : le cyclotourisme. La Voie Verte qui relie Givry à Cluny, l'une des toutes premières de France, draine chaque année des milliers de cyclistes en itinérance. Un logement qui propose un local à vélos sécurisé, un point de lavage et un séchage se distingue immédiatement de ses concurrents et peut afficher un tarif supérieur.</p>
<p>La saison utile s'étend d'avril à octobre, avec un pic aux vendanges. L'hiver est réel, mais il peut être partiellement comblé par la clientèle professionnelle de Chalon, qui est à portée immédiate.</p>""",
        "quartiers": """<h2>Ce que nous mettons en avant sur ce secteur</h2>
<ul>
<li><strong>Le positionnement œnotouristique</strong> : nos annonces citent nommément les appellations, les domaines ouverts à la visite et les distances réelles. C'est ce qui déclenche la réservation, bien plus que la surface en mètres carrés.</li>
<li><strong>Les extérieurs</strong> : terrasse, jardin, vue sur les vignes. Ces éléments sont photographiés et mis en avant, car ils portent l'essentiel de la valeur perçue.</li>
<li><strong>Les équipements cyclistes</strong> : nous vous conseillons sur les aménagements à faible coût qui font basculer une réservation.</li>
<li><strong>Les durées minimales</strong> : sur ce marché, imposer deux ou trois nuits améliore nettement le revenu net et allège la logistique.</li>
<li><strong>Le partenariat avec les acteurs locaux</strong> : caveaux, restaurants, loueurs de vélos, recommandés aux voyageurs dans notre guide d'accueil.</li>
</ul>""",
    },
    {
        "slug": "conciergerie-grand-chalon.html",
        "cities": ["Saint-Rémy", "Saint-Marcel", "Champforgeuil", "Fragnes-La Loyère",
                   "Lux", "Saint-Loup-de-Varennes", "Beaumont-sur-Grosne",
                   "La Charmée", "Saint-Germain-du-Plain", "Le Creusot"],
        "place": "le Grand Chalon",
        "nav_label": "Grand Chalon",
        "title": "Conciergerie Airbnb dans le Grand Chalon et le Chalonnais | SH Développement",
        "desc": "Conciergerie Airbnb dans les communes du Grand Chalon : Saint-Rémy, Saint-Marcel, Châtenoy, Champforgeuil, Lux et alentours. Gestion complète, estimation gratuite.",
        "kicker": "Conciergerie · Grand Chalon",
        "h1": "Conciergerie Airbnb dans le Grand Chalon",
        "intro": """<h2>Louer hors du centre-ville : une idée reçue à corriger</h2>
<p>Beaucoup de propriétaires des communes qui entourent Chalon-sur-Saône partent du principe que leur logement « n'est pas assez central » pour la location courte durée. C'est faux dans la grande majorité des cas, et cette croyance leur coûte plusieurs milliers d'euros par an.</p>
<p>La raison est simple : la clientèle du Chalonnais vient très majoritairement en voiture. Pour un voyageur qui a roulé trois heures depuis Paris ou Lyon, huit minutes de plus jusqu'à Saint-Rémy, Champforgeuil ou Saint-Marcel ne changent rien à sa décision. En revanche, ce qui change tout, c'est ce que ces communes offrent et que le centre-ville n'offre pas : un stationnement gratuit devant la porte, un jardin, une terrasse, du calme et davantage de surface pour le même budget.</p>
<p>Ces atouts correspondent exactement à ce que recherchent trois segments très rentables : les familles, les groupes d'amis, et la clientèle professionnelle en mission longue qui préfère un logement spacieux à une chambre d'hôtel. Ces trois segments réservent des séjours plus longs, génèrent moins de ménages par mois et laissent de meilleures notes.</p>
<p>La condition, c'est le positionnement de l'annonce. Un logement à Saint-Rémy annoncé comme « appartement à Saint-Rémy » sera invisible. Le même bien annoncé sur « Chalon-sur-Saône, à 6 minutes du centre, parking privé et jardin » capte l'intégralité du trafic de recherche sur Chalon. C'est un travail de rédaction et de paramétrage, pas de chance.</p>""",
        "quartiers": """<h2>Les communes où nous intervenons</h2>
<p>Nous gérons des logements dans l'ensemble du Chalonnais et au-delà, notamment à Saint-Rémy, Saint-Marcel, Champforgeuil, Fragnes-La Loyère, Lux, Saint-Loup-de-Varennes, La Charmée, Beaumont-sur-Grosne, Saint-Germain-du-Plain, Dracy-le-Fort, Givry, Chagny et Le Creusot.</p>
<p>Si votre commune ne figure pas dans cette liste, cela ne veut pas dire que nous ne pouvons pas intervenir : notre zone d'intervention couvre l'ensemble du département de Saône-et-Loire et déborde sur la Côte-d'Or. Le seul critère réel est la capacité de nos équipes de ménage à assurer une rotation le jour même entre deux séjours. Dites-nous où se trouve votre bien, nous vous répondrons franchement.</p>""",
    },
]


def city_faq(place, block):
    med = f"{block['median']} €" if block["median"] else "variable"
    n = block["n"]
    parc = (f"Nous gérons actuellement {n} logement{'s' if n > 1 else ''} sur ce secteur"
            if n else "Nous intervenons sur ce secteur")
    return [
        (f"Combien coûte une conciergerie à {place} ?",
         "Nous appliquons une commission unique sur le montant des séjours encaissés, "
         "sans frais de dossier, sans abonnement et sans frais de mise en service. "
         "Le ménage est facturé au voyageur et non au propriétaire. Le taux exact dépend "
         "du niveau de service retenu et du volume : il vous est communiqué chiffré, "
         "par écrit, lors de l'estimation gratuite."),
        (f"Combien mon logement peut-il rapporter à {place} ?",
         f"Sur notre parc, le prix médian constaté sur ce secteur s'établit autour de {med} la nuit, "
         "mais le revenu réel dépend surtout du taux d'occupation, donc de la qualité de l'annonce "
         "et du pilotage des prix. Le plus simple est d'utiliser notre "
         '<a href="/proprietaires.html#estimation">simulateur de revenus</a> puis de nous '
         "demander une estimation personnalisée : elle est gratuite et sans engagement."),
        ("Dois-je déclarer mon logement en mairie ?",
         "Oui. Toute location d'un meublé de tourisme doit faire l'objet d'une déclaration en mairie, "
         "qui donne lieu à un numéro d'enregistrement à afficher sur les annonces. Depuis la loi "
         "du 19 novembre 2024, dite loi Le Meur, cette obligation se généralise à l'ensemble des communes "
         "et les plateformes doivent contrôler ce numéro. Nous vous accompagnons dans cette démarche. "
         'Nous détaillons le sujet dans notre <a href="/conseils/loi-le-meur-meuble-tourisme.html">'
         "guide sur la loi Le Meur</a>."),
        ("Puis-je continuer à utiliser mon logement personnellement ?",
         "Oui, sans aucune difficulté. Vous bloquez les dates qui vous conviennent dans le calendrier, "
         "à l'avance ou au fil de l'eau, et le logement vous est rendu prêt. C'est l'un des intérêts "
         "de la courte durée par rapport à un bail classique."),
        ("Que se passe-t-il en cas de dégradation ?",
         "Chaque séjour fait l'objet d'un état des lieux photographique à l'entrée et à la sortie. "
         "En cas de dommage, nous constituons le dossier et engageons la procédure auprès de la plateforme "
         "ou de l'assurance, dépôt de garantie à l'appui, sans que vous ayez à intervenir. Nous vous "
         "tenons informé à chaque étape."),
        (f"{parc} : puis-je voir ce que vous gérez ?",
         "Oui, l'intégralité de nos logements est visible publiquement sur notre "
         '<a href="/catalogue.html">catalogue en ligne</a>, avec les photographies, les descriptifs '
         "et les notes réellement laissées par les voyageurs. C'est le meilleur moyen de juger de "
         "notre travail avant de nous confier votre bien."),
    ]


def build_city_page(cfg, by_city, global_med, nav_links):
    block = city_block(cfg["cities"], by_city, global_med)
    place = cfg["place"]
    n = block["n"]

    parc_para = ""
    if n:
        note = (f" Leur note moyenne voyageurs s'établit à {str(block['rating']).replace('.', ',')}/10"
                if block["rating"] and block["nrated"] >= 2 else "")
        parc_para = (
            f'<h2>Notre parc sur {place}</h2>'
            f"<p>Nous gérons actuellement <strong>{n} logement{'s' if n > 1 else ''}</strong> "
            f"sur ce secteur.{note}, sur la base des avis publiés par les voyageurs eux-mêmes. "
            f'Vous pouvez les consulter un par un dans notre <a href="/catalogue.html?q='
            f'{cfg["cities"][0].replace(" ", "+")}">catalogue public</a> : photographies, '
            f"descriptifs, équipements et commentaires réels. Nous n'avons rien à cacher sur "
            f"la façon dont nous présentons et tenons les biens qui nous sont confiés.</p>"
        )

    others = "".join(
        f'<li><a href="/{c["slug"]}">Conciergerie à {c["nav_label"]}</a></li>'
        for c in CITY_PAGES if c["slug"] != cfg["slug"]
    )

    body = "\n".join([
        cfg["intro"],
        cfg["quartiers"],
        "<h2>Ce que vous pouvez espérer en revenus</h2>",
        "<p>Il n'existe pas de réponse unique : deux logements identiques peuvent avoir "
        "des résultats très différents selon leur emplacement, leur équipement et surtout "
        "la façon dont ils sont pilotés. Les ordres de grandeur ci-dessous sont calculés "
        "à partir des prix réellement pratiqués sur notre parc, et actualisés automatiquement.</p>",
        revenue_table(block, place),
        parc_para,
        SERVICES,
        why_local(place),
        TRANSPARENCE,
        f'<h2>Nos autres secteurs</h2><ul>{others}</ul>'
        f'<p>Vous cherchez plutôt à comprendre le fonctionnement général de notre offre ? '
        f'Tout est détaillé sur la page <a href="/proprietaires.html">Propriétaires</a>, '
        f'et nos <a href="/conseils-proprietaires.html">conseils aux propriétaires</a> '
        f'abordent la fiscalité, le classement et la réglementation.</p>',
    ])

    ld_local = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "@id": f"{SITE}/#organisation",
        "name": "SH Développement",
        "url": f"{SITE}/{cfg['slug']}",
        "telephone": TEL,
        "email": MAIL,
        "image": f"{SITE}/img/hero.jpg",
        "priceRange": "€€",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "1 rue Georges Duny",
            "postalCode": "71100",
            "addressLocality": "Chalon-sur-Saône",
            "addressRegion": "Bourgogne-Franche-Comté",
            "addressCountry": "FR",
        },
        "areaServed": [{"@type": "City", "name": c} for c in cfg["cities"]],
        "description": cfg["desc"],
    }

    trail = [("Accueil", "/"), ("Propriétaires", "/proprietaires.html"),
             (f"Conciergerie à {cfg['nav_label']}", "/" + cfg["slug"])]

    lede = (f"Nous gérons {n} logement{'s' if n > 1 else ''} sur ce secteur, de la mise en ligne "
            f"de l'annonce au ménage entre deux séjours. Vous gardez votre bien, nous nous occupons "
            f"du reste." if n else
            "De la mise en ligne de l'annonce au ménage entre deux séjours : vous gardez votre bien, "
            "nous nous occupons du reste.")

    return page(cfg["slug"], cfg["title"], cfg["desc"], cfg["kicker"], cfg["h1"],
                lede, body, city_faq(place, block), trail, ld_local)


# ─────────────────────────────────────────────────────────────────────────────
#  Articles
# ─────────────────────────────────────────────────────────────────────────────
def articles(stats):
    """Retourne la liste des articles (slug, title, desc, kicker, h1, lede, body, faq)."""
    _, by_city, global_med = stats
    chalon = city_block(["Chalon-sur-Saône"], by_city, global_med)

    arts = []

    # ── 1. Loi Le Meur ────────────────────────────────────────────────────────
    arts.append({
        "slug": "loi-le-meur-meuble-tourisme.html",
        "title": "Loi Le Meur : ce qui change pour les meublés de tourisme | SH Développement",
        "desc": "Numéro d'enregistrement, DPE, abattement micro-BIC : ce que la loi Le Meur du 19 novembre 2024 impose aux propriétaires de meublés de tourisme.",
        "kicker": "Conseils propriétaires · Réglementation",
        "h1": "Loi Le Meur : ce qui change pour les meublés de tourisme",
        "lede": "Enregistrement obligatoire, performance énergétique, fiscalité revue à la baisse pour les meublés non classés : le point sur un texte qui redessine les règles de la location courte durée.",
        "date": "2026-08-15",
        "body": """<p>La loi n° 2024-1039 du 19 novembre 2024, dite « loi Le Meur », est le texte qui structure aujourd'hui la location de meublés de tourisme en France. Elle poursuit trois objectifs : donner aux communes des outils de régulation, aligner les meublés touristiques sur les exigences énergétiques du logement classique, et réduire l'avantage fiscal dont ils bénéficiaient face à la location nue. Voici ce qu'un propriétaire doit en retenir concrètement.</p>

<h2>1. Le numéro d'enregistrement devient la règle partout</h2>
<p>Jusqu'ici, la déclaration en mairie avec attribution d'un numéro d'enregistrement ne s'imposait que dans certaines communes, principalement les grandes villes et les zones tendues. La loi Le Meur généralise le principe : la déclaration devient la norme sur l'ensemble du territoire, et le numéro obtenu doit figurer sur chaque annonce, quelle que soit la plateforme.</p>
<p>Le numéro national d'enregistrement comporte treize caractères. Les plateformes ont l'obligation de le collecter, de le vérifier et de retirer les annonces qui n'en disposent pas. Autrement dit, le risque n'est pas seulement l'amende : c'est la désactivation pure et simple de l'annonce, avec les réservations en cours.</p>
<p>Les sanctions prévues sont substantielles — jusqu'à 20 000 € en cas de défaut d'enregistrement. Le calendrier de mise en œuvre a été décalé à plusieurs reprises et le déploiement complet du téléservice national s'étale sur 2026 : il est donc essentiel de vérifier auprès de sa propre mairie l'état d'avancement du dispositif, plutôt que de se fier à une date générale.</p>
<p><strong>Ce que cela implique en pratique :</strong> si votre logement n'est pas encore déclaré, faites-le maintenant. La démarche est gratuite, elle se fait auprès de la mairie de la commune où se situe le bien, et elle prend quelques minutes. Ne pas l'avoir faite ne fait gagner strictement rien.</p>

<h2>2. Le DPE entre dans le jeu</h2>
<p>C'est le changement le plus lourd de conséquences à moyen terme. Les meublés de tourisme, jusque-là épargnés par le calendrier de rénovation énergétique applicable aux locations classiques, y sont désormais soumis.</p>
<p>Le principe retenu est un seuil minimal de classe E pour pouvoir être proposé à la location touristique, avec un durcissement progressif : à compter du 1er janvier 2034, seuls les logements classés entre A et D pourront être loués en meublé de tourisme. Les communes disposent par ailleurs de la faculté d'exiger un DPE lors de la déclaration, ce qui rend le diagnostic difficilement contournable.</p>
<p>Le non-respect expose à une amende administrative pouvant atteindre 5 000 € par logement.</p>
<p><strong>Ce que cela implique en pratique :</strong> si vous détenez un logement classé F ou G, l'horizon 2034 paraît lointain mais ne l'est pas à l'échelle de travaux de rénovation. Faites réaliser le diagnostic maintenant, ne serait-ce que pour connaître votre situation exacte et étaler la dépense. Un logement énergivore se loue aussi moins bien : le chauffage électrique d'un studio mal isolé pèse directement sur votre marge en hiver.</p>

<h2>3. L'abattement fiscal du micro-BIC fortement réduit</h2>
<p>C'est la mesure qui frappe le plus grand nombre de propriétaires. Le régime micro-BIC, choisi par défaut par la majorité des loueurs en meublé non professionnels, a été révisé dans un sens nettement défavorable aux meublés non classés.</p>
<table>
<thead><tr><th>Situation du logement</th><th>Abattement forfaitaire</th><th>Plafond de recettes</th></tr></thead>
<tbody>
<tr><td>Meublé de tourisme <strong>classé</strong></td><td>50 %</td><td>77 700 €</td></tr>
<tr><td>Meublé de tourisme <strong>non classé</strong></td><td>30 %</td><td>15 000 €</td></tr>
</tbody>
</table>
<p>L'écart est considérable. Sur 30 000 € de recettes annuelles, un meublé classé au micro-BIC est imposé sur 15 000 € ; un meublé non classé dépasse le plafond de 15 000 € et bascule au régime réel, avec l'obligation comptable qui l'accompagne.</p>
<p><strong>Ce que cela implique en pratique :</strong> deux réflexes. D'abord, envisager sérieusement le <a href="/conseils/classement-meuble-tourisme-etoiles.html">classement en meublé de tourisme</a>, dont le coût est sans commune mesure avec l'économie fiscale. Ensuite, faire chiffrer par un comptable la comparaison micro-BIC / régime réel : pour beaucoup de propriétaires, le réel est devenu plus avantageux, notamment grâce à l'amortissement du bien.</p>

<h2>4. Des pouvoirs élargis pour les communes</h2>
<p>La loi renforce la capacité des communes à réguler l'activité sur leur territoire : possibilité d'abaisser le plafond de location de la résidence principale de 120 à 90 jours par an, instauration de quotas d'autorisations, création de zones réservées à la résidence principale dans les documents d'urbanisme, extension du régime d'autorisation de changement d'usage.</p>
<p>Toutes les communes n'activent pas ces leviers, loin de là. En Saône-et-Loire, le marché reste très largement ouvert et rien ne s'apparente à la situation de Paris, Annecy ou du littoral. Mais la règle applicable est désormais locale, et elle peut évoluer d'une année sur l'autre : c'est auprès de votre mairie qu'il faut la vérifier, pas dans un article général.</p>

<h2>Ce que nous faisons pour nos propriétaires</h2>
<p>La conformité fait partie de notre travail. Concrètement, nous vérifions que chaque logement confié dispose d'un numéro d'enregistrement valide et affiché sur toutes les plateformes, nous vous accompagnons dans la déclaration en mairie si elle n'a pas été faite, nous collectons et reversons la taxe de séjour, et nous vous alertons lorsqu'une évolution réglementaire concerne votre commune.</p>
<p>Nous vous orientons également vers le classement lorsque le calcul fiscal le justifie, ce qui est le cas de la grande majorité des logements dépassant 15 000 € de recettes annuelles.</p>

<p class="text-sm text-ink/60 mt-10">Cet article présente l'état du droit à la date de sa publication, à titre d'information générale. Il ne constitue pas un conseil juridique ou fiscal personnalisé : la situation de chaque propriétaire doit être validée avec un professionnel du chiffre et auprès de la mairie concernée.</p>""",
        "faq": [
            ("Mon logement est en Saône-et-Loire, suis-je vraiment concerné ?",
             "Oui pour l'enregistrement, le DPE et la fiscalité, qui sont des règles nationales. "
             "Les mesures de restriction (quotas, changement d'usage, plafond de 90 jours) relèvent "
             "en revanche d'une décision de chaque commune : à ce jour, le Chalonnais et le Mâconnais "
             "restent des marchés ouverts."),
            ("Que risque une annonce sans numéro d'enregistrement ?",
             "Deux choses distinctes : une amende administrative pouvant atteindre 20 000 €, et surtout "
             "le retrait de l'annonce par la plateforme, qui a désormais l'obligation de vérifier ce numéro. "
             "Le second risque est le plus immédiat."),
            ("Le classement en meublé de tourisme est-il obligatoire ?",
             "Non, il reste facultatif. Mais depuis la révision du micro-BIC, il devient très largement "
             "rentable dès que vos recettes dépassent quelques milliers d'euros par an, puisqu'il fait "
             "passer l'abattement de 30 % à 50 % et le plafond de 15 000 € à 77 700 €."),
            ("Mon logement est classé F, dois-je vendre ?",
             "Non. Le seuil bloquant à horizon 2034 est la classe D ; d'ici là, un logement classé E "
             "reste louable. L'urgence est de faire établir le diagnostic pour connaître votre situation "
             "réelle et planifier d'éventuels travaux, pas de céder dans la précipitation."),
        ],
    })

    # ── 2. Classement meublé de tourisme ──────────────────────────────────────
    arts.append({
        "slug": "classement-meuble-tourisme-etoiles.html",
        "title": "Classement meublé de tourisme : pourquoi obtenir des étoiles | SH Développement",
        "desc": "Abattement fiscal de 50 %, taxe de séjour maîtrisée, visibilité accrue : pourquoi et comment faire classer son meublé de tourisme en Saône-et-Loire.",
        "kicker": "Conseils propriétaires · Fiscalité",
        "h1": "Classement en meublé de tourisme : pourquoi il est devenu incontournable",
        "lede": "Longtemps considéré comme une formalité facultative, le classement en meublé de tourisme est devenu, depuis la réforme du micro-BIC, l'une des décisions les plus rentables qu'un propriétaire puisse prendre.",
        "date": "2026-08-15",
        "body": """<p>Le classement en meublé de tourisme est une procédure volontaire qui attribue à un logement de une à cinq étoiles, sur la base d'une grille de contrôle nationale. Pendant des années, la plupart des propriétaires l'ont ignorée : la démarche paraissait bureaucratique et le gain flou. Ce raisonnement n'est plus valable.</p>

<h2>Le vrai argument : la fiscalité</h2>
<p>Depuis la loi Le Meur, le régime micro-BIC distingue durement les meublés classés des autres. Un meublé <strong>classé</strong> bénéficie d'un abattement forfaitaire de 50 % avec un plafond de recettes de 77 700 €. Un meublé <strong>non classé</strong> tombe à 30 % d'abattement, avec un plafond de 15 000 €.</p>
<p>Prenons un cas courant : un T2 qui génère 18 000 € de recettes annuelles.</p>
<table>
<thead><tr><th></th><th>Meublé classé</th><th>Meublé non classé</th></tr></thead>
<tbody>
<tr><td>Recettes</td><td>18 000 €</td><td>18 000 €</td></tr>
<tr><td>Abattement</td><td>50 % (9 000 €)</td><td>Plafond de 15 000 € dépassé</td></tr>
<tr><td>Base imposable</td><td>9 000 €</td><td>Bascule au régime réel</td></tr>
</tbody>
</table>
<p>Le meublé classé reste au micro-BIC, simple et sans comptabilité. Le meublé non classé, lui, dépasse le plafond et doit passer au régime réel : bilan, liasse fiscale, honoraires de comptable. Le régime réel n'est pas une mauvaise chose en soi — il permet d'amortir le bien et se révèle souvent plus favorable — mais il doit être un choix, pas une contrainte subie.</p>
<p>Rapporté au coût de la visite de classement, généralement de l'ordre de 150 à 300 € pour cinq ans, l'arbitrage se passe de commentaire.</p>

<h2>Les autres bénéfices, moins connus</h2>
<ul>
<li><strong>La taxe de séjour devient prévisible.</strong> Pour un meublé classé, elle est forfaitaire par nuitée et par personne selon la catégorie. Pour un non classé, elle est proportionnelle au prix de la nuitée, donc plus élevée sur les séjours haut de gamme et plus difficile à anticiper.</li>
<li><strong>La visibilité.</strong> Le classement ouvre l'accès à certains canaux de distribution institutionnels et permet d'être référencé par les offices de tourisme et les comités départementaux, qui orientent une clientèle de qualité.</li>
<li><strong>Le signal de confiance.</strong> Les étoiles rassurent une clientèle qui compare, en particulier la clientèle étrangère et les séjours longs.</li>
<li><strong>Les chèques-vacances.</strong> L'acceptation des titres ANCV, qui représentent un volume réel sur certains segments familiaux, est facilitée pour les hébergements classés.</li>
</ul>

<h2>Comment se déroule la procédure</h2>
<p>La démarche est plus simple que sa réputation. Elle se déroule en quatre temps.</p>
<h3>1. Choisir un organisme accrédité</h3>
<p>La visite doit être réalisée par un organisme accrédité par le COFRAC ou titulaire de l'agrément prévu par le code du tourisme. Plusieurs opérateurs interviennent en Saône-et-Loire, avec des tarifs et des délais variables. Il est utile de demander deux ou trois devis.</p>
<h3>2. Préparer le logement</h3>
<p>C'est l'étape que les propriétaires sous-estiment. La grille de classement compte plus de cent points de contrôle, répartis en critères obligatoires et en critères « à la carte » qui permettent de compenser certaines absences. Beaucoup de points se gagnent pour quelques dizaines d'euros : une notice d'utilisation des équipements, un extincteur, un détecteur de fumée conforme, un éclairage suffisant, un nombre de prises adéquat, du linge de lit en quantité, une poubelle de tri.</p>
<h3>3. La visite</h3>
<p>Elle dure généralement une à deux heures. L'inspecteur parcourt la grille point par point et relève les manquements. Un logement bien préparé obtient son classement du premier coup.</p>
<h3>4. La décision</h3>
<p>Le classement est prononcé pour cinq ans. Il est ensuite déclaré en mairie, et le numéro doit être conservé pour la déclaration fiscale.</p>

<h2>Quelle catégorie viser ?</h2>
<p>Contrairement à une idée répandue, viser le maximum d'étoiles n'est pas toujours le bon calcul. L'avantage fiscal est identique de une à cinq étoiles : c'est le fait d'être classé qui compte, pas le nombre d'étoiles. Les étoiles supplémentaires jouent sur l'image et sur le barème de taxe de séjour, mais elles imposent des critères de surface et d'équipement qui peuvent exiger des investissements disproportionnés.</p>
<p>Pour un studio ou un T2 urbain à Chalon-sur-Saône ou à Mâcon, viser deux ou trois étoiles est presque toujours le meilleur rapport effort / bénéfice. Pour une maison de caractère en Côte chalonnaise ou aux portes de Beaune, monter à quatre étoiles peut se justifier commercialement.</p>

<h2>Notre rôle</h2>
<p>Nous accompagnons les propriétaires qui nous confient leur bien sur l'ensemble de la démarche : audit préalable du logement au regard de la grille, liste chiffrée des points à corriger par ordre de priorité, mise en relation avec un organisme de contrôle, et préparation du logement avant la visite. Dans la plupart des cas, la mise à niveau représente quelques centaines d'euros, amortis dès la première année.</p>

<p class="text-sm text-ink/60 mt-10">Les montants et taux cités le sont à titre indicatif et à la date de publication. Faites valider votre situation par votre expert-comptable : l'arbitrage micro-BIC / régime réel dépend de votre tranche d'imposition, de vos charges et de votre patrimoine.</p>""",
        "faq": [
            ("Le classement est-il obligatoire ?",
             "Non, il reste entièrement facultatif. Mais il conditionne l'abattement de 50 % au micro-BIC "
             "et le plafond de 77 700 €, ce qui le rend financièrement très difficile à ignorer."),
            ("Combien coûte le classement ?",
             "La visite de contrôle par un organisme accrédité se situe généralement entre 150 et 300 €, "
             "pour un classement valable cinq ans. À cela peut s'ajouter la mise à niveau du logement, "
             "de quelques dizaines à quelques centaines d'euros selon l'état de départ."),
            ("Combien de temps le classement reste-t-il valable ?",
             "Cinq ans. Passé ce délai, une nouvelle visite est nécessaire pour le renouveler."),
            ("Puis-je faire classer un logement que je loue déjà ?",
             "Oui, à tout moment. Le classement n'exige pas d'interrompre l'activité ; il suffit de "
             "programmer la visite sur une journée où le logement est libre."),
            ("Faut-il viser cinq étoiles ?",
             "Rarement. L'avantage fiscal est le même quel que soit le nombre d'étoiles. Les catégories "
             "élevées imposent des critères de surface et d'équipement coûteux qui ne se rentabilisent "
             "que sur des biens de standing."),
        ],
    })

    # ── 3. Rentabilité Chalon ─────────────────────────────────────────────────
    med = chalon["median"]
    t2 = next((r for r in chalon["rows"] if r["type"] == "T2"), None)
    studio = next((r for r in chalon["rows"] if r["type"] == "Studio"), None)
    tbl = revenue_table(chalon, "Chalon-sur-Saône")
    arts.append({
        "slug": "rentabilite-location-courte-duree-chalon.html",
        "title": "Combien rapporte un Airbnb à Chalon-sur-Saône ? | SH Développement",
        "desc": "Prix par nuit, taux d'occupation, charges réelles : les chiffres d'un meublé touristique à Chalon-sur-Saône, à partir de notre parc en gestion.",
        "kicker": "Conseils propriétaires · Rentabilité",
        "h1": "Combien rapporte réellement un Airbnb à Chalon-sur-Saône ?",
        "lede": "La question que tout propriétaire se pose, et à laquelle presque personne ne répond avec des chiffres vérifiables. Voici les nôtres, issus des logements que nous gérons réellement.",
        "date": "2026-08-15",
        "body": f"""<p>La plupart des articles qui traitent de la rentabilité d'un meublé touristique reposent sur des moyennes nationales ou sur des simulations. Nous préférons partir de ce que nous observons directement sur notre parc chalonnais, actualisé automatiquement à chaque mise à jour de ce site.</p>

<h2>Le prix par nuit : le chiffre qui trompe le plus</h2>
<p>Sur les logements que nous gérons à Chalon-sur-Saône, le prix médian s'établit autour de <strong>{med} € la nuit</strong>. C'est un chiffre utile, mais c'est aussi le plus mal interprété de tous, pour deux raisons.</p>
<p>D'abord parce qu'il s'agit d'une médiane sur des biens très différents, du studio étudiant à la maison familiale. Ensuite et surtout parce que <strong>le prix par nuit ne dit rien du revenu</strong>. Un logement affiché à 80 € qui se loue dix nuits par mois rapporte moins qu'un logement à 55 € qui s'en loue vingt-deux. C'est le produit des deux qui compte, et c'est précisément ce que la plupart des propriétaires en autogestion optimisent mal.</p>

{tbl}

<h2>Le taux d'occupation : là où tout se joue</h2>
<p>À Chalon, l'écart entre un logement bien piloté et un logement laissé à lui-même se situe entre quinze et trente points d'occupation. Trois facteurs expliquent l'essentiel de cet écart.</p>
<h3>La saisonnalité doit être exploitée, pas subie</h3>
<p>Le marché chalonnais connaît une saison haute très marquée de juin à septembre, avec un pic pendant le festival Chalon dans la Rue, et un creux de novembre à février. Un tarif fixe toute l'année produit mécaniquement le pire des deux mondes : des nuits invendues l'hiver et des nuits bradées l'été. Nos prix sont recalculés chaque jour en fonction du remplissage, de la concurrence disponible et du calendrier local.</p>
<h3>La clientèle professionnelle sauve l'hiver</h3>
<p>C'est la spécificité chalonnaise. Les déplacements liés au centre hospitalier, aux entreprises du bassin et aux chantiers génèrent une demande de semaine, toute l'année, qui n'existe pas dans une ville purement touristique. Encore faut-il aller la chercher : facturation possible, arrivée autonome tardive, espace de travail, connexion fiable, et surtout une durée minimale de séjour qui n'exclut pas les nuitées isolées en semaine.</p>
<h3>La réactivité</h3>
<p>Sur les plateformes, le délai de réponse et le taux d'acceptation pèsent directement sur le classement de l'annonce dans les résultats de recherche. Un propriétaire qui répond en six heures est structurellement désavantagé face à une équipe qui répond en quelques minutes, sept jours sur sept.</p>

<h2>Les charges qu'on oublie systématiquement</h2>
<p>Le revenu brut affiché par les plateformes n'est pas ce qui arrive sur votre compte. Voici ce qu'il faut déduire, dans l'ordre :</p>
<ul>
<li><strong>La commission des plateformes</strong>, généralement de 3 % à 15 % selon le canal et le mode de facturation retenu.</li>
<li><strong>Le ménage entre chaque séjour</strong>, qui est en pratique refacturé au voyageur mais qui pèse sur le prix total affiché, donc sur la conversion.</li>
<li><strong>La blanchisserie</strong>, souvent sous-estimée : le linge hôtelier lavé en pressing coûte plus cher qu'une machine à domicile, mais il évite les mauvaises notes qui coûtent bien davantage.</li>
<li><strong>Les consommables et le réapprovisionnement</strong> : produits d'accueil, papier, produits d'entretien, ampoules, petits remplacements.</li>
<li><strong>Les charges fixes</strong> : énergie, eau, internet, assurance propriétaire non occupant, copropriété, taxe foncière, cotisation foncière des entreprises.</li>
<li><strong>La maintenance</strong> : compter une provision annuelle réaliste. Un logement loué en courte durée s'use plus vite qu'une location nue.</li>
<li><strong>La fiscalité</strong>, qui dépend de votre régime et de votre classement.</li>
</ul>
<p>C'est pour cette raison que nous raisonnons toujours en <strong>revenu net reversé au propriétaire</strong>, jamais en chiffre d'affaires brut. Un discours commercial qui vous annonce un montant sans préciser ce qu'il comprend n'a aucune valeur.</p>

<h2>Courte durée ou location classique : le bon comparatif</h2>
<p>À Chalon-sur-Saône, un T2 correct se loue en bail classique dans une fourchette de 450 à 600 € par mois, charges non comprises. La courte durée bien pilotée dépasse généralement ce montant, souvent nettement, mais elle n'est pas comparable terme à terme.</p>
<p>Ce que la courte durée apporte réellement : un revenu supérieur, la disponibilité du bien pour un usage personnel, l'absence de risque d'impayé, un logement inspecté toutes les semaines donc entretenu, et une sortie facile en cas de vente.</p>
<p>Ce qu'elle coûte : une charge de travail réelle, une variabilité saisonnière, et une exposition à la réglementation locale. La conciergerie supprime la première, lisse la deuxième et prend en charge la troisième — c'est exactement sa raison d'être.</p>

<h2>Obtenir un chiffre pour votre bien</h2>
<p>Les ordres de grandeur ci-dessus vous situent, ils ne remplacent pas une étude. Notre <a href="/proprietaires.html#estimation">simulateur de revenus</a> vous donne une première projection en une minute, à partir du type de bien et d'une hypothèse d'occupation. Pour un chiffre sérieux, demandez-nous une estimation : nous regardons l'adresse exacte, l'étage, les extérieurs, l'équipement et la concurrence directe, et nous vous envoyons une projection écrite, gratuite et sans engagement.</p>""",
        "faq": [
            ("Quel taux d'occupation viser à Chalon-sur-Saône ?",
             "Sur l'année, un logement bien positionné et piloté quotidiennement se situe le plus souvent "
             "entre 55 % et 75 % d'occupation selon le type de bien et l'emplacement. En dessous de 50 %, "
             "c'est généralement le signe d'un problème de prix, de photos ou de paramétrage, pas de marché."),
            ("La courte durée rapporte-t-elle plus qu'une location classique ?",
             "Dans la plupart des cas oui, mais l'écart dépend entièrement du pilotage. Un logement en "
             "courte durée mal géré peut rapporter moins qu'un bail classique, tout en demandant beaucoup "
             "plus de travail. C'est la régularité de l'occupation qui fait la différence."),
            ("Faut-il investir dans du mobilier haut de gamme ?",
             "Non. Ce qui fait la note et la réservation, c'est la propreté, la literie, la connexion "
             "internet et la qualité des photographies. Un mobilier coûteux mal photographié ne rapporte rien."),
            ("Combien de temps pour que le logement atteigne son rythme de croisière ?",
             "Comptez deux à trois mois. Une annonce neuve n'a ni historique ni avis : elle doit d'abord "
             "accumuler des séjours et des notes pour remonter dans les résultats de recherche. Cette phase "
             "se pilote avec un tarif d'amorçage volontairement attractif."),
        ],
    })

    # ── 4. Choisir sa conciergerie ────────────────────────────────────────────
    arts.append({
        "slug": "choisir-sa-conciergerie-airbnb.html",
        "title": "Comment choisir sa conciergerie Airbnb : 10 questions à poser | SH Développement",
        "desc": "Commission, frais cachés, engagement, ménage, assurance : les dix questions à poser avant de confier son logement à une conciergerie Airbnb.",
        "kicker": "Conseils propriétaires · Bien choisir",
        "h1": "Choisir sa conciergerie : les 10 questions à poser avant de signer",
        "lede": "Le marché de la conciergerie s'est rempli d'acteurs très inégaux, du réseau national piloté depuis un centre d'appels à l'intermédiaire qui revend simplement votre demande. Voici comment faire le tri.",
        "date": "2026-08-15",
        "body": """<p>Confier son logement, c'est confier un actif qui vaut souvent plusieurs centaines de milliers d'euros à une entreprise que l'on connaît mal. Les questions ci-dessous ne sont pas des pièges : ce sont celles auxquelles un prestataire sérieux répond sans hésiter, par écrit. Posez-les à tous les candidats, y compris à nous.</p>

<h2>1. Quel est le taux exact de commission, et sur quelle base ?</h2>
<p>La réponse doit être un pourcentage unique et une assiette claire. Attention aux commissions annoncées « à partir de », et surtout à la base de calcul : une commission sur le montant hors frais de ménage n'a rien à voir avec une commission sur le total encaissé. Demandez un exemple chiffré sur un séjour type.</p>

<h2>2. Y a-t-il des frais en plus de la commission ?</h2>
<p>Frais de dossier, frais de mise en service, abonnement logiciel, frais de photographie, frais de sortie : ils existent chez certains acteurs et peuvent représenter plusieurs centaines d'euros. La bonne question est : « quel est le montant total que je vous verserai la première année, tout compris ? »</p>

<h2>3. Qui paie le ménage, et combien ?</h2>
<p>Dans un modèle sain, le ménage est facturé au voyageur et reversé au prestataire de ménage. Vérifiez si une marge est prise au passage, et surtout si le ménage vous est facturé lorsque le logement reste vide. Demandez le tarif de ménage appliqué à votre surface.</p>

<h2>4. Quelle est la durée d'engagement, et comment sort-on ?</h2>
<p>Un mandat d'un an reconductible tacitement avec préavis de trois mois n'a pas la même portée qu'un mandat résiliable à tout moment. Demandez aussi ce qui se passe à la sortie : récupérez-vous vos annonces, vos photographies, vos avis et votre historique ? Ce point est décisif, car l'historique d'une annonce constitue une valeur réelle.</p>

<h2>5. Sur quelles plateformes serai-je diffusé ?</h2>
<p>Une conciergerie qui ne diffuse que sur Airbnb vous prive d'une part importante de la demande, notamment de la clientèle professionnelle et étrangère qui passe par Booking.com. Demandez la liste des canaux et si un site de réservation directe existe, car c'est le seul canal sans commission de plateforme.</p>

<h2>6. Qui fixe les prix, et à quelle fréquence ?</h2>
<p>C'est la question la plus discriminante de la liste. « Nous ajustons selon la saison » signifie en pratique deux ou trois changements par an, ce qui est très insuffisant. Un pilotage sérieux recalcule les tarifs quotidiennement, en tenant compte du remplissage, de la concurrence et du calendrier local. Demandez à voir un calendrier de prix réel sur un logement comparable.</p>

<h2>7. Quel est le délai d'intervention sur place ?</h2>
<p>Un dégât des eaux, une panne de chauffage, un voyageur bloqué dehors : la vraie question est le temps nécessaire pour qu'une personne physique soit devant la porte. Une équipe locale répond en heures, un réseau national en jours. Demandez où sont physiquement basées les personnes qui interviendront chez vous.</p>

<h2>8. Que se passe-t-il en cas de dégradation ?</h2>
<p>Demandez qui constitue le dossier, qui avance les frais de remise en état, quel est le montant du dépôt de garantie exigé aux voyageurs, et comment sont documentés les états des lieux. Un prestataire qui ne photographie pas systématiquement le logement entre deux séjours ne pourra rien prouver.</p>

<h2>9. Quel reporting vais-je recevoir ?</h2>
<p>Le minimum acceptable est un relevé mensuel détaillé, séjour par séjour, avec le montant encaissé, les frais et le net reversé. Méfiez-vous d'un simple virement mensuel sans justificatif. Demandez à voir un exemple de relevé anonymisé.</p>

<h2>10. Puis-je voir vos logements et vos avis ?</h2>
<p>C'est le test le plus simple et le plus révélateur. Une conciergerie qui gère réellement des biens peut vous montrer ses annonces publiques, ses photographies et les notes laissées par les voyageurs. Si l'on vous répond que c'est confidentiel, posez-vous la question de ce qui est géré exactement.</p>

<h2>Un signal d'alerte à connaître : l'intermédiaire déguisé</h2>
<p>Une partie du trafic de recherche sur « conciergerie » est aujourd'hui captée par des sites qui ne gèrent aucun logement. Ils se présentent comme des comparateurs, des annuaires ou des « observatoires indépendants », proposent un audit gratuit de votre annonce, puis revendent votre demande à des prestataires contre commission ou facturent aux conciergeries leur référencement.</p>
<p>Ces sites ne sont pas illégaux, et certains produisent du contenu utile. Mais il faut savoir à qui l'on parle. Deux vérifications suffisent : cherchez le numéro SIREN et l'ancienneté de la société dans les mentions légales, et demandez à voir les logements effectivement gérés. Une entreprise qui exploite réellement des biens le montre en trois clics.</p>

<h2>Nos réponses, en une ligne chacune</h2>
<ul>
<li><strong>Commission</strong> : taux unique sur le montant encaissé, communiqué par écrit lors de l'estimation, sans frais de dossier, d'abonnement ni de mise en service.</li>
<li><strong>Ménage</strong> : facturé au voyageur, réalisé par nos équipes salariées ou partenaires, contrôlé après chaque intervention.</li>
<li><strong>Engagement</strong> : pas de durée bloquante ; vous récupérez votre bien et vos annonces si vous partez.</li>
<li><strong>Diffusion</strong> : Airbnb, Booking.com, Abritel et notre propre site de réservation directe, sans commission de plateforme.</li>
<li><strong>Prix</strong> : recalculés quotidiennement par notre outil de tarification, sur la base du remplissage et du calendrier local.</li>
<li><strong>Intervention</strong> : équipes basées à Chalon-sur-Saône, intervention dans la journée sur l'ensemble du Chalonnais.</li>
<li><strong>Dégradations</strong> : état des lieux photographique à chaque rotation, dossier constitué et suivi par nous.</li>
<li><strong>Reporting</strong> : relevé mensuel détaillé séjour par séjour.</li>
<li><strong>Nos logements</strong> : <a href="/catalogue.html">tous visibles publiquement ici</a>, avec les avis réels des voyageurs.</li>
</ul>
<p>Et notre SIREN, 901 242 511, figure dans nos <a href="/mentions-legales.html">mentions légales</a>.</p>""",
        "faq": [
            ("Quelle commission est normale pour une conciergerie ?",
             "Le marché français se situe généralement entre 15 % et 30 % du montant encaissé, selon "
             "l'étendue des services inclus. Un taux très bas cache souvent des frais annexes ou un "
             "service partiel ; un taux très élevé doit se justifier par des prestations réellement "
             "supérieures. Comparez toujours le montant net qui vous est reversé, pas le pourcentage seul."),
            ("Puis-je changer de conciergerie en cours de route ?",
             "Oui, sous réserve du préavis prévu au mandat. Le point à vérifier avant de signer est la "
             "restitution des annonces : celles créées sur vos propres comptes vous restent, celles créées "
             "sur les comptes du prestataire peuvent être perdues, avec l'historique et les avis."),
            ("Une conciergerie peut-elle garantir un revenu ?",
             "Une garantie de revenu existe chez certains acteurs, mais elle se paie : elle s'accompagne "
             "presque toujours d'une commission supérieure ou d'un loyer garanti inférieur au potentiel réel. "
             "Un engagement chiffré non assorti de conditions écrites doit éveiller la méfiance."),
            ("Comment vérifier qu'une conciergerie existe vraiment ?",
             "Cherchez le SIREN dans les mentions légales, vérifiez sa date d'immatriculation et son "
             "activité sur les registres publics, et demandez à voir les logements gérés ainsi que les avis "
             "des voyageurs. Ces trois vérifications prennent cinq minutes."),
        ],
    })

    return arts


def build_article(art, nav_links):
    others = "".join(
        f'<li><a href="/conseils/{a["slug"]}">{a["h1"].replace("&#8209;", "-")}</a></li>'
        for a in nav_links if a["slug"] != art["slug"]
    )
    body = art["body"] + (
        f'<h2>À lire également</h2><ul>{others}</ul>'
        f'<p>Vous souhaitez déléguer la gestion complète de votre logement ? '
        f'Découvrez <a href="/proprietaires.html">notre offre de conciergerie</a> '
        f'ou notre présence à <a href="/conciergerie-chalon-sur-saone.html">Chalon-sur-Saône</a>, '
        f'<a href="/conciergerie-macon.html">Mâcon</a>, '
        f'<a href="/conciergerie-tournus.html">Tournus</a>, '
        f'<a href="/conciergerie-beaune-chagny.html">Beaune et Chagny</a> et '
        f'<a href="/conciergerie-givry-cote-chalonnaise.html">en Côte chalonnaise</a>.</p>'
    )
    ld_article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": strip_tags(art["h1"]),
        "description": art["desc"],
        "datePublished": art["date"],
        "dateModified": TODAY,
        "inLanguage": "fr-FR",
        "author": {"@type": "Organization", "name": "SH Développement", "url": SITE + "/"},
        "publisher": {
            "@type": "Organization",
            "name": "SH Développement",
            "logo": {"@type": "ImageObject", "url": SITE + "/img/logo_gold.png"},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE}/conseils/{art['slug']}"},
        "image": SITE + "/img/hero.jpg",
    }
    trail = [("Accueil", "/"), ("Conseils propriétaires", "/conseils-proprietaires.html"),
             (strip_tags(art["h1"])[:60], f"/conseils/{art['slug']}")]
    return page(f"conseils/{art['slug']}", art["title"], art["desc"], art["kicker"],
                art["h1"], art["lede"], body, art["faq"], trail, ld_article)


def build_hub(arts):
    cards = "".join(
        f'<article class="rounded-2xl bg-white/70 border border-ecru p-6 hover:shadow-lg transition">'
        f'<p class="text-bronze text-xs uppercase tracking-luxe mb-3">{esc(a["kicker"].split("·")[-1].strip())}</p>'
        f'<h3 class="font-display text-2xl mt-0 mb-3 leading-snug">'
        f'<a href="/conseils/{a["slug"]}" class="no-underline text-ink hover:text-bronze">{a["h1"]}</a></h3>'
        f'<p class="text-ink/70 text-[15px] leading-relaxed">{esc(a["desc"])}</p>'
        f'<p class="mt-4"><a href="/conseils/{a["slug"]}" class="font-600">Lire l\'article →</a></p>'
        f"</article>"
        for a in arts
    )
    villes = "".join(
        f'<li><a href="/{c["slug"]}">Conciergerie à {c["nav_label"]}</a></li>' for c in CITY_PAGES
    )
    body = f"""<p>Louer un logement en courte durée, ce n'est pas seulement publier une annonce. C'est arbitrer entre des régimes fiscaux, respecter une réglementation qui bouge vite, fixer des prix qui suivent la demande et tenir un logement à un niveau de qualité que les voyageurs notent publiquement. Nous rassemblons ici ce que nous expliquons quotidiennement aux propriétaires qui nous confient leur bien.</p>
<div class="grid gap-6 sm:grid-cols-2 mt-10 not-prose">{cards}</div>
<h2>Notre conciergerie, secteur par secteur</h2>
<ul>{villes}</ul>
<p>Une question qui n'est traitée nulle part ici ? Écrivez-nous à <a href="mailto:{MAIL}">{MAIL}</a> ou appelez le <a href="tel:{TEL}">{TEL_H}</a> : nous répondons, même si vous ne devenez pas client.</p>"""
    trail = [("Accueil", "/"), ("Conseils propriétaires", "/conseils-proprietaires.html")]
    return page("conseils-proprietaires.html",
                "Conseils aux propriétaires de meublés de tourisme | SH Développement",
                "Fiscalité, loi Le Meur, classement, rentabilité, choix d'une conciergerie : nos guides pour les propriétaires de meublés touristiques en Bourgogne.",
                "Ressources", "Conseils aux propriétaires",
                "Fiscalité, réglementation, rentabilité, choix d'un prestataire : nos réponses aux questions que se posent les propriétaires de meublés de tourisme en Saône-et-Loire.",
                body, [], trail)


# ─────────────────────────────────────────────────────────────────────────────
def main():
    stats = load_stats()
    _, by_city, global_med = stats
    written = []

    for cfg in CITY_PAGES:
        html = build_city_page(cfg, by_city, global_med, CITY_PAGES)
        with open(os.path.join(HERE, cfg["slug"]), "w", encoding="utf-8") as f:
            f.write(html)
        written.append(cfg["slug"])

    arts = articles(stats)
    os.makedirs(os.path.join(HERE, "conseils"), exist_ok=True)
    for a in arts:
        with open(os.path.join(HERE, "conseils", a["slug"]), "w", encoding="utf-8") as f:
            f.write(build_article(a, arts))
        written.append("conseils/" + a["slug"])

    with open(os.path.join(HERE, "conseils-proprietaires.html"), "w", encoding="utf-8") as f:
        f.write(build_hub(arts))
    written.append("conseils-proprietaires.html")

    print(f"build_seo_pages : {len(written)} pages générées")
    for w in written:
        print("  ·", w)
    return written


SEO_URLS = ([c["slug"] for c in CITY_PAGES]
            + ["conseils-proprietaires.html"]
            + ["conseils/" + a["slug"] for a in articles(load_stats())]
            if os.path.exists(os.path.join(HERE, "catalogue.json")) else [])


if __name__ == "__main__":
    main()
