/**
 * Widget UI. Everything lives in a Shadow DOM so the host app's CSS cannot
 * reach in and ours cannot leak out.
 */
const LD_STYLES = `
:host { all: initial; }
*, *::before, *::after { box-sizing: border-box; }
.root {
  --canvas:#0a0a0a; --card:#1a1a1a; --elev:#242424; --hair:#2a2a2a; --hair2:#3a3a3a;
  --y:#faff69; --y2:#e6eb52; --ink:#fff; --body:#ccc; --muted:#888;
  --green:#22c55e; --rose:#ef4444;
  --sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
  font: 400 14px/1.55 var(--sans);
  color: var(--body);
  position: fixed; inset: auto 20px 20px auto; z-index: 2147483000;
  color-scheme: dark;
}
.fab {
  width: 52px; height: 52px; border-radius: 26px; border: 0; cursor: pointer;
  background: var(--y); color: #0a0a0a;
  box-shadow: 0 8px 28px rgba(0,0,0,.5);
  display: grid; place-items: center; transition: transform .15s ease;
}
.fab:hover { transform: translateY(-2px); background: var(--y2); }
.fab .mark {
  width: 20px; height: 20px; border: 3px solid #0a0a0a; border-radius: 50%;
  border-right-color: transparent; transform: rotate(-30deg);
}
.panel {
  position: fixed; right: 20px; bottom: 84px; width: 388px; max-width: calc(100vw - 32px);
  max-height: min(680px, calc(100vh - 120px));
  background: var(--card); border: 1px solid var(--hair); border-radius: 12px;
  box-shadow: 0 24px 60px rgba(0,0,0,.6);
  display: flex; flex-direction: column; overflow: hidden;
}
.hd { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--hair); }
.hd .mark { width: 18px; height: 18px; border: 3px solid var(--y); border-radius: 50%; border-right-color: transparent; transform: rotate(-30deg); flex: none; }
.hd h2 { margin: 0; font-size: 14px; font-weight: 600; color: var(--ink); flex: 1; letter-spacing: -.2px; }
.hd .sub { display: block; font: 400 12px var(--mono); color: var(--muted); margin-top: 2px; }
.x { border: 0; background: transparent; cursor: pointer; font-size: 20px; color: var(--muted); padding: 2px 6px; line-height: 1; }
.x:hover { color: var(--ink); }
.tabs { display: flex; gap: 4px; padding: 10px 12px 0; border-bottom: 1px solid var(--hair); }
.tab { border: 0; background: transparent; padding: 8px 12px; cursor: pointer; font: 500 13px var(--sans); color: var(--muted); border-radius: 8px 8px 0 0; }
.tab[aria-selected="true"] { background: var(--elev); color: var(--ink); }
.body { padding: 16px; overflow-y: auto; }
.muted { color: var(--muted); font-size: 13px; }
.card { border: 1px solid var(--hair); border-radius: 10px; padding: 14px; margin-bottom: 10px; background: var(--elev); }
.card h3 { margin: 0 0 6px; font-size: 13.5px; font-weight: 600; color: var(--ink); }
.card .steps { margin: 10px 0 0; padding-left: 18px; font-size: 13px; color: var(--body); }
.card .steps li { margin: 4px 0; }
.card code { font: 400 12px var(--mono); background: var(--canvas); padding: 1px 5px; border-radius: 4px; color: var(--y); }
.meta { display: flex; gap: 6px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.chip { font: 500 11px var(--mono); padding: 2px 9px; border-radius: 9999px; background: var(--card); border: 1px solid var(--hair2); color: var(--ink); }
.chip.y { background: var(--y); border-color: var(--y); color: #0a0a0a; }
.chip.ok { color: var(--green); border-color: var(--green); }
.chip.bad { color: var(--rose); border-color: var(--rose); }
.meter { position: relative; height: 4px; background: var(--hair2); border-radius: 2px; margin: 16px 0 26px; }
.meter i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--y); border-radius: 2px; }
.meter i.low { background: var(--muted); }
.meter s { position: absolute; top: -4px; width: 1px; height: 12px; background: var(--muted); }
.meter span { position: absolute; top: 13px; font: 400 10px var(--mono); color: var(--muted); transform: translateX(-50%); }
button.primary, button.ghost, button.sm {
  font: 600 14px var(--sans); cursor: pointer; border-radius: 8px; padding: 10px 14px; border: 1px solid transparent;
}
button.primary { background: var(--y); color: #0a0a0a; width: 100%; }
button.primary:hover { background: var(--y2); }
button.primary:disabled { background: var(--hair2); color: var(--muted); cursor: progress; }
button.ghost { background: var(--card); border-color: var(--hair2); color: var(--ink); width: 100%; }
button.ghost:hover { background: var(--elev); }
button.sm { padding: 6px 11px; font: 500 12px var(--sans); background: var(--card); border-color: var(--hair2); color: var(--body); }
button.sm:hover { color: var(--ink); }
button.sm.active { background: var(--y); color: #0a0a0a; border-color: var(--y); }
textarea, input[type=text] {
  width: 100%; font: 400 14px/1.5 var(--sans); padding: 10px 12px;
  border: 1px solid var(--hair); border-radius: 8px; resize: vertical;
  background: var(--elev); color: var(--ink);
}
textarea:focus, input[type=text]:focus { outline: 0; border-color: var(--y); }
textarea::placeholder { color: var(--muted); }
label { display: block; font: 600 12px var(--sans); margin: 14px 0 6px; color: var(--muted); }
.preview { width: 100%; border: 1px solid var(--hair); border-radius: 8px; display: block; }
.row { display: flex; gap: 8px; margin-top: 10px; }
.row > * { flex: 1; }
.banner { padding: 11px 13px; border-radius: 8px; font-size: 13px; margin-bottom: 14px; background: var(--elev); color: var(--body); border-left: 2px solid var(--hair2); }
.banner.ok { border-left-color: var(--y); color: var(--ink); }
.banner.warn { border-left-color: var(--y2); }
.banner.bad { border-left-color: var(--rose); }
.spin { display: inline-block; width: 13px; height: 13px; border: 2px solid var(--hair2); border-top-color: var(--y); border-radius: 50%; animation: s .7s linear infinite; vertical-align: -2px; }
@keyframes s { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation-duration: 2s; } .fab { transition: none; } }
.foot { padding: 9px 16px; border-top: 1px solid var(--hair); font: 400 11px var(--mono); color: var(--muted); display: flex; justify-content: space-between; gap: 8px; }
a { color: var(--y); }
button:focus-visible, .tab:focus-visible, a:focus-visible { outline: 2px solid var(--y); outline-offset: 2px; }
`;

function h(tag, attrs, children) {
  const el = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (v === null || v === undefined || v === false) return;
    if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  });
  (children || []).forEach((c) => c && el.appendChild(c));
  return el;
}

/** Deliberately tiny: bullets, bold and inline code only. No HTML passthrough. */
function renderSteps(md) {
  const lines = String(md || '')
    .split('\n')
    .map((l) => l.replace(/^\s*[-*]\s?/, '').trim())
    .filter(Boolean);
  const ul = h('ul', { class: 'steps' });
  lines.forEach((line) => {
    const li = document.createElement('li');
    line.split(/(`[^`]+`|\*\*[^*]+\*\*)/).forEach((part) => {
      if (/^`.+`$/.test(part)) li.appendChild(h('code', { text: part.slice(1, -1) }));
      else if (/^\*\*.+\*\*$/.test(part)) li.appendChild(h('strong', { text: part.slice(2, -2) }));
      else if (part) li.appendChild(document.createTextNode(part));
    });
    ul.appendChild(li);
  });
  return ul;
}

/** The confidence gate, drawn. The two ticks are the 0.4 and 0.7 thresholds,
 *  so the user can see why they got an answer or a ticket. */
function confidenceMeter(confidence, verdict) {
  const pct = Math.max(2, Math.round(confidence * 100));
  const bar = h('i', { class: verdict === 'unknown' ? 'low' : '' });
  bar.style.width = pct + '%';
  const tick = (left) => {
    const s = h('s', {});
    s.style.left = left;
    return s;
  };
  const label = (left, text) => {
    const el = h('span', { text });
    el.style.left = left;
    return el;
  };
  return h(
    'div',
    {
      class: 'meter',
      role: 'img',
      'aria-label': `Confidence ${confidence.toFixed(2)} of 1. Shows a fix at 0.7, hedges at 0.4.`,
    },
    [bar, tick('40%'), tick('70%'), label('40%', '0.4'), label('70%', '0.7')]
  );
}

class LoopDeskUI {
  constructor(config) {
    this.config = config;
    this.state = { tab: 'help', screenshot: null, analysis: null, rated: null, busy: false };

    this.hostEl = document.createElement('div');
    this.hostEl.setAttribute('data-loopdesk', 'root');
    this.shadow = this.hostEl.attachShadow({ mode: 'open' });
    this.shadow.appendChild(h('style', { text: LD_STYLES }));
    this.root = h('div', { class: 'root' });
    this.shadow.appendChild(this.root);
    document.body.appendChild(this.hostEl);

    this.fab = h(
      'button',
      {
        class: 'fab',
        title: 'Report a problem',
        'aria-label': 'Report a problem',
        onclick: () => this.toggle(),
      },
      [h('span', { class: 'mark' })]
    );
    this.root.appendChild(this.fab);
    this.panel = null;
  }

  toggle() {
    if (this.panel) return this.close();
    this.open();
  }

  close() {
    if (this.panel) this.panel.remove();
    this.panel = null;
  }

  open() {
    this.state = { tab: 'help', screenshot: null, analysis: null, rated: null, busy: false };
    this.panel = h('div', { class: 'panel', role: 'dialog', 'aria-label': 'LoopDesk help' });
    this.root.appendChild(this.panel);
    this.render();
    this.loadSuggestions();
  }

  setState(patch) {
    Object.assign(this.state, patch);
    this.render();
  }

  render() {
    if (!this.panel) return;
    const ctx = collectContext(this.config);
    this.panel.textContent = '';

    this.panel.appendChild(
      h('div', { class: 'hd' }, [
        h('span', { class: 'mark' }),
        h('h2', {}, [
          document.createTextNode('Need a hand?'),
          h('div', { class: 'sub', text: `${ctx.subproduct} - v${ctx.app_version}` }),
        ]),
        h('button', { class: 'x', text: '×', 'aria-label': 'Close', onclick: () => this.close() }),
      ])
    );

    this.panel.appendChild(
      h('div', { class: 'tabs' }, [
        this.tabBtn('help', 'Get help'),
        this.tabBtn('reports', 'My reports'),
      ])
    );

    const body = h('div', { class: 'body' });
    this.panel.appendChild(body);
    if (this.state.tab === 'reports') this.renderReports(body);
    else if (this.state.view === 'ticket') this.renderTicket(body, ctx);
    else if (this.state.analysis) this.renderResult(body, ctx);
    else this.renderHelp(body, ctx);

    this.panel.appendChild(
      h('div', { class: 'foot' }, [
        h('span', { text: 'LoopDesk' }),
        h('span', { text: this.state.analysis ? `via ${this.state.analysis.provider}` : 'screenshot stays on your infra' }),
      ])
    );
  }

  tabBtn(id, label) {
    return h('button', {
      class: 'tab',
      role: 'tab',
      'aria-selected': String(this.state.tab === id),
      text: label,
      onclick: () => this.setState({ tab: id }),
    });
  }

  // ---- view: help (layer 1 suggestions + capture) ----
  renderHelp(body, ctx) {
    body.appendChild(
      h('p', { class: 'muted', text: 'Known issues on this page:' })
    );

    const list = h('div', { 'data-suggestions': '' });
    body.appendChild(list);
    this.suggestionsEl = list;
    this.paintSuggestions();

    body.appendChild(h('label', { text: "What went wrong? (optional)" }));
    this.commentEl = h('textarea', {
      rows: '3',
      placeholder: 'I expected the filter to stay on 30 days',
    });
    if (this.state.comment) this.commentEl.value = this.state.comment;
    body.appendChild(this.commentEl);

    if (this.state.screenshot) {
      body.appendChild(h('label', { text: 'Screenshot (private fields redacted)' }));
      body.appendChild(h('img', { class: 'preview', src: this.state.screenshot, alt: 'Captured screenshot' }));
    }

    body.appendChild(
      h('div', { class: 'row' }, [
        h('button', {
          class: 'ghost',
          text: this.state.screenshot ? 'Retake screenshot' : 'Take screenshot',
          onclick: () => this.capture(),
        }),
      ])
    );
    body.appendChild(
      h('button', {
        class: 'primary',
        text: this.state.busy ? 'Analysing...' : 'Get a solution',
        disabled: this.state.busy,
        onclick: () => this.analyze(ctx),
      })
    );
    if (this.state.error) {
      body.appendChild(h('div', { class: 'banner bad', text: this.state.error }));
    }
  }

  paintSuggestions() {
    const el = this.suggestionsEl;
    if (!el) return;
    el.textContent = '';
    if (this.state.suggestions === undefined) {
      el.appendChild(h('p', { class: 'muted' }, [h('span', { class: 'spin' }), document.createTextNode(' loading...')]));
      return;
    }
    if (!this.state.suggestions.length) {
      el.appendChild(h('p', { class: 'muted', text: 'Nothing reported on this page yet.' }));
      return;
    }
    this.state.suggestions.forEach((s) => el.appendChild(this.solutionCard(s, false)));
  }

  async loadSuggestions() {
    const ctx = collectContext(this.config);
    try {
      const data = await apiGet(this.config, '/api/suggestions', {
        route: ctx.route,
        subproduct: ctx.subproduct,
        version: ctx.app_version,
      });
      this.state.suggestions = data;
    } catch (err) {
      console.warn('[loopdesk] suggestions failed', err);
      this.state.suggestions = [];
    }
    this.paintSuggestions();
  }

  async capture() {
    this.state.comment = this.commentEl ? this.commentEl.value : '';
    // Hide the whole widget host, not just the panel, so neither the button
    // nor the panel ends up in the user's screenshot.
    this.hostEl.style.display = 'none';
    let shot = null;
    try {
      shot = await captureWithFallback(null);
    } finally {
      this.hostEl.style.display = '';
    }
    this.setState({
      screenshot: shot,
      error: shot ? null : 'Could not capture the screen. You can still describe the problem.',
    });
  }

  // ---- view: result (layer 2 agent answer) ----
  async analyze(ctx) {
    const comment = this.commentEl ? this.commentEl.value : '';
    this.setState({ busy: true, comment, error: null });
    try {
      const analysis = await apiPost(this.config, '/api/analyze', {
        screenshot: this.state.screenshot,
        comment,
        context: ctx,
      });
      this.setState({ busy: false, analysis, rated: null });
    } catch (err) {
      console.error('[loopdesk] analyze failed', err);
      this.setState({ busy: false, error: 'The assistant is unreachable. You can still raise a ticket.' });
    }
  }

  renderResult(body, ctx) {
    const a = this.state.analysis;
    const cls = { confident: 'ok', maybe: 'warn', unknown: 'bad' }[a.verdict] || 'bad';
    body.appendChild(h('div', { class: `banner ${cls}`, text: a.message }));
    if (a.diagnosis) body.appendChild(h('p', { class: 'muted', text: a.diagnosis }));
    body.appendChild(confidenceMeter(a.confidence, a.verdict));

    a.solutions.forEach((s) => body.appendChild(this.solutionCard(s, true)));

    if (a.duplicate_of) {
      const d = a.duplicate_of;
      body.appendChild(
        h('div', { class: 'card' }, [
          h('h3', { text: `This looks like #${d.issue_number}` }),
          h('p', { class: 'muted', text: d.title }),
          h('button', {
            class: 'ghost',
            text: 'Me too - add me to that ticket',
            onclick: () => this.submitTicket(ctx, { me_too_issue_number: d.issue_number }),
          }),
        ])
      );
    }

    if (a.needs_ticket || a.verdict !== 'confident') {
      body.appendChild(
        h('button', {
          class: 'primary',
          text: 'Still not solved, raise a ticket',
          onclick: () => this.setState({ view: 'ticket' }),
        })
      );
    }
    body.appendChild(
      h('button', { class: 'ghost', text: 'Back', onclick: () => this.setState({ analysis: null, view: null }) })
    );
  }

  solutionCard(s, rateable) {
    const children = [
      h('h3', { text: s.title }),
      h('p', { class: 'muted', text: s.summary }),
      renderSteps(s.steps_md),
    ];

    const meta = h('div', { class: 'meta' });
    if (s.source_issue_number) meta.appendChild(h('span', { class: 'chip', text: `from #${s.source_issue_number}` }));
    meta.appendChild(h('span', { class: 'chip', text: s.subproduct }));
    if (rateable && this.state.analysis) {
      meta.appendChild(h('span', { class: 'chip', text: `match ${Math.round(s.relevance * 100)}%` }));
    }
    children.push(meta);

    if (rateable) {
      const rated = this.state.rated === s.id;
      children.push(
        h('div', { class: 'row' }, [
          h('button', {
            class: `sm ${rated ? 'active' : ''}`,
            text: rated ? 'Thanks!' : 'This helped',
            onclick: () => this.rate(s.id, true),
          }),
          h('button', { class: 'sm', text: 'Did not help', onclick: () => this.rate(s.id, false) }),
        ])
      );
    }
    return h('div', { class: 'card' }, children);
  }

  async rate(solutionId, helpful) {
    const a = this.state.analysis;
    if (!a) return;
    try {
      await apiPost(this.config, '/api/rate', {
        report_id: a.report_id,
        solution_id: solutionId,
        helpful,
      });
    } catch (err) {
      console.warn('[loopdesk] rating failed', err);
    }
    if (helpful) this.setState({ rated: solutionId });
    else this.setState({ view: 'ticket' });
  }

  // ---- view: ticket ----
  renderTicket(body, ctx) {
    const a = this.state.analysis || {};
    if (this.state.ticket) {
      const t = this.state.ticket;
      body.appendChild(
        h('div', { class: 'banner ok', text: t.me_too ? 'Added to the existing ticket.' : 'Ticket raised. The team can see your screenshot and page details.' })
      );
      if (t.github_url) {
        body.appendChild(h('p', {}, [h('a', { href: t.github_url, target: '_blank', rel: 'noopener', text: `View issue #${t.github_issue_number}` })]));
      } else if (t.github_issue_number) {
        body.appendChild(h('p', { class: 'muted', text: `Issue #${t.github_issue_number} (dry-run mode - no GitHub token configured)` }));
      }
      body.appendChild(h('button', { class: 'ghost', text: 'Done', onclick: () => this.close() }));
      return;
    }

    body.appendChild(h('label', { text: 'Title' }));
    this.titleEl = h('input', { type: 'text' });
    this.titleEl.value = this.state.ticketTitle || a.suggested_title || '';
    body.appendChild(this.titleEl);

    body.appendChild(h('label', { text: 'Details (sent to the dev team)' }));
    this.descEl = h('textarea', { rows: '9' });
    this.descEl.value = this.state.ticketDesc || a.suggested_description || this.state.comment || '';
    body.appendChild(this.descEl);

    body.appendChild(
      h('p', { class: 'muted', text: 'Your screenshot, console errors and page details are attached.' })
    );
    body.appendChild(
      h('button', {
        class: 'primary',
        text: this.state.busy ? 'Sending...' : 'Raise ticket',
        disabled: this.state.busy,
        onclick: () => this.submitTicket(ctx, {}),
      })
    );
    body.appendChild(
      h('button', { class: 'ghost', text: 'Back', onclick: () => this.setState({ view: null }) })
    );
  }

  async submitTicket(ctx, extra) {
    const a = this.state.analysis || {};
    const title = this.titleEl ? this.titleEl.value : a.suggested_title || 'Issue reported from the app';
    const description = this.descEl ? this.descEl.value : a.suggested_description || '';
    this.setState({ busy: true, view: 'ticket' });
    try {
      const ticket = await apiPost(this.config, '/api/tickets', {
        report_id: a.report_id || null,
        title,
        description: description + (this.state.screenshot && a.screenshot_url ? `\n\n[Screenshot](${a.screenshot_url})` : ''),
        subproduct: ctx.subproduct,
        ...extra,
      });
      this.setState({ busy: false, ticket });
    } catch (err) {
      console.error('[loopdesk] ticket failed', err);
      this.setState({ busy: false, error: 'Could not raise the ticket. Please try again.' });
    }
  }

  // ---- view: my reports ----
  async renderReports(body) {
    body.appendChild(h('p', { class: 'muted' }, [h('span', { class: 'spin' }), document.createTextNode(' loading...')]));
    let rows = [];
    try {
      rows = await apiGet(this.config, '/api/reports/mine', { session_id: sessionId() });
    } catch (err) {
      console.warn('[loopdesk] reports failed', err);
    }
    if (this.state.tab !== 'reports' || !this.panel) return;
    body.textContent = '';
    if (!rows.length) {
      body.appendChild(h('p', { class: 'muted', text: 'Nothing reported from this browser yet.' }));
      return;
    }
    rows.forEach((r) => {
      const children = [
        h('h3', { text: r.comment || `Report on ${r.route}` }),
        h('p', { class: 'muted', text: new Date(r.created_at).toLocaleString() }),
      ];
      if (r.fixed_in) {
        children.push(
          h('div', { class: 'banner ok', text: `Fixed${r.fixed_in.version ? ` in v${r.fixed_in.version}` : ''}: ${r.fixed_in.title}` })
        );
      } else if (r.ticket) {
        children.push(h('span', { class: 'chip', text: `ticket #${r.ticket.number} - ${r.ticket.status}` }));
      } else {
        children.push(h('span', { class: 'chip ok', text: 'resolved without a ticket' }));
      }
      body.appendChild(h('div', { class: 'card' }, children));
    });
  }
}
