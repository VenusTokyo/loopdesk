/* Landing page interactions. No framework, no build step. */
(function () {
  'use strict';

  function wireTabs(selector, onSelect) {
    var items = Array.prototype.slice.call(document.querySelectorAll(selector));
    items.forEach(function (btn, index) {
      btn.addEventListener('click', function () {
        items.forEach(function (other, j) {
          other.setAttribute('aria-selected', String(other === btn));
          other.classList.toggle('done', j < index);
        });
        onSelect(btn, index);
      });
      // Arrow keys move between tabs, as a tablist should.
      btn.addEventListener('keydown', function (e) {
        var delta = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
        if (!delta) return;
        e.preventDefault();
        var next = items[(index + delta + items.length) % items.length];
        next.focus();
        next.click();
      });
    });
  }

  wireTabs('.tab', function (btn) {
    ['p1', 'p2', 'p3'].forEach(function (id) {
      document.getElementById(id).hidden = id !== btn.dataset.p;
    });
  });

  var LOOP = [
    '<pre><span class="k3">POST /webhooks/github</span>\n{ <span class="k1">"action"</span>: <span class="k2">"closed"</span>,\n  <span class="k1">"issue"</span>: { <span class="k1">"number"</span>: 42 } }</pre>' +
      '<p class="note">The delivery signature is verified before anything is read.</p>',

    '<div class="q">Draft ready. Stack traces removed, rewritten for users.</div>' +
      '<div class="ans">- Update to v2.4.1 or later.<br>- Reload the Analytics page.</div>' +
      '<p style="margin-top:20px"><span class="chip">status: draft</span> <span class="chip">not visible to users</span></p>',

    '<div class="ans"><b>Approved by a developer.</b> The draft was edited once, then published to the knowledge base and embedded for retrieval.</div>' +
      '<p style="margin-top:20px"><span class="chip y">published</span> <span class="chip">from issue #42</span></p>',

    '<pre><span class="k3">$ git log -1 --stat</span>\ndocs(solutions): publish fix for #42\n\n <span class="k2">solutions/analytics/analytics-date-range-resets.md</span> | 15 +++++</pre>',

    '<div class="q">The date filter will not stay on 30 days.</div>' +
      '<div class="ans"><b>Update to v2.4.1 or later, then reload the page.</b></div>' +
      '<p style="margin-top:20px"><span class="chip y">cited solution</span> <span class="ok">ticket deflected</span></p>',
  ];

  var panel = document.getElementById('lp');
  function showStep(i) { panel.innerHTML = LOOP[i]; }
  showStep(0);
  wireTabs('.step', function (_, i) { showStep(i); });

  // Copy buttons. Clipboard access can be refused; say so rather than lying.
  Array.prototype.forEach.call(document.querySelectorAll('[data-copy]'), function (el) {
    el.addEventListener('click', function () {
      var original = el.textContent;
      navigator.clipboard.writeText(el.dataset.copy).then(
        function () { el.textContent = 'Copied'; },
        function () { el.textContent = 'Press Ctrl+C'; }
      );
      setTimeout(function () { el.textContent = original; }, 1400);
    });
  });

  var approve = document.getElementById('approve');
  approve.addEventListener('click', function () {
    approve.textContent = 'Committed';
    document.querySelector('.time span:last-child').classList.add('on');
  });
})();
