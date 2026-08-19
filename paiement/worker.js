// =============================================================================
//  SH-Développement — Serveur de paiement (Cloudflare Worker)
//  Encaissement Stripe Connect (paiement scindé) + création auto de la
//  réservation Hostaway.
//
//  CONFORMITÉ (décision Terence 06/08/2026) : l'argent de la LOCATION ne transite
//  jamais par SH. Le paiement est scindé à la source par Stripe :
//    · propriétaire  → hébergement × (1 − commission)   (virement direct Stripe)
//    · SH            → commission + frais de dossier (markup) + ménage
//  Un logement dont le propriétaire n'est pas enrôlé (pas de compte Stripe
//  connecté) NE PEUT PAS être payé en ligne → le site garde le flux « demande ».
//
//  AUCUNE CLÉ n'est écrite ici. Secrets Cloudflare (wrangler secret put) :
//    STRIPE_SECRET_KEY      sk_test_… puis sk_live_… (compte plateforme SH)
//    STRIPE_WEBHOOK_SECRET  whsec_… (endpoint /webhook ; si absent, la
//                           vérification repose uniquement sur le re-fetch GET)
//    HOSTAWAY_ACCOUNT_ID / HOSTAWAY_API_KEY
//  Binding KV : SPLIT_KV, clé "config" =
//    { "default_commission": 0.20,
//      "<listingId>": { "acct": "acct_…", "commission": 0.20 }, … }
//  (poussé par paiement/onboard_proprietaires.py, jamais committé : les taux
//   par logement ne doivent pas être publics.)
//
//  Le montant N'EST JAMAIS fait confiance depuis le navigateur : il est
//  recalculé côté serveur depuis le calendrier Hostaway (anti-fraude).
// =============================================================================

const STRIPE_API = 'https://api.stripe.com/v1';
const HOSTAWAY_API = 'https://api.hostaway.com/v1';
const UNAVAILABLE = ['reserved', 'blocked', 'unavailable'];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(env, request);
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });
    try {
      if (url.pathname === '/create-payment' && request.method === 'POST') return await createPayment(request, env, cors);
      if (url.pathname === '/webhook' && request.method === 'POST') return await handleWebhook(request, env);
      if (url.pathname === '/onboard' && request.method === 'GET') return await onboardRedirect(request, env);
      if (url.pathname === '/onboard/retour' && request.method === 'GET') return onboardPage('retour');
      if (url.pathname === '/health') return json({ ok: true }, 200, cors);
      return json({ error: 'not_found' }, 404, cors);
    } catch (e) {
      return json({ error: 'server_error', detail: String((e && e.message) || e) }, 500, cors);
    }
  }
};

// ---------------------------------------------------------------------------
// 1) Création du paiement — appelé par la fiche logement du site
// ---------------------------------------------------------------------------
async function createPayment(request, env, cors) {
  const body = await request.json().catch(() => null);
  const { listingId, startDate, endDate, guests, customer } = body || {};
  if (!listingId || !startDate || !endDate || !customer || !customer.email || !customer.name)
    return json({ error: 'missing_fields' }, 400, cors);

  // Propriétaire enrôlé ? Sans compte Stripe connecté, pas de paiement en ligne.
  const split = await splitFor(env, listingId);
  if (!split) return json({ error: 'owner_not_onboarded' }, 409, cors);

  const tok = await hostawayToken(env);
  // Recalcul du prix DEPUIS Hostaway (on ne fait jamais confiance au montant du client)
  const quote = await computeQuote(env, tok, listingId, startDate, endDate);
  if (!quote.ok) return json({ error: 'unavailable', reason: quote.reason }, 409, cors);

  const totalCents = Math.round(quote.total * 100);
  // Part propriétaire = hébergement brut × (1 − commission), plus les frais de
  // ménage lorsque le contrat prévoit qu'ils lui reviennent (SH les lui
  // refacture alors séparément : cas Auberger).
  // SH garde le reste : commission + frais de dossier (markup) [+ ménage].
  const ownerCents = Math.round(quote.base * (1 - split.commission) * 100)
    + (split.menageProprio ? Math.round(quote.cleaning * 100) : 0);
  const feeCents = totalCents - ownerCents;
  if (feeCents < 0 || ownerCents <= 0) return json({ error: 'bad_split' }, 500, cors);

  const meta = {
    listingId: String(listingId), startDate, endDate, guests: String(guests || 1),
    guestName: customer.name, guestPhone: customer.phone || '', guestEmail: customer.email
  };
  const session = await stripePost(env, '/checkout/sessions', {
    mode: 'payment',
    locale: 'fr',
    customer_email: customer.email,
    'line_items[0][quantity]': '1',
    'line_items[0][price_data][currency]': 'eur',
    'line_items[0][price_data][unit_amount]': String(totalCents),
    'line_items[0][price_data][product_data][name]': `Séjour du ${startDate} au ${endDate} · ${quote.nights} nuit(s)`,
    'line_items[0][price_data][product_data][description]': 'Tarif non remboursable',
    // Politique d'annulation (décision Terence 19/08/2026) : non remboursable.
    // Affichée sur la page Stripe ET acceptée explicitement (case à cocher) :
    // indispensable pour défendre une contestation « credit not processed ».
    'custom_text[terms_of_service_acceptance][message]': `Séjour à [tarif non remboursable](${env.SITE_ORIGIN}/cgv.html) : aucune annulation remboursée (CGV, art. 5).`,
    'consent_collection[terms_of_service]': 'required',
    'payment_intent_data[application_fee_amount]': String(feeCents),
    'payment_intent_data[transfer_data][destination]': split.acct,
    'payment_intent_data[description]': `SH Développement · logement ${listingId} · ${startDate} → ${endDate}`,
    'payment_method_options[card][request_three_d_secure]': 'any',
    success_url: `${env.SITE_ORIGIN}/merci-reservation.html?s={CHECKOUT_SESSION_ID}`,
    cancel_url: `${env.SITE_ORIGIN}/bien/${listingId}/`,
    ...Object.fromEntries(Object.entries(meta).map(([k, v]) => [`metadata[${k}]`, v]))
  });
  if (!session || !session.url) return json({ error: 'stripe_error', detail: session }, 502, cors);

  return json({ payment_url: session.url, payment_id: session.id, amount: quote.total }, 200, cors);
}

// ---------------------------------------------------------------------------
// 2) Webhook Stripe → vérification, puis réservation Hostaway
// ---------------------------------------------------------------------------
async function handleWebhook(request, env) {
  const raw = await request.text();
  if (env.STRIPE_WEBHOOK_SECRET) {
    const okSig = await verifyStripeSignature(raw, request.headers.get('Stripe-Signature') || '', env.STRIPE_WEBHOOK_SECRET);
    if (!okSig) return json({ error: 'bad_signature' }, 400);
  }
  const event = safeParse(raw);
  if (!event || !event.type) return json({ error: 'bad_notification' }, 400);
  // `completed` couvre la carte ; `async_payment_succeeded` couvre les moyens de
  // paiement différés (prélèvement, virement…), qui se règlent après le checkout.
  // Sans ce second événement, une réservation payée en différé ne serait jamais créée.
  const FULFILL = ['checkout.session.completed', 'checkout.session.async_payment_succeeded'];
  if (!FULFILL.includes(event.type)) return json({ ok: true, ignored: event.type }, 200);

  // On NE fait PAS confiance au POST : on re-récupère la session via GET authentifié.
  const id = event.data && event.data.object && event.data.object.id;
  if (!id) return json({ error: 'bad_notification' }, 400);
  const session = await stripeGet(env, `/checkout/sessions/${id}`);
  if (!session || !session.id) return json({ error: 'verify_failed' }, 502);
  if (session.payment_status !== 'paid') return json({ ok: true, ignored: 'not_paid' }, 200);

  // Idempotence : Stripe réémet un webhook tant qu'il n'a pas reçu de 2xx, et les
  // deux événements ci-dessus peuvent tomber pour la même session. Sans garde, on
  // créerait plusieurs fois la même réservation dans Hostaway.
  const doneKey = `done:${session.id}`;
  if (env.SPLIT_KV) {
    const already = await env.SPLIT_KV.get(doneKey);
    if (already) return json({ ok: true, ignored: 'already_fulfilled' }, 200);
  }

  const tok = await hostawayToken(env);
  const res = await createHostawayReservation(env, tok, session.metadata || {}, session);
  if (env.SPLIT_KV) {
    // 90 jours : bien au-delà de la fenêtre de réémission de Stripe.
    await env.SPLIT_KV.put(doneKey, String((res && (res.id || (res.result && res.result.id))) || 'ok'), { expirationTtl: 7776000 });
  }
  return json({ ok: true }, 200);
}

// ---------------------------------------------------------------------------
// Répartition (KV) — { "default_commission": 0.20, "<id>": { acct, commission } }
// ---------------------------------------------------------------------------
async function splitFor(env, listingId) {
  if (!env.SPLIT_KV) return null;
  const cfg = safeParse(await env.SPLIT_KV.get('config')) || {};
  const row = cfg[String(listingId)];
  if (!row || !row.acct) return null;
  const commission = Number(row.commission != null ? row.commission : cfg.default_commission);
  if (!(commission >= 0 && commission < 1)) return null;
  // Un compte créé n'est pas un compte prêt : tant que le propriétaire n'a pas
  // terminé sa vérification, Stripe refuse le virement. On le détecte AVANT de
  // créer le paiement, pour renvoyer owner_not_onboarded et laisser le site
  // retomber sur la demande de réservation.
  if (!(await canReceiveTransfers(env, row.acct))) return null;
  return { acct: row.acct, commission, menageProprio: row.menage_proprio === true };
}

// Capacité v2 « recipient » : stripe_balance.stripe_transfers doit être active.
// Résultat mis en cache 1 h : l'état ne change qu'au rythme des vérifications Stripe.
async function canReceiveTransfers(env, acct) {
  const key = `cap:${acct}`;
  if (env.SPLIT_KV) {
    const cached = await env.SPLIT_KV.get(key);
    if (cached === '1') return true;
    if (cached === '0') return false;
  }
  // Accounts v2 d'abord ; si la plateforme n'y a pas droit (ou si le compte a été
  // créé en v1), on lit la capacité `transfers` de l'API historique.
  let ok = false;
  const r = await fetch(
    `https://api.stripe.com/v2/core/accounts/${acct}?include=configuration.recipient`,
    { headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`, 'Stripe-Version': '2026-07-29.preview' } }
  );
  const a = r.ok ? await r.json().catch(() => null) : null;
  const st = a && a.configuration && a.configuration.recipient
    && a.configuration.recipient.capabilities
    && a.configuration.recipient.capabilities.stripe_balance
    && a.configuration.recipient.capabilities.stripe_balance.stripe_transfers
    && a.configuration.recipient.capabilities.stripe_balance.stripe_transfers.status;
  if (st) {
    ok = st === 'active';
  } else {
    const r1 = await fetch(`https://api.stripe.com/v1/accounts/${acct}`,
      { headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` } });
    const a1 = r1.ok ? await r1.json().catch(() => null) : null;
    ok = !!(a1 && a1.capabilities && a1.capabilities.transfers === 'active');
  }
  // On ne met en cache un « non » que brièvement : le propriétaire peut finir
  // son onboarding d'une minute à l'autre.
  if (env.SPLIT_KV) await env.SPLIT_KV.put(key, ok ? '1' : '0', { expirationTtl: ok ? 3600 : 300 });
  return ok;
}

// ---------------------------------------------------------------------------
// 1 bis) Enrôlement du propriétaire — lien d'invitation PERMANENT
//
// Les liens Stripe (AccountLink) expirent en quelques minutes : impossible de
// les envoyer par mail. Le propriétaire reçoit donc une URL stable
//   https://…/onboard?k=<jeton>
// et c'est le worker qui fabrique un lien Stripe FRAIS à chaque clic. Stripe
// rappelle lui-même cette URL (refresh_url) si le lien expire pendant le
// parcours, donc le propriétaire ne tombe jamais sur « lien expiré ».
//
// KV : `onb:<jeton>` = { "acct": "acct_…", "nom": "…" } (écrit par
// liens_proprietaires.py). Le jeton est aléatoire (32 hex) et ne donne accès
// qu'au formulaire Stripe du propriétaire concerné.
// ---------------------------------------------------------------------------
async function onboardRedirect(request, env) {
  const url = new URL(request.url);
  const token = (url.searchParams.get('k') || '').trim();
  if (!/^[a-f0-9]{16,64}$/.test(token) || !env.SPLIT_KV) return onboardPage('inconnu');

  const row = safeParse(await env.SPLIT_KV.get(`onb:${token}`));
  if (!row || !row.acct) return onboardPage('inconnu');

  // Déjà vérifié : inutile de renvoyer le propriétaire dans le formulaire.
  if (await canReceiveTransfers(env, row.acct)) return onboardPage('deja', row.nom);

  const base = env.WORKER_URL || url.origin;
  const link = await stripePost(env, '/account_links', {
    account: row.acct,
    type: 'account_onboarding',
    refresh_url: `${base}/onboard?k=${token}`,
    return_url: `${base}/onboard/retour`,
    'collection_options[fields]': 'eventually_due'
  });
  if (!link || !link.url) return onboardPage('erreur', row.nom);
  return new Response(null, { status: 302, headers: { Location: link.url, 'Cache-Control': 'no-store' } });
}

// Petites pages de service (charte brun/or), servies par le worker pour ne pas
// dépendre d'un déploiement du site.
function onboardPage(cas, nom) {
  const T = {
    retour: ['Merci, c’est enregistré',
      'Vos informations ont été transmises à Stripe. La vérification prend en général quelques minutes, parfois 24 h. Dès qu’elle est validée, vos logements peuvent être réservés et payés en direct, et votre part vous est versée automatiquement.'],
    deja: ['Votre compte est déjà validé',
      'Rien de plus à faire : votre compte de versement est actif. Les réservations en direct vous sont versées automatiquement.'],
    inconnu: ['Lien non reconnu',
      'Ce lien n’est plus valable ou a été mal recopié. Écrivez à contact@sh-developpement.fr et nous vous en renvoyons un.'],
    erreur: ['Petit contretemps',
      'Stripe n’a pas répondu correctement. Réessayez dans quelques minutes ou écrivez à contact@sh-developpement.fr.']
  }[cas] || ['', ''];
  const bonjour = nom ? `<p style="margin:0 0 10px;color:#6b5b4a;">Bonjour ${escapeHtml(nom)},</p>` : '';
  const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${T[0]} · SH Développement</title></head>
<body style="margin:0;background:#fbf9f4;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#3a2f25;">
<div style="max-width:560px;margin:8vh auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 18px rgba(0,0,0,.06);">
  <div style="background:#463618;padding:22px 26px;">
    <div style="color:#FFD549;font-size:13px;letter-spacing:.08em;text-transform:uppercase;">SH Développement</div>
    <div style="color:#f4ead6;font-size:20px;font-weight:700;margin-top:6px;">${T[0]}</div>
  </div>
  <div style="padding:22px 26px;font-size:15px;line-height:1.6;">${bonjour}<p style="margin:0;">${T[1]}</p></div>
  <div style="padding:14px 26px;background:#fbf9f4;color:#9a8a78;font-size:12px;">SH Développement · contact@sh-developpement.fr</div>
</div></body></html>`;
  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------------------
// Stripe (REST, form-encodé)
// ---------------------------------------------------------------------------
async function stripePost(env, path, params) {
  const r = await fetch(STRIPE_API + path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(params).toString()
  });
  return r.json().catch(() => null);
}
async function stripeGet(env, path) {
  const r = await fetch(STRIPE_API + path, { headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` } });
  return r.json().catch(() => null);
}

// Signature Stripe : Stripe-Signature = "t=…,v1=hmac_sha256(t + '.' + payload)"
async function verifyStripeSignature(payload, header, secret, toleranceSec = 300) {
  const parts = Object.fromEntries(header.split(',').map(p => p.split('=')));
  const t = Number(parts.t), v1 = parts.v1;
  if (!t || !v1) return false;
  if (Math.abs(Date.now() / 1000 - t) > toleranceSec) return false;
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const mac = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`${t}.${payload}`));
  const hex = [...new Uint8Array(mac)].map(b => b.toString(16).padStart(2, '0')).join('');
  return hex === v1;
}

// ---------------------------------------------------------------------------
// Hostaway
// ---------------------------------------------------------------------------
async function hostawayToken(env) {
  const data = new URLSearchParams({
    grant_type: 'client_credentials', client_id: env.HOSTAWAY_ACCOUNT_ID,
    client_secret: env.HOSTAWAY_API_KEY, scope: 'general'
  });
  const r = await fetch(`${HOSTAWAY_API}/accessTokens`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Cache-control': 'no-cache' },
    body: data.toString()
  });
  const j = await r.json().catch(() => ({}));
  if (!j.access_token) throw new Error('hostaway_auth_failed');
  return j.access_token;
}

async function computeQuote(env, tok, listingId, startDate, endDate) {
  const cal = await fetch(`${HOSTAWAY_API}/listings/${listingId}/calendar?startDate=${startDate}&endDate=${endDate}`,
    { headers: { Authorization: `Bearer ${tok}` } });
  const rows = ((await cal.json().catch(() => ({}))).result) || [];
  let base = 0, nights = 0, available = true;
  for (const row of rows) {
    if (row.date >= endDate) continue; // la nuit de départ ne se paie pas
    const st = String(row.status || '').toLowerCase();
    if (!row.isAvailable || UNAVAILABLE.includes(st)) available = false;
    base += Number(row.price) || 0; nights++;
  }
  if (!available || nights < 1) return { ok: false, reason: 'dates_unavailable' };

  const lr = await fetch(`${HOSTAWAY_API}/listings/${listingId}`, { headers: { Authorization: `Bearer ${tok}` } });
  const l = ((await lr.json().catch(() => ({}))).result) || {};
  const markup = Number(l.bookingEngineMarkup) || 1;
  const cleaning = Number(l.cleaningFee) || 0;
  // base = hébergement brut (assiette de la part propriétaire) ; total = payé par le voyageur
  return { ok: true, nights, base, cleaning, total: Math.round(base * markup) + cleaning };
}

async function createHostawayReservation(env, tok, m, session) {
  const payload = {
    listingMapId: Number(m.listingId),
    channelId: 2000,                         // 2000 = réservation directe (à vérifier sur le compte)
    arrivalDate: m.startDate,
    departureDate: m.endDate,
    numberOfGuests: Number(m.guests) || 1,
    guestName: m.guestName || 'Voyageur',
    guestEmail: m.guestEmail || (session.customer_details && session.customer_details.email) || '',
    phone: m.guestPhone || '',
    totalPrice: (Number(session.amount_total) || 0) / 100,
    isPaid: 1,
    source: 'Site direct SH'
  };
  const r = await fetch(`${HOSTAWAY_API}/reservations?forceOverbooking=0`, {
    method: 'POST', headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error('hostaway_reservation_failed: ' + JSON.stringify(j));
  return j;
}

// ---------------------------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------------------------
function safeParse(s) { try { return JSON.parse(s); } catch { return null; } }
function corsHeaders(env, request) {
  // Le site de production, plus l'aperçu local servi sur localhost pendant les
  // tests. Aucune autre origine n'est autorisée à créer un paiement.
  const site = env.SITE_ORIGIN || '';
  const origin = (request && request.headers.get('Origin')) || '';
  const localhost = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
  return {
    'Access-Control-Allow-Origin': localhost ? origin : (site || '*'),
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  };
}
function json(obj, status = 200, extra = {}) {
  return new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', ...extra } });
}
