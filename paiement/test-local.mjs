// Test local du worker SANS vraies clés : on simule Stripe et Hostaway en
// interceptant fetch(), et on vérifie le flux complet, split compris.
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
let LAST_SESSION = null;      // params envoyés à Stripe /checkout/sessions (URLSearchParams décodés)
let SESSION_STATE = 'paid';   // payment_status renvoyé par le GET session
let RESERVATION = null;       // payload envoyé à Hostaway /reservations
const jr = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });

function mockFetch() {
  return async (url, opts = {}) => {
    url = String(url); const method = opts.method || 'GET';
    if (url.endsWith('/accessTokens')) return jr({ access_token: 'tok_test' });
    if (/\/listings\/\d+\/calendar/.test(url)) return jr({ result: CALENDAR });
    if (/\/listings\/\d+$/.test(url)) return jr({ result: { bookingEngineMarkup: 1.05, cleaningFee: 300 } });
    if (url.endsWith('/checkout/sessions') && method === 'POST') {
      LAST_SESSION = Object.fromEntries(new URLSearchParams(opts.body));
      return jr({ id: 'cs_test', url: 'https://checkout.stripe.com/c/pay/cs_test' });
    }
    if (/\/checkout\/sessions\/cs_test$/.test(url)) {
      return jr({
        id: 'cs_test', payment_status: SESSION_STATE,
        amount_total: Number(LAST_SESSION['line_items[0][price_data][unit_amount]']),
        customer_details: { email: LAST_SESSION.customer_email },
        metadata: Object.fromEntries(Object.entries(LAST_SESSION)
          .filter(([k]) => k.startsWith('metadata['))
          .map(([k, v]) => [k.slice(9, -1), v]))
      });
    }
    if (/\/reservations/.test(url) && method === 'POST') { RESERVATION = JSON.parse(opts.body); return jr({ status: 'success', result: { id: 999 } }); }
    return jr({ error: 'unmocked: ' + url }, 404);
  };
}
globalThis.fetch = mockFetch();

// KV simulé : logement 470939 enrôlé à 20 %, 555555 à 2 % (type Beguet), 111111 PAS enrôlé
const SPLIT = {
  default_commission: 0.20,
  470939: { acct: 'acct_OWNER1', commission: 0.20 },
  555555: { acct: 'acct_BEGUET', commission: 0.02 }
};
const ENV = {
  STRIPE_SECRET_KEY: 'sk_test_xxx', HOSTAWAY_ACCOUNT_ID: '136426', HOSTAWAY_API_KEY: 'k',
  SITE_ORIGIN: 'https://www.sh-developpement.fr',
  SPLIT_KV: { get: async () => JSON.stringify(SPLIT) }
};
const req = (path, body) => new Request('https://paiement.sh-developpement.fr' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const availCal = () => [d(10), d(11), d(12), d(13)].map(date => ({ date, isAvailable: 1, status: 'available', price: 200, minimumStay: 1 }));
const customer = { name: 'Jean Dupont', email: 'jean@example.fr', phone: '0600000000' };

// =====================================================================
console.log('\nTest 1 — création du paiement (prix recalculé + SPLIT 20 %)');
CALENDAR = availCal(); // 3 nuits × 200 = 600 ; ×1,05 = 630 ; +300 ménage = 930 €
{
  const res = await worker.fetch(req('/create-payment', { listingId: 470939, startDate, endDate, guests: 2, customer }), ENV);
  const j = await res.json();
  ok(res.status === 200, 'HTTP 200');
  ok(j.payment_url === 'https://checkout.stripe.com/c/pay/cs_test', 'renvoie l\'URL Stripe Checkout');
  ok(j.amount === 930, 'montant recalculé serveur = 930 € (3 nuits×200×1,05 + 300 ménage)');
  ok(LAST_SESSION['line_items[0][price_data][unit_amount]'] === '93000', 'Stripe reçoit 93 000 centimes');
  ok(LAST_SESSION['payment_intent_data[transfer_data][destination]'] === 'acct_OWNER1', 'part location → compte Stripe du PROPRIÉTAIRE');
  ok(LAST_SESSION['payment_intent_data[application_fee_amount]'] === '45000',
    'SH garde 450 € (120 commission + 30 frais dossier + 300 ménage) → proprio 480 €');
  ok(LAST_SESSION['payment_method_options[card][request_three_d_secure]'] === 'any', '3-D Secure demandé');
  ok(LAST_SESSION['metadata[listingId]'] === '470939' && LAST_SESSION['metadata[startDate]'] === startDate, 'métadonnées jointes');
  ok(LAST_SESSION.success_url.includes('/merci-reservation.html'), 'retour → page de confirmation dédiée');
}

console.log('\nTest 2 — commission spéciale 2 % (type Beguet)');
{
  const res = await worker.fetch(req('/create-payment', { listingId: 555555, startDate, endDate, guests: 2, customer }), ENV);
  ok(res.status === 200, 'HTTP 200');
  // proprio = 600×0,98 = 588 € → SH = 930 − 588 = 342 €
  ok(LAST_SESSION['payment_intent_data[application_fee_amount]'] === '34200', 'SH garde 342 € (12 commission + 30 + 300)');
  ok(LAST_SESSION['payment_intent_data[transfer_data][destination]'] === 'acct_BEGUET', 'bon compte propriétaire');
}

console.log('\nTest 3 — propriétaire NON enrôlé → refus (conformité), pas de paiement');
{
  LAST_SESSION = null;
  const res = await worker.fetch(req('/create-payment', { listingId: 111111, startDate, endDate, guests: 2, customer }), ENV);
  const j = await res.json();
  ok(res.status === 409 && j.error === 'owner_not_onboarded', '409 owner_not_onboarded');
  ok(LAST_SESSION === null, 'aucune session Stripe créée');
}

console.log('\nTest 4 — webhook payé → réservation créée dans Hostaway');
{
  CALENDAR = availCal();
  await worker.fetch(req('/create-payment', { listingId: 470939, startDate, endDate, guests: 2, customer }), ENV);
  SESSION_STATE = 'paid'; RESERVATION = null;
  const res = await worker.fetch(req('/webhook', { type: 'checkout.session.completed', data: { object: { id: 'cs_test' } } }), ENV);
  const j = await res.json();
  ok(res.status === 200 && j.ok === true, 'webhook traité (200)');
  ok(RESERVATION && RESERVATION.listingMapId === 470939, 'réservation Hostaway sur le bon logement');
  ok(RESERVATION.arrivalDate === startDate && RESERVATION.departureDate === endDate, 'dates correctes');
  ok(RESERVATION.numberOfGuests === 2, 'nombre de voyageurs correct');
  ok(RESERVATION.totalPrice === 930 && RESERVATION.isPaid === 1, 'montant payé reporté + marqué payé');
  ok(RESERVATION.guestName === 'Jean Dupont', 'nom du voyageur repris');
}

console.log('\nTest 5 — webhook NON payé → on ne crée rien');
{
  SESSION_STATE = 'unpaid'; RESERVATION = null;
  const res = await worker.fetch(req('/webhook', { type: 'checkout.session.completed', data: { object: { id: 'cs_test' } } }), ENV);
  const j = await res.json();
  ok(res.status === 200 && j.ignored === 'not_paid', 'paiement non abouti ignoré');
  ok(RESERVATION === null, 'aucune réservation créée si non payé');
}

console.log('\nTest 6 — autres événements webhook ignorés proprement');
{
  RESERVATION = null;
  const res = await worker.fetch(req('/webhook', { type: 'payment_intent.created', data: { object: { id: 'pi_x' } } }), ENV);
  const j = await res.json();
  ok(res.status === 200 && j.ignored === 'payment_intent.created', 'événement non pertinent ignoré');
}

console.log('\nTest 7 — dates indisponibles → 409, pas de paiement');
{
  LAST_SESSION = null;
  CALENDAR = availCal(); CALENDAR[1] = { ...CALENDAR[1], isAvailable: 0, status: 'reserved' };
  const res = await worker.fetch(req('/create-payment', { listingId: 470939, startDate, endDate, guests: 2, customer }), ENV);
  ok(res.status === 409, 'HTTP 409 (indisponible)');
  ok(LAST_SESSION === null, 'aucun paiement créé si dates prises');
}

console.log(`\n${fail === 0 ? '🎉 TOUT PASSE' : '⚠️ ÉCHECS'} — ${pass} réussis, ${fail} échoués\n`);
process.exit(fail === 0 ? 0 : 1);
