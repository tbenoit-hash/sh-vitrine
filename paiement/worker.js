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
    const cors = corsHeaders(env);
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });
    try {
      if (url.pathname === '/create-payment' && request.method === 'POST') return await createPayment(request, env, cors);
      if (url.pathname === '/webhook' && request.method === 'POST') return await handleWebhook(request, env);
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
  // Part propriétaire = hébergement brut × (1 − commission).
  // SH garde : commission + frais de dossier (markup) + ménage = totalCents − part proprio.
  const ownerCents = Math.round(quote.base * (1 - split.commission) * 100);
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
  if (event.type !== 'checkout.session.completed') return json({ ok: true, ignored: event.type }, 200);

  // On NE fait PAS confiance au POST : on re-récupère la session via GET authentifié.
  const id = event.data && event.data.object && event.data.object.id;
  if (!id) return json({ error: 'bad_notification' }, 400);
  const session = await stripeGet(env, `/checkout/sessions/${id}`);
  if (!session || !session.id) return json({ error: 'verify_failed' }, 502);
  if (session.payment_status !== 'paid') return json({ ok: true, ignored: 'not_paid' }, 200);

  const tok = await hostawayToken(env);
  await createHostawayReservation(env, tok, session.metadata || {}, session);
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
  return { acct: row.acct, commission };
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
function corsHeaders(env) {
  return {
    'Access-Control-Allow-Origin': env.SITE_ORIGIN || '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  };
}
function json(obj, status = 200, extra = {}) {
  return new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', ...extra } });
}
