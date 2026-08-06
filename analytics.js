/* SH Développement : mesure d'audience Google Analytics 4 (G-BVC1TN3D47)
   Conformité CNIL : GA n'est chargé qu'après consentement explicite.
   Le choix est mémorisé 6 mois dans localStorage (sh_consent). */
(function () {
  'use strict';
  var GA_ID = 'G-BVC1TN3D47';
  var KEY = 'sh_consent';
  var SIX_MONTHS = 182 * 24 * 3600 * 1000;

  function readChoice() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return null;
      var c = JSON.parse(raw);
      if (!c.at || Date.now() - c.at > SIX_MONTHS) { localStorage.removeItem(KEY); return null; }
      return c.ga; // 'yes' | 'no'
    } catch (e) { return null; }
  }
  function saveChoice(v) {
    try { localStorage.setItem(KEY, JSON.stringify({ ga: v, at: Date.now() })); } catch (e) {}
  }

  function loadGA() {
    if (window.dataLayer && window.gtag) return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', GA_ID, { anonymize_ip: true });
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(s);
  }

  function banner() {
    var css = document.createElement('style');
    css.textContent =
      '#sh-consent{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:80;width:calc(100vw - 20px);max-width:520px;background:#FBF8F3;color:#2E2410;border:1px solid #ecdbc0;border-radius:18px;box-shadow:0 22px 55px -14px rgba(46,36,16,.45);padding:16px 18px;font-family:Figtree,Inter,system-ui,sans-serif;font-size:13px;line-height:1.55}' +
      '#sh-consent p{margin:0 0 12px}' +
      '#sh-consent a{color:#8A5E1A;text-decoration:underline}' +
      '#sh-consent .row{display:flex;gap:8px;flex-wrap:wrap}' +
      '#sh-consent button{border:0;border-radius:999px;padding:9px 18px;font-size:13px;font-weight:700;cursor:pointer}' +
      '#sh-consent .ok{background:#E0AE2C;color:#2E2410}' +
      '#sh-consent .ok:hover{background:#8A5E1A;color:#FBF8F3}' +
      '#sh-consent .no{background:none;color:#6B605C;border:1px solid #ecdbc0}' +
      '#sh-consent .no:hover{border-color:#8A5E1A;color:#2E2410}';
    document.head.appendChild(css);
    var d = document.createElement('div');
    d.id = 'sh-consent';
    d.className = 'notranslate';
    d.setAttribute('role', 'dialog');
    d.setAttribute('aria-label', 'Consentement à la mesure d\'audience');
    d.innerHTML =
      '<p>Nous utilisons Google Analytics pour mesurer la fréquentation du site et améliorer nos services. Vos données restent anonymisées. <a href="/confidentialite.html">En savoir plus</a></p>' +
      '<div class="row"><button type="button" class="ok">Accepter</button><button type="button" class="no">Continuer sans accepter</button></div>';
    document.body.appendChild(d);
    d.querySelector('.ok').addEventListener('click', function () { saveChoice('yes'); d.remove(); loadGA(); });
    d.querySelector('.no').addEventListener('click', function () { saveChoice('no'); d.remove(); });
  }

  function init() {
    var c = readChoice();
    if (c === 'yes') loadGA();
    else if (c === null) banner();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
