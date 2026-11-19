#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Données du simulateur de revenus de l'accueil (simulateur.json).

Source : Hostaway, 12 derniers mois complets (réservations confirmées + calendriers).
Aucune donnée personnelle : uniquement des médianes et des coefficients.

Méthode
  - Revenu net propriétaire d'une nuit = loyer (total - ménage - taxes)
      x part reçue de la plateforme (versement Airbnb / total, Booking : total - commission, sinon médiane du canal)
      x 0,80 (commission SH 20 % TTC sur le montant des locations hors frais de plateforme).
  - Nuits ouvertes = nuits disponibles + nuits réservées (les nuits bloquées par le propriétaire sont exclues).
  - Un logement compte pour un mois entre sa première et sa dernière réservation de la période ;
    revenus calculés sur les logements actifs au moins 6 mois ; remplissage affiché sur ceux loués les 12 mois
    (même base que la section « Résultats ») quand il y en a au moins 5 dans le secteur.
  - Base = médiane du revenu net par nuit ouverte des logements de Chalon-sur-Saône, par type.
  - Effet du secteur = régression log(revenu net par nuit ouverte) ~ type + secteur, rétrécie vers 0
    selon le nombre de logements (n / (n + 5)).
  - Niveau de finition et fourchette = percentiles des écarts au modèle (logements réels).
  - Saisons = revenu par nuit ouverte de chaque mois / moyenne, ville et campagne, lissé (0,25 / 0,5 / 0,25).

  python3 build_simulateur.py            (lit ../.env en local, ou HOSTAWAY_* dans l'environnement)
"""
import os, sys, json, math, datetime as dt, collections, statistics as st, concurrent.futures as cf, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_data as B

ZONES = [  # clé, libellé affiché, communes du parc
    ("chalon", "Chalon-sur-Saône", ["Chalon-sur-Saône"]),
    ("agglo", "Autour de Chalon (Grand Chalon)", ["Saint-Rémy", "Saint-Marcel", "Lux", "Champforgeuil", "Fragnes-La Loyère", "Sevrey",
                                                  "La Charmée", "Saint-Loup-de-Varennes", "Fontaines", "Châtenoy-le-Royal", "Crissey", "Virey-le-Grand"]),
    ("cote", "Côte chalonnaise, Givry, Chagny", ["Givry", "Chagny", "Dracy-le-Fort", "Buxy", "Saint-Désert", "Saint-Léger-sur-Dheune",
                                                  "Cortevaix", "Beaumont-sur-Grosne", "Mercurey", "Rully"]),
    ("macon", "Mâcon et Mâconnais", ["Mâcon", "Pierreclos"]),
    ("tournus", "Tournus", ["Tournus"]),
    ("autre", "Autre commune", ["Saint-Germain-du-Plain", "Saint-Trivier-de-Courtes"]),
]
EXCLUS = {"Les Belleville"}          # Val Thorens : hors secteur
TYPES = ["Studio", "T2", "T3", "T4", "T5", "T6+"]
COMMISSION = 0.80


def mois_periode(today):
    fin = dt.date(today.year, today.month, 1)                 # 1er du mois en cours (exclu)
    deb = dt.date(fin.year - 1, fin.month, 1)
    out, d = [], deb
    while d < fin:
        out.append(d.isoformat()[:7]); d = (d + dt.timedelta(32)).replace(day=1)
    return deb, fin, out


def main():
    B.load_env(); tok = B.get_token()
    D0, D1, MOIS = mois_periode(dt.date.today())
    cat = {x["id"]: x for x in json.load(open(os.path.join(HERE, "catalogue.json"), encoding="utf-8"))["listings"]}
    zone_of = {c: z for z, _, cs in ZONES for c in cs}

    res, off = [], 0
    a0 = (D0 - dt.timedelta(62)).isoformat()
    while True:
        r = B.api_get("/reservations", tok, {"limit": 500, "offset": off, "arrivalStartDate": a0,
                                             "arrivalEndDate": (D1 - dt.timedelta(1)).isoformat()})["result"]
        res += r; off += 500
        if len(r) < 500 or off > 40000: break
    res = [x for x in res if x.get("status") in ("new", "modified") and x.get("listingMapId") in cat]

    def part(x):
        tp = float(x.get("totalPrice") or 0)
        if tp <= 0: return None
        if x.get("airbnbExpectedPayoutAmount"): return float(x["airbnbExpectedPayoutAmount"]) / tp
        if x.get("channelCommissionAmount"): return (tp - float(x["channelCommissionAmount"])) / tp
        return None
    par_canal = collections.defaultdict(list)
    for x in res:
        p = part(x)
        if p: par_canal[x.get("channelName")].append(p)
    med_canal = {c: st.median(v) for c, v in par_canal.items()}

    nuits = collections.defaultdict(lambda: [0, 0.0])   # (logement, mois) -> nuits, net propriétaire
    brut_tot = net_tot = 0.0; first, last = {}, {}
    for x in res:
        tp = float(x.get("totalPrice") or 0)
        a = dt.date.fromisoformat(x["arrivalDate"]); d = dt.date.fromisoformat(x["departureDate"]); n = (d - a).days
        if tp <= 0 or n <= 0: continue
        l = x["listingMapId"]
        first[l] = min(first.get(l, x["arrivalDate"]), x["arrivalDate"]); last[l] = max(last.get(l, x["departureDate"]), x["departureDate"])
        p = part(x) or med_canal.get(x.get("channelName"), 0.98); p = min(max(p, 0.6), 1.0)
        loyer = (tp - float(x.get("cleaningFee") or 0) - float(x.get("taxAmount") or 0)) / n
        for i in range(n):
            j = a + dt.timedelta(i)
            if D0 <= j < D1:
                v = nuits[(l, j.isoformat()[:7])]; v[0] += 1; v[1] += loyer * p * COMMISSION
                brut_tot += loyer; net_tot += loyer * p * COMMISSION

    def cal(l):
        for k in range(4):
            try:
                c = B.api_get(f"/listings/{l}/calendar", tok, {"startDate": D0.isoformat(), "endDate": (D1 - dt.timedelta(1)).isoformat()})["result"]
                m = collections.Counter(day["date"][:7] for day in c if day.get("status") == "available")
                return l, m
            except Exception:
                time.sleep(2 + 2 * k)
        return l, None
    with cf.ThreadPoolExecutor(6) as ex:
        cals = dict(ex.map(cal, [l for l in cat if cat[l]["city"] not in EXCLUS]))

    lm = []   # logement-mois actifs
    for l, c in cals.items():
        if c is None or l not in first: continue
        for m in MOIS:
            if first[l][:7] > m or last[l][:7] < m: continue
            n, net = nuits.get((l, m), (0, 0.0)); ouv = c.get(m, 0) + n
            if ouv >= 10: lm.append((l, m, n, net, ouv))

    agg = collections.defaultdict(lambda: [0, 0.0, 0, 0])
    for l, m, n, net, ouv in lm:
        a = agg[l]; a[0] += n; a[1] += net; a[2] += ouv; a[3] += 1
    L = []
    for l, (n, net, ouv, k) in agg.items():
        c = cat[l]
        if k < 6 or n < 20: continue
        L.append({"l": l, "type": c["type"], "zone": zone_of.get(c["city"], "autre"), "rpn": net / ouv, "occ": n / ouv,
                  "nuits": n, "annee": k >= len(MOIS)})

    # base Chalon par type, puis types rares dérivés du parc
    def med(xs): return st.median(xs) if xs else None
    base = {t: med([x["rpn"] for x in L if x["zone"] == "chalon" and x["type"] == t]) for t in TYPES}
    parc = {t: med([x["rpn"] for x in L if x["type"] == t]) for t in TYPES}
    for t in TYPES:
        nb = sum(1 for x in L if x["zone"] == "chalon" and x["type"] == t)
        if base[t] is None or nb < 4: base[t] = parc[t]
    if base.get("T5") is None or sum(1 for x in L if x["type"] == "T5") < 5:
        base["T5"] = (base["T4"] + base["T6+"]) / 2 if base.get("T6+") else base["T4"] * 1.2
    for i in range(1, len(TYPES)):           # jamais moins qu'un type plus petit
        base[TYPES[i]] = max(base[TYPES[i]], base[TYPES[i - 1]] * 1.05)

    # effet secteur : moyenne des log-écarts à la base du type, rétrécie
    eff = {}
    for z, _, _ in ZONES:
        xs = [math.log(x["rpn"] / base[x["type"]]) for x in L if x["zone"] == z and x["rpn"] > 0]
        eff[z] = 0.0 if z == "chalon" or not xs else st.mean(xs) * len(xs) / (len(xs) + 5)
    # remplissage affiché : logements loués toute l'année (même base que « Résultats ») si au moins 5 dans le secteur,
    # sinon tous les logements retenus, rétréci vers la médiane du parc
    occ_parc = med([x["occ"] for x in L])
    occ = {}
    for z, _, _ in ZONES:
        an = [x["occ"] for x in L if x["zone"] == z and x["annee"]]
        xs = [x["occ"] for x in L if x["zone"] == z]
        occ[z] = med(an) if len(an) >= 5 else (sum(xs) + 5 * occ_parc) / (len(xs) + 5)

    resid = sorted(math.log(x["rpn"] / (base[x["type"]] * math.exp(eff[x["zone"]]))) for x in L if x["rpn"] > 0)
    def pct(p): return math.exp(resid[min(len(resid) - 1, int(p * len(resid)))])
    finition = {"simple": round(pct(0.30), 3), "soigne": round(pct(0.50), 3), "haut": round(pct(0.75), 3)}
    fourchette = [round(pct(0.25) / pct(0.50), 3), round(pct(0.75) / pct(0.50), 3)]

    zone_l = {l: zone_of.get(cat[l]["city"], "autre") for l in cat}
    saison = {}
    for g, zs in (("ville", {"chalon", "macon", "agglo"}), ("campagne", {"cote", "tournus", "autre"})):
        s = collections.defaultdict(lambda: [0.0, 0])
        for l, m, n, net, ouv in lm:
            if zone_l.get(l) in zs: s[m][0] += net; s[m][1] += ouv
        v = [s[m][0] / s[m][1] if s[m][1] else 0 for m in MOIS]
        moy = sum(v) / len(v)
        raw = [x / moy for x in v]
        lis = [0.25 * raw[i - 1] + 0.5 * raw[i] + 0.25 * raw[(i + 1) % 12] for i in range(12)]
        k = 12 / sum(lis)
        par_mois = {int(m[5:]): round(lis[i] * k, 3) for i, m in enumerate(MOIS)}
        saison[g] = [par_mois[i] for i in range(1, 13)]   # janvier à décembre

    out = {
        "maj": dt.date.today().isoformat(),
        "periode": [D0.isoformat(), (D1 - dt.timedelta(1)).isoformat()],
        "logements": len(L), "nuits": sum(x["nuits"] for x in L),
        "part_proprietaire": round(net_tot / brut_tot, 3),
        "base": {t: round(base[t], 2) for t in TYPES},
        "zones": [{"k": z, "label": lab, "mult": round(math.exp(eff[z]), 3), "occ": round(occ[z], 3),
                   "saison": "campagne" if z in ("cote", "tournus", "autre") else "ville",
                   "n": sum(1 for x in L if x["zone"] == z)} for z, lab, _ in ZONES],
        "finition": finition, "fourchette": fourchette, "saison": saison,
    }
    json.dump(out, open(os.path.join(HERE, "simulateur.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
