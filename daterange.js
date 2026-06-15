/* SH Développement — sélecteur de plage de dates maison (brun/or, façon Airbnb)
   Remplace les <input type="date"> moches du navigateur.
   Convention de balisage dans la page :
     <div data-rangepicker>
       <button data-dr-trigger="in"> … <span data-dr-disp-in data-empty="Quand ?"></span></button>
       <button data-dr-trigger="out"> … <span data-dr-disp-out data-empty="Quand ?"></span></button>
       <input type="hidden" data-dr-in name|id=…>
       <input type="hidden" data-dr-out name|id=…>
     </div>
   Les <input> cachés reçoivent la valeur YYYY-MM-DD et émettent un événement "change"
   (compatibles avec le code existant qui lit getElementById('d-in').value, etc.). */
(function () {
  'use strict';
  if (window.__shDateRange) return; window.__shDateRange = true;

  var MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
  var DOW = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
  var DAY = 86400000;

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function parseISO(s) { if (!s) return null; var p = String(s).split('-'); if (p.length !== 3) return null; var d = new Date(+p[0], +p[1] - 1, +p[2]); return isNaN(d) ? null : d; }
  function fmtDisp(d) { return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + '/' + d.getFullYear(); }
  function startOfToday() { var n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }
  function sameDay(a, b) { return a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate(); }
  function firstOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }

  var css = ''
    + '.dr-pop{position:fixed;z-index:60;width:328px;max-width:calc(100vw - 16px);background:#FBF8F3;border:1px solid #ecdbc0;border-radius:20px;box-shadow:0 22px 55px -14px rgba(46,36,16,.4);padding:16px;font-family:Inter,system-ui,sans-serif;opacity:0;transform:translateY(-6px);pointer-events:none;transition:opacity .14s ease,transform .14s ease}'
    + '.dr-pop.dr-show{opacity:1;transform:none;pointer-events:auto}'
    + '.dr-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}'
    + '.dr-title{font-family:"Cormorant Garamond",Georgia,serif;font-weight:700;font-size:21px;color:#2E2410;text-transform:capitalize}'
    + '.dr-nav{width:34px;height:34px;border-radius:9999px;border:1px solid #ecdbc0;background:#fff;color:#5c4636;font-size:19px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s,border-color .15s}'
    + '.dr-nav:hover:not(:disabled){background:#F1E9DC;border-color:#8A5E1A;color:#2E2410}'
    + '.dr-nav:disabled{opacity:.3;cursor:default}'
    + '.dr-dow{display:grid;grid-template-columns:repeat(7,1fr);margin-bottom:2px}'
    + '.dr-dow span{text-align:center;font-size:11px;font-weight:700;color:#8A5E1A;padding:5px 0}'
    + '.dr-grid{display:grid;grid-template-columns:repeat(7,1fr)}'
    + '.dr-cell{position:relative;aspect-ratio:1;border:0;background:transparent;color:#2E2410;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;font-family:inherit}'
    + '.dr-cell:hover:not(:disabled):not(.dr-sel){background:#F1E9DC;border-radius:9999px}'
    + '.dr-blank{visibility:hidden}'
    + '.dr-past{color:#c4b79f;cursor:default}'
    + '.dr-range{background:#F4ECDD}'
    + '.dr-sel{background:#E0AE2C;color:#2E2410;font-weight:700;border-radius:9999px;z-index:1}'
    + '.dr-sel-in{border-top-left-radius:9999px;border-bottom-left-radius:9999px}'
    + '.dr-sel-out{border-top-right-radius:9999px;border-bottom-right-radius:9999px}'
    + '.dr-foot{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:10px;border-top:1px solid #ecdbc0}'
    + '.dr-hint{font-size:12px;color:#6B605C}'
    + '.dr-clear{background:transparent;border:0;color:#8A5E1A;font-weight:700;font-size:13px;cursor:pointer;text-decoration:underline;text-underline-offset:2px;font-family:inherit}'
    + '.dr-clear:hover{color:#2E2410}';
  var styleEl = document.createElement('style'); styleEl.textContent = css; document.head.appendChild(styleEl);

  function initOne(root) {
    var trigIn = root.querySelector('[data-dr-trigger="in"]');
    var trigOut = root.querySelector('[data-dr-trigger="out"]');
    var dispIn = root.querySelector('[data-dr-disp-in]');
    var dispOut = root.querySelector('[data-dr-disp-out]');
    var inEl = root.querySelector('[data-dr-in]');
    var outEl = root.querySelector('[data-dr-out]');
    if (!inEl || !outEl) return;

    var selIn = parseISO(inEl.value);
    var selOut = parseISO(outEl.value);
    var view = firstOfMonth(selIn || startOfToday());
    var stage = 'in';
    var pop = null, open = false, curAnchor = null, suppress = false;

    function updateDisp(el, date) {
      if (!el) return;
      if (date) { el.textContent = fmtDisp(date); el.style.color = '#2E2410'; el.style.fontWeight = '600'; }
      else { el.textContent = el.getAttribute('data-empty') || 'Quand ?'; el.style.color = '#6B605C'; el.style.fontWeight = '400'; }
    }
    function paintDisp() { updateDisp(dispIn, selIn); updateDisp(dispOut, selOut); }

    // écrit dans les inputs cachés + notifie le reste de la page
    function commit() {
      suppress = true;
      inEl.value = selIn ? iso(selIn) : '';
      outEl.value = selOut ? iso(selOut) : '';
      [inEl, outEl].forEach(function (x) {
        x.dispatchEvent(new Event('input', { bubbles: true }));
        x.dispatchEvent(new Event('change', { bubbles: true }));
      });
      suppress = false;
      paintDisp();
    }
    // relit les inputs s'ils sont modifiés de l'extérieur (ex. params d'URL sur le catalogue)
    function readExternal() {
      if (suppress) return;
      selIn = parseISO(inEl.value); selOut = parseISO(outEl.value);
      if (selIn) view = firstOfMonth(selIn);
      paintDisp(); if (pop) renderPop();
    }
    inEl.addEventListener('change', readExternal);
    outEl.addEventListener('change', readExternal);

    function buildPop() {
      pop = document.createElement('div');
      pop.className = 'dr-pop';
      pop.setAttribute('role', 'dialog');
      pop.setAttribute('aria-label', 'Choix des dates');
      pop.innerHTML =
        '<div class="dr-head">' +
        '<button type="button" class="dr-nav" data-dr-prev aria-label="Mois précédent">‹</button>' +
        '<div class="dr-title" data-dr-title></div>' +
        '<button type="button" class="dr-nav" data-dr-next aria-label="Mois suivant">›</button>' +
        '</div>' +
        '<div class="dr-dow">' + DOW.map(function (d) { return '<span>' + d + '</span>'; }).join('') + '</div>' +
        '<div class="dr-grid" data-dr-grid></div>' +
        '<div class="dr-foot"><span class="dr-hint" data-dr-hint></span><button type="button" class="dr-clear" data-dr-clear>Effacer</button></div>';
      document.body.appendChild(pop);
      pop.addEventListener('click', onPopClick);
    }

    function renderPop() {
      if (!pop) return;
      pop.querySelector('[data-dr-title]').textContent = MONTHS[view.getMonth()] + ' ' + view.getFullYear();
      var y = view.getFullYear(), m = view.getMonth();
      var startDow = (new Date(y, m, 1).getDay() + 6) % 7; // lundi = 0
      var nbDays = new Date(y, m + 1, 0).getDate();
      var today = startOfToday();
      var html = '';
      for (var i = 0; i < startDow; i++) html += '<span class="dr-cell dr-blank"></span>';
      for (var d = 1; d <= nbDays; d++) {
        var date = new Date(y, m, d);
        var past = date < today;
        var isIn = sameDay(date, selIn), isOut = sameDay(date, selOut);
        var inRange = selIn && selOut && date > selIn && date < selOut;
        var cls = 'dr-cell';
        if (past) cls += ' dr-past';
        if (inRange) cls += ' dr-range';
        if (isIn || isOut) { cls += ' dr-sel'; if (selOut && isIn) cls += ' dr-sel-in'; if (selIn && isOut) cls += ' dr-sel-out'; }
        html += '<button type="button" class="' + cls + '" data-d="' + iso(date) + '"' + (past ? ' disabled' : '') + '>' + d + '</button>';
      }
      pop.querySelector('[data-dr-grid]').innerHTML = html;
      pop.querySelector('[data-dr-prev]').disabled = (firstOfMonth(view) <= firstOfMonth(today));
      var hint = pop.querySelector('[data-dr-hint]');
      if (selIn && selOut) { var n = Math.round((selOut - selIn) / DAY); hint.textContent = n + ' nuit' + (n > 1 ? 's' : ''); }
      else if (selIn) hint.textContent = 'Choisissez la date de départ';
      else hint.textContent = 'Choisissez la date d’arrivée';
    }

    function onPopClick(e) {
      var t = e.target;
      if (t.closest('[data-dr-prev]')) { if (!t.closest('[data-dr-prev]').disabled) { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); renderPop(); } return; }
      if (t.closest('[data-dr-next]')) { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); renderPop(); return; }
      if (t.closest('[data-dr-clear]')) { selIn = null; selOut = null; stage = 'in'; commit(); renderPop(); return; }
      var cell = t.closest('[data-d]');
      if (cell && !cell.disabled) {
        var date = parseISO(cell.getAttribute('data-d'));
        if (!selIn || selOut || date <= selIn) { selIn = date; selOut = null; stage = 'out'; }
        else { selOut = date; stage = 'in'; }
        commit(); renderPop();
        if (selIn && selOut) setTimeout(closePop, 160);
      }
    }

    function position() {
      if (!curAnchor) return;
      var r = curAnchor.getBoundingClientRect();
      var pw = pop.offsetWidth || 328;
      var left = r.left;
      if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
      if (left < 8) left = 8;
      var top = r.bottom + 8;
      var ph = pop.offsetHeight || 360;
      if (top + ph > window.innerHeight - 8 && r.top - ph - 8 > 8) top = r.top - ph - 8;
      pop.style.left = left + 'px'; pop.style.top = top + 'px';
    }
    function onReposition() { if (open) position(); }
    function onOutside(e) { if (pop.contains(e.target) || root.contains(e.target)) return; closePop(); }
    function onKey(e) { if (e.key === 'Escape') closePop(); }

    function openPop(which, anchor) {
      if (!pop) buildPop();
      stage = which || 'in';
      view = firstOfMonth(selIn || startOfToday());
      curAnchor = anchor;
      renderPop();
      pop.classList.add('dr-show'); open = true;
      position();
      document.addEventListener('mousedown', onOutside, true);
      document.addEventListener('keydown', onKey, true);
      window.addEventListener('resize', onReposition, true);
      window.addEventListener('scroll', onReposition, true);
    }
    function closePop() {
      if (!pop || !open) return;
      pop.classList.remove('dr-show'); open = false;
      document.removeEventListener('mousedown', onOutside, true);
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('resize', onReposition, true);
      window.removeEventListener('scroll', onReposition, true);
    }
    function toggle(which, anchor) { if (open && curAnchor === anchor) closePop(); else openPop(which, anchor); }

    if (trigIn) trigIn.addEventListener('click', function (e) { e.preventDefault(); toggle('in', trigIn); });
    if (trigOut) trigOut.addEventListener('click', function (e) { e.preventDefault(); toggle(selIn ? 'out' : 'in', trigOut); });

    paintDisp();
  }

  function initAll() { document.querySelectorAll('[data-rangepicker]').forEach(initOne); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
})();
