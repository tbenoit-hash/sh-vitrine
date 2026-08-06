/* SH Développement : sélecteur de langue (FR, EN, ES, IT, PT, DE)
   Pastille flottante en bas à gauche, présente sur toutes les pages.
   La traduction s'appuie sur Google Translate (cookie googtrans) : le script
   Google n'est chargé que si une langue autre que le français est choisie. */
(function () {
  'use strict';
  var LANGS = [
    { code: 'fr', flag: '🇫🇷', name: 'Français' },
    { code: 'en', flag: '🇬🇧', name: 'English' },
    { code: 'es', flag: '🇪🇸', name: 'Español' },
    { code: 'it', flag: '🇮🇹', name: 'Italiano' },
    { code: 'pt', flag: '🇵🇹', name: 'Português' },
    { code: 'de', flag: '🇩🇪', name: 'Deutsch' }
  ];

  function getCookie(n) {
    var m = document.cookie.match(new RegExp('(?:^|; )' + n + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
  }
  function current() {
    var v = getCookie('googtrans'); // format /fr/en
    var c = v ? v.split('/')[2] : 'fr';
    for (var i = 0; i < LANGS.length; i++) if (LANGS[i].code === c) return LANGS[i];
    return LANGS[0];
  }
  function setLang(code) {
    var host = location.hostname;
    var doms = [host];
    var parts = host.split('.');
    if (parts.length > 2) doms.push(parts.slice(-2).join('.'));
    if (host.indexOf('www.') !== 0) doms.push('.' + host); else doms.push('.' + parts.slice(1).join('.'));
    doms.forEach(function (d) {
      if (code === 'fr') {
        document.cookie = 'googtrans=; path=/; domain=' + d + '; expires=Thu, 01 Jan 1970 00:00:00 GMT';
        document.cookie = 'googtrans=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
      } else {
        document.cookie = 'googtrans=/fr/' + code + '; path=/; domain=' + d;
        document.cookie = 'googtrans=/fr/' + code + '; path=/';
      }
    });
    location.reload();
  }

  /* Charge Google Translate seulement si une autre langue est active */
  function bootTranslate() {
    if (current().code === 'fr') return;
    var holder = document.createElement('div');
    holder.id = 'gt_holder';
    holder.className = 'notranslate';
    holder.setAttribute('aria-hidden', 'true');
    document.body.appendChild(holder);
    window.googleTranslateElementInit = function () {
      new window.google.translate.TranslateElement({
        pageLanguage: 'fr',
        includedLanguages: 'en,es,it,pt,de',
        autoDisplay: false
      }, 'gt_holder');
    };
    var s = document.createElement('script');
    s.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    s.defer = true;
    document.body.appendChild(s);
  }

  function buildUI() {
    var cur = current();
    var css = document.createElement('style');
    css.textContent =
      '#sh-lang{position:fixed;left:14px;bottom:14px;z-index:70;font-family:Figtree,Inter,system-ui,sans-serif}' +
      '#sh-lang-btn{display:inline-flex;align-items:center;gap:7px;background:#FBF8F3;color:#2E2410;border:1px solid #ecdbc0;border-radius:999px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 10px 30px -8px rgba(46,36,16,.35)}' +
      '#sh-lang-btn:hover{background:#f5eee2}' +
      '#sh-lang-menu{position:absolute;left:0;bottom:calc(100% + 8px);min-width:170px;background:#FBF8F3;border:1px solid #ecdbc0;border-radius:16px;box-shadow:0 22px 55px -14px rgba(46,36,16,.4);padding:6px;display:none}' +
      '#sh-lang.open #sh-lang-menu{display:block}' +
      '.sh-lang-opt{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:none;border:0;border-radius:10px;padding:9px 11px;font-size:13px;font-weight:500;color:#2E2410;cursor:pointer}' +
      '.sh-lang-opt:hover{background:#f1e7d4}' +
      '.sh-lang-opt[aria-current="true"]{font-weight:700;background:#f5eee2}' +
      /* masque la bannière et l’infobulle Google Translate */
      'body{top:0 !important}' +
      '#gt_holder,.goog-te-banner-frame,.skiptranslate iframe,#goog-gt-tt,.goog-te-balloon-frame,.VIpgJd-ZVi9od-aZ2wEe-wOHMyf{display:none !important}' +
      'font[style]{background:none !important;box-shadow:none !important}';
    document.head.appendChild(css);

    var wrap = document.createElement('div');
    wrap.id = 'sh-lang';
    wrap.className = 'notranslate';
    var opts = '';
    LANGS.forEach(function (l) {
      opts += '<button type="button" class="sh-lang-opt" data-lang="' + l.code + '" aria-current="' + (l.code === cur.code) + '"><span>' + l.flag + '</span><span>' + l.name + '</span></button>';
    });
    wrap.innerHTML =
      '<button type="button" id="sh-lang-btn" aria-haspopup="true" aria-expanded="false" aria-label="Choisir la langue">' +
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>' +
      '<span>' + cur.code.toUpperCase() + '</span></button>' +
      '<div id="sh-lang-menu" role="menu" aria-label="Langues">' + opts + '</div>';
    document.body.appendChild(wrap);

    var btn = document.getElementById('sh-lang-btn');
    btn.addEventListener('click', function () {
      var open = wrap.classList.toggle('open');
      btn.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', function (e) {
      if (!wrap.contains(e.target)) { wrap.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
    });
    wrap.querySelectorAll('.sh-lang-opt').forEach(function (o) {
      o.addEventListener('click', function () { setLang(o.getAttribute('data-lang')); });
    });
  }

  function init() { buildUI(); bootTranslate(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
