/* SH Développement — autocomplétion du champ « Destination » (façon Airbnb)
   Convention de balisage :
     <label data-destpicker> … <input data-dest-input id|name=…> </label>
   Liste des villes lue dans cities.json ({cities:[{name,n}]}, généré par build_data.py).
   À la sélection : écrit la ville dans l'input + émet 'input'/'change' (compatible
   avec le filtrage existant du catalogue et la soumission du formulaire d'accueil). */
(function () {
  'use strict';
  if (window.__shDestPicker) return; window.__shDestPicker = true;

  var citiesPromise = null;
  function loadCities() {
    if (!citiesPromise) citiesPromise = fetch('cities.json')
      .then(function (r) { return r.ok ? r.json() : { cities: [] }; })
      .then(function (d) { return (d && d.cities) || []; })
      .catch(function () { return []; });
    return citiesPromise;
  }
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]; }); }

  var PIN = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';
  var GLOBE = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg>';

  var css = ''
    + '.dp-pop{position:fixed;z-index:60;width:328px;max-width:calc(100vw - 16px);max-height:344px;overflow-y:auto;background:#FBF8F3;border:1px solid #ecdbc0;border-radius:18px;box-shadow:0 22px 55px -14px rgba(46,36,16,.4);padding:8px;font-family:Figtree,-apple-system,"Helvetica Neue",Arial,sans-serif;opacity:0;transform:translateY(-6px);pointer-events:none;transition:opacity .14s ease,transform .14s ease}'
    + '.dp-pop.dp-show{opacity:1;transform:none;pointer-events:auto}'
    + '.dp-head{font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#8A5E1A;padding:8px 10px 5px}'
    + '.dp-row{display:flex;align-items:center;gap:11px;width:100%;text-align:left;border:0;background:transparent;border-radius:12px;padding:8px 10px;cursor:pointer;color:#2E2410;font-family:inherit;font-size:14px}'
    + '.dp-row:hover,.dp-row.dp-active{background:#F1E9DC}'
    + '.dp-ic{width:34px;height:34px;border-radius:9999px;background:#F1E9DC;color:#8A5E1A;display:flex;align-items:center;justify-content:center;flex:none}'
    + '.dp-row:hover .dp-ic,.dp-row.dp-active .dp-ic{background:#E7D7BC}'
    + '.dp-main{display:flex;flex-direction:column;min-width:0}'
    + '.dp-name{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
    + '.dp-sub{font-size:12px;color:#6B605C}'
    + '.dp-empty{padding:12px;color:#6B605C;font-size:13px;line-height:1.5}';
  var styleEl = document.createElement('style'); styleEl.textContent = css; document.head.appendChild(styleEl);

  function initOne(root) {
    var input = root.querySelector('[data-dest-input]');
    if (!input) return;
    input.setAttribute('autocomplete', 'off');
    var pop = null, open = false, cities = [], active = -1, rows = [];

    function buildPop() {
      pop = document.createElement('div');
      pop.className = 'dp-pop';
      pop.setAttribute('role', 'listbox');
      document.body.appendChild(pop);
      pop.addEventListener('mousedown', function (e) { e.preventDefault(); }); // ne pas voler le focus de l'input
      pop.addEventListener('click', function (e) {
        var r = e.target.closest('[data-city]');
        if (r) select(r.getAttribute('data-city'));
      });
    }

    function render() {
      var q = norm(input.value);
      var list = q ? cities.filter(function (c) { return norm(c.name).indexOf(q) !== -1; }) : cities.slice();
      var html = '<div class="dp-head">' + (q ? 'Villes' : 'Destinations populaires') + '</div>';
      html += '<button type="button" class="dp-row" data-city=""><span class="dp-ic">' + GLOBE + '</span><span class="dp-main"><span class="dp-name">Partout en Bourgogne</span><span class="dp-sub">Tous nos logements</span></span></button>';
      list.forEach(function (c) {
        html += '<button type="button" class="dp-row" data-city="' + esc(c.name) + '"><span class="dp-ic">' + PIN + '</span><span class="dp-main"><span class="dp-name">' + esc(c.name) + '</span><span class="dp-sub">' + c.n + ' logement' + (c.n > 1 ? 's' : '') + '</span></span></button>';
      });
      if (q && !list.length) html += '<div class="dp-empty">Aucune ville ne correspond. La recherche portera sur «&nbsp;' + esc(input.value) + '&nbsp;».</div>';
      pop.innerHTML = html;
      rows = [].slice.call(pop.querySelectorAll('[data-city]'));
      active = -1;
    }

    function position() {
      var r = root.getBoundingClientRect();
      var pw = pop.offsetWidth || 328;
      var left = r.left; if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8; if (left < 8) left = 8;
      pop.style.left = left + 'px'; pop.style.top = (r.bottom + 8) + 'px';
    }
    function onReposition() { if (open) position(); }
    function onOutside(e) { if (pop.contains(e.target) || root.contains(e.target)) return; close(); }

    function openPop() {
      if (open) return;
      if (!pop) buildPop();
      loadCities().then(function (c) {
        cities = c; render();
        pop.classList.add('dp-show'); open = true; position();
        document.addEventListener('mousedown', onOutside, true);
        window.addEventListener('resize', onReposition, true);
        window.addEventListener('scroll', onReposition, true);
      });
    }
    function close() {
      if (!pop || !open) return;
      pop.classList.remove('dp-show'); open = false; active = -1;
      document.removeEventListener('mousedown', onOutside, true);
      window.removeEventListener('resize', onReposition, true);
      window.removeEventListener('scroll', onReposition, true);
    }
    function select(name) {
      input.value = name;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      close();
    }
    function setActive(i) {
      if (!rows.length) return;
      active = (i + rows.length) % rows.length;
      rows.forEach(function (r, k) { r.classList.toggle('dp-active', k === active); });
      if (rows[active]) rows[active].scrollIntoView({ block: 'nearest' });
    }

    input.addEventListener('focus', openPop);
    input.addEventListener('click', openPop);
    input.addEventListener('input', function () { if (!open) openPop(); else render(); });
    input.addEventListener('keydown', function (e) {
      if (!open) { if (e.key === 'ArrowDown') openPop(); return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
      else if (e.key === 'Enter') { if (active >= 0 && rows[active]) { e.preventDefault(); select(rows[active].getAttribute('data-city')); } }
      else if (e.key === 'Escape') { close(); }
    });
  }

  function initAll() { document.querySelectorAll('[data-destpicker]').forEach(initOne); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
})();
