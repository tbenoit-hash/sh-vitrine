// Test local du worker SANS vraies clés : on simule Payplug et Hostaway en
// interceptant fetch(), et on vérifie le flux complet.
//   node test-local.mjs   (ou: npm test)
import worker from './worker.js';

// ---- petit framework d'assertions ----
let pass = 0, fail = 0;
const ok = (cond, label) => { if (cond) { pass++; console.log('  ✅', label); } else { fail++; console.log('  ❌', label); } };

// ---- dates de test (J+10 → J+13 = 3 nuits) ----
const d = n => { const x = new Date(); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };
const startDate = d(10), endDate = d(13);

// ---- état mutable des mocks ----
let CALENDAR = [];            // lignes /calendar
let LAST_PAYMENT = null;      // payload envoyé à Payplug
let RESERVATION = null;       // payload envoyé à Hostaway /reservations
const jr = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });

globalThis.fetch = async (url, opts = {}) => {
  url = String(url); const method = opts.method || 'GET';
  if (url.endsWith('/accessTokens')) return jr({ access_token: 'tok_test' });
  if (/\/listings\/\d+\/calendar/.test(url)) return jr({ result: CALENDAR });
  if (/\/listings\/\d+$/.test(url)) return jr({ result: { bookingEngineMarkup: 1.05, cleaningFee: 300 } });
  if (url.endsWith('/v1/payments') && method === 'POST') { LAST_PAYMENT = JSON.parse(opts.body); return jr({ id: 'pay_test', object: 'payment', hosted_payment: { payment_url: 'https://secure.payplug.com/pay/test/abc' } }); }
  if (/\/v1\/payments\/pay_test$/.test(url)) return jr({ id: 'pay_test', is_paid: true, amount: LAST_PAYMENT.amount, billing: LAST_PAYMENT.billing, metadata: LAST_PAYMENT.metadata });
  if (/\/reservations/.test(url) && method === 'POST') { RESERVATION = JSON.parse(opts.body); return jr({ status: 'success', result: { id: 999 } }); }
  return jr({ error: 'unmocked: ' + url }, 404);
};

const ENV = {
  PAYPLUG_SECRET_KEY: 'sk_test_xxx', HOSTAWAY_ACCOUNT_ID: '136426', HOSTAWAY_API_KEY: 'k',
  SITE_ORIGIN: 'https://www.sh-developpement.fr', WORKER_URL: 'https://paiement.sh-developpement.fr'
};
const req = (path, body) => new Request('https://paiement.sh-developpement.fr' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const availCal = () => [d(10), d(11), d(12), d(13)].map((date, i) => ({ date, isAvailable: 1, status: 'available', price: 200, minimumStay: 1 }));

// =====================================================================
console.log('\nTest 1 — création du paiement (prix recalculé serveur)');
CALENDAR = availCal(); // 3 nuits × 200 = 600 ; ×1,05 = 630 ; +300 ménage = 930 €
{
  const res = await worker.fetch(req('/create-payment', {
    listingId: 470939, startDate, endDate, guests: 2,
    customer: { name: 'Jean Dupont', email: 'jean@example.fr', phone: '0600000000' }
  }), ENV);
  const j = await res.json();
  ok(res.status === 200, 'HTTP 200');
  ok(j.payment_url === 'https://secure.payplug.com/pay/test/abc', 'renvoie l\'URL de paiement Payplug');
  ok(j.amount === 930, 'montant recalculé serveur = 930 € (3 nuits×200×1,05 + 300 ménage)');
  ok(LAST_PAYMENT && LAST_PAYMENT.amount === 93000, 'Payplug reçoit 93000 centimes');
  ok(LAST_PAYMENT.billing.email === 'jean@example.fr', 'client transmis à Payplug');
  ok(LAST_PAYMENT.metadata.listingId === '470939' && LAST_PAYMENT.metadata.startDate === startDate, 'métadonnées (logement + dates) jointes');
  ok(LAST_PAYMENT.notification_url === 'https://paiement.sh-developpement.fr/webhook', 'webhook (notification_url) configuré');
  ok(LAST_PAYMENT.force_3ds === true, '3-D Secure forcé');
}

console.log('\nTest 2 — webhook payé → réservation créée dans Hostaway');
{
  const res = await worker.fetch(req('/webhook', { id: 'pay_test', object: 'payment', is_live: false }), ENV);
  const j = await res.json();
  ok(res.status === 200 && j.ok === true, 'webhook traité (200)');
  ok(RESERVATION && RESERVATION.listingMapId === 470939, 'réservation Hostaway sur le bon logement');
  ok(RESERVATION.arrivalDate === startDate && RESERVATION.departureDate === endDate, 'dates correctes');
  ok(RESERVATION.numberOfGuests === 2, 'nombre de voyageurs correct');
  ok(RESERVATION.totalPrice === 930 && RESERVATION.isPaid === 1, 'montant payé reporté + marqué payé');
  ok(RESERVATION.guestName === 'Jean Dupont', 'nom du voyageur repris');
}

console.log('\nTest 3 — webhook NON payé (échec) → on ne crée rien');
{
  RESERVATION = null;
  globalThis.fetch = (orig => async (url, opts = {}) => {
    if (/\/v1\/payments\/pay_test$/.test(String(url))) return jr({ id: 'pay_test', is_paid: false, failure: { code: 'card_declined' } });
    return orig(url, opts);
  })(globalThis.fetch);
  const res = await worker.fetch(req('/webhook', { id: 'pay_test' }), ENV);
  const j = await res.json();
  ok(res.status === 200 && j.ignored === 'not_paid', 'paiement échoué ignoré');
  ok(RESERVATION === null, 'aucune réservation créée si non payé');
}

console.log('\nTest 4 — dates indisponibles → 409, pas de paiement');
{
  LAST_PAYMENT = null;
  CALENDAR = availCal(); CALENDAR[1] = { ...CALENDAR[1], isAvailable: 0, status: 'reserved' };
  // on restaure un fetch propre (sans l'override du test 3)
  globalThis.fetch = async (url, opts = {}) => {
    url = String(url); const method = opts.method || 'GET';
    if (url.endsWith('/accessTokens')) return jr({ access_token: 'tok_test' });
    if (/\/listings\/\d+\/calendar/.test(url)) return jr({ result: CALENDAR });
    if (/\/listings\/\d+$/.test(url)) return jr({ result: { bookingEngineMarkup: 1.05, cleaningFee: 300 } });
    if (url.endsWith('/v1/payments') && method === 'POST') { LAST_PAYMENT = JSON.parse(opts.body); return jr({ id: 'pay_test', hosted_payment: { payment_url: 'x' } }); }
    return jr({ error: 'unmocked' }, 404);
  };
  const res = await worker.fetch(req('/create-payment', {
    listingId: 470939, startDate, endDate, guests: 2, customer: { name: 'Jean Dupont', email: 'jean@example.fr' }
  }), ENV);
  ok(res.status === 409, 'HTTP 409 (indisponible)');
  ok(LAST_PAYMENT === null, 'aucun paiement créé si dates prises');
}

console.log(`\n${fail === 0 ? '🎉 TOUT PASSE' : '⚠️ ÉCHECS'} — ${pass} réussis, ${fail} échoués\n`);
process.exit(fail === 0 ? 0 : 1);
