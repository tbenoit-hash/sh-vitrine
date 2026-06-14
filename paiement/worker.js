// =============================================================================
//  SH-Développement — Serveur de paiement (Cloudflare Worker)
//  Encaissement Payplug + création automatique de la réservation Hostaway.
//
//  AUCUNE CLÉ n'est écrite ici. Tout vient des variables d'environnement
//  (secrets Cloudflare) : voir paiement/README.md.
//    PAYPLUG_SECRET_KEY   sk_test_... puis sk_live_...
//    HOSTAWAY_ACCOUNT_ID  / HOSTAWAY_API_KEY
//    SITE_ORIGIN          https://www.sh-developpement.fr
//    WORKER_URL           https://paiement.sh-developpement.fr (URL publique de ce worker)
//    SPLIT_ENABLED        "1" pour activer le paiement scindé (propriétaire payé en direct)
//
//  Le montant N'EST JAMAIS fait confiance depuis le navigateur : il est
//  recalculé côté serveur depuis le calendrier Hostaway (anti-fraude).
// =============================================================================

const PAYPLUG_API = 'https://api.payplug.com/v1';
const HOSTAWAY_API = 'https://api.hostaway.com/v1';
const PAYPLUG_VERSION = '2019-08-06';
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

  const tok = await hostawayToken(env);
  // Recalcul du prix DEPUIS Hostaway (on ne fait jamais confiance au montant envoyé par le client)
  const quote = await computeQuote(env, tok, listingId, startDate, endDate);
  if (!quote.ok) return json({ error: 'unavailable', reason: quote.reason }, 409, cors);

  const parts = String(customer.name).trim().split(/\s+/);
  const first_name = parts.shift() || 'Client';
  const last_name = parts.join(' ') || '-';

  const payload = buildPaymentPayload({
    amountCents: Math.round(quote.total * 100), env,
    customer: { first_name, last_name, email: customer.email, mobile_phone_number: customer.phone || null },
    metadata: {
      listingId: String(listingId), startDate, endDate, guests: String(guests || 1),
      guestName: customer.name, guestPhone: customer.phone || ''
    }
  });

  const r = await fetch(`${PAYPLUG_API}/payments`, {
    method: 'POST', headers: payplugHeaders(env.PAYPLUG_SECRET_KEY), body: JSON.stringify(payload)
  });
  const pay = await r.json().catch(() => ({}));
  if (!r.ok || !pay.hosted_payment || !pay.hosted_payment.payment_url)
    return json({ error: 'payplug_error', detail: pay }, 502, cors);

  return json({ payment_url: pay.hosted_payment.payment_url, payment_id: pay.id, amount: quote.total }, 200, cors);
}

function buildPaymentPayload({ amountCents, env, customer, metadata }) {
  const base = {
    amount: amountCents,
    currency: 'EUR',
    billing: {
      first_name: customer.first_name, last_name: customer.last_name, email: customer.email,
      mobile_phone_number: customer.mobile_phone_number, country: 'FR', language: 'fr'
    },
    shipping: {
      first_name: customer.first_name, last_name: customer.last_name, email: customer.email,
      country: 'FR', delivery_type: 'DIGITAL_GOODS'
    },
    hosted_payment: {
      return_url: `${env.SITE_ORIGIN}/merci.html`,
      cancel_url: `${env.SITE_ORIGIN}/bien/${metadata.listingId}/`
    },
    notification_url: `${env.WORKER_URL}/webhook`,
    metadata,
    force_3ds: true
  };
  // ⚠️ PAIEMENT SCINDÉ (conformité — propriétaire payé en direct, SH ne garde que sa commission).
  // À finaliser avec l'offre Payplug « marketplace » / Mangopay une fois le compte ouvert :
  // le découpage bénéficiaires se branche ICI (la structure exacte dépend de l'offre Payplug).
  // Tant que SPLIT_ENABLED !== '1', le paiement est encaissé en simple (à n'utiliser qu'en test).
  // if (env.SPLIT_ENABLED === '1') base.payment_split = buildSplit(amountCents, metadata, env);
  return base;
}

// ---------------------------------------------------------------------------
// 2) Webhook Payplug → on vérifie, puis on crée la réservation Hostaway
// ---------------------------------------------------------------------------
async function handleWebhook(request, env) {
  const note = await request.json().catch(() => ({}));
  if (!note || !note.id) return json({ error: 'bad_notification' }, 400);

  // On NE fait PAS confiance au POST : on re-récupère l'objet via GET HTTPS authentifié.
  const r = await fetch(`${PAYPLUG_API}/payments/${note.id}`, { headers: payplugHeaders(env.PAYPLUG_SECRET_KEY) });
  const pay = await r.json().catch(() => ({}));
  if (!r.ok || !pay.id) return json({ error: 'verify_failed' }, 502);
  if (!pay.is_paid) return json({ ok: true, ignored: 'not_paid' }, 200); // échec / expiration → on ignore

  const tok = await hostawayToken(env);
  await createHostawayReservation(env, tok, pay.metadata || {}, pay);
  return json({ ok: true }, 200);
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
  return { ok: true, nights, cleaning, total: Math.round(base * markup) + cleaning };
}

async function createHostawayReservation(env, tok, m, pay) {
  const billing = pay.billing || {};
  const payload = {
    listingMapId: Number(m.listingId),
    channelId: 2000,                         // 2000 = réservation directe (à vérifier sur le compte)
    arrivalDate: m.startDate,
    departureDate: m.endDate,
    numberOfGuests: Number(m.guests) || 1,
    guestName: m.guestName || `${billing.first_name || ''} ${billing.last_name || ''}`.trim() || 'Voyageur',
    guestEmail: billing.email || '',
    phone: m.guestPhone || '',
    totalPrice: (Number(pay.amount) || 0) / 100,
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
function payplugHeaders(key) {
  return { Authorization: `Bearer ${key}`, 'PayPlug-Version': PAYPLUG_VERSION, 'Content-Type': 'application/json' };
}
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
