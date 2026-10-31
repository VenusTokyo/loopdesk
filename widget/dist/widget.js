/*! LoopDesk widget v0.1.0 | MIT | built 2026-10-31T07:58:37.141Z */
(function () {
'use strict';

/* ---------- api.js ---------- */
/** Thin API client. Uses the native fetch captured before we wrapped it. */
const nativeFetchRef = window.fetch.bind(window);

function apiUrl(config, path) {
  return `${config.api.replace(/\/$/, '')}${path}`;
}

async function apiGet(config, path, params) {
  const qs = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== null && v !== undefined && v !== '')
  ).toString();
  const res = await nativeFetchRef(apiUrl(config, path) + (qs ? `?${qs}` : ''), {
    headers: { 'X-LoopDesk-Key': config.key || '' },
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(config, path, body) {
  const res = await nativeFetchRef(apiUrl(config, path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-LoopDesk-Key': config.key || '' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

/* ---------- metadata.js ---------- */
/**
 * Everything the agent needs that the user should not have to type.
 *
 * Console errors and failed requests are buffered from page load, because by
 * the time someone opens the widget the devtools evidence is long gone.
 */
const LD_MAX_ERRORS = 10;
const LD_MAX_REQUESTS = 10;

const buffers = {
  errors: [],
  requests: [],
};

function pushCapped(list, item, cap) {
  list.push(item);
  while (list.length > cap) list.shift();
}

function installErrorCapture() {
  const nativeError = console.error.bind(console);
  console.error = function (...args) {
    try {
      pushCapped(buffers.errors, args.map(fmt).join(' ').slice(0, 500), LD_MAX_ERRORS);
    } catch (_) {
      /* never break the host app's logging */
    }
    return nativeError(...args);
  };

  window.addEventListener('error', (e) => {
    const where = e.filename ? ` (${e.filename}:${e.lineno})` : '';
    pushCapped(buffers.errors, `${e.message}${where}`.slice(0, 500), LD_MAX_ERRORS);
  });

  window.addEventListener('unhandledrejection', (e) => {
    pushCapped(buffers.errors, `Unhandled rejection: ${fmt(e.reason)}`.slice(0, 500), LD_MAX_ERRORS);
  });
}

function installNetworkCapture() {
  const nativeFetch = window.fetch;
  if (typeof nativeFetch === 'function') {
    window.fetch = async function (input, init) {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const method = (init && init.method) || (input && input.method) || 'GET';
      try {
        const res = await nativeFetch.apply(this, arguments);
        if (res.status >= 400) {
          pushCapped(buffers.requests, { url: short(url), status: res.status, method }, LD_MAX_REQUESTS);
        }
        return res;
      } catch (err) {
        pushCapped(buffers.requests, { url: short(url), status: 0, method }, LD_MAX_REQUESTS);
        throw err;
      }
    };
  }

  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__ld = { method, url };
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener('loadend', () => {
      const meta = this.__ld || {};
      if (this.status === 0 || this.status >= 400) {
        pushCapped(
          buffers.requests,
          { url: short(meta.url || ''), status: this.status, method: meta.method || 'GET' },
          LD_MAX_REQUESTS
        );
      }
    });
    return send.apply(this, arguments);
  };
}

function fmt(value) {
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch (_) {
    return String(value);
  }
}

/** Query strings can carry personal data, so they never leave the page. */
function short(url) {
  try {
    const u = new URL(url, window.location.origin);
    return u.pathname + (u.search ? '?<redacted>' : '');
  } catch (_) {
    return String(url).split('?')[0].slice(0, 200);
  }
}

function browserName() {
  const ua = navigator.userAgent;
  const m =
    ua.match(/(Firefox|Edg|OPR|Chrome|Safari)\/(\d+)/) || [];
  const name = { Edg: 'Edge', OPR: 'Opera' }[m[1]] || m[1] || 'Unknown';
  return `${name} ${m[2] || ''}`.trim();
}

function subproductFor(route, config) {
  if (config.subproduct && config.subproduct !== 'auto') return config.subproduct;
  const host = window.LOOPDESK_CONTEXT || {};
  if (host.subproduct) return host.subproduct;
  const seg = route.split('/').filter(Boolean)[0];
  return seg || 'unknown';
}

function collectContext(config) {
  const host = window.LOOPDESK_CONTEXT || {};
  const route = window.location.pathname;
  return {
    route,
    url: window.location.href.split('?')[0],
    subproduct: subproductFor(route, config),
    app_version: host.app_version || '0.0.0',
    user_role: host.user_role || 'member',
    browser: browserName(),
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    page_title: document.title,
    console_errors: buffers.errors.slice(-5),
    failed_requests: buffers.requests.slice(-5),
    session_id: sessionId(),
  };
}

function sessionId() {
  const KEY = 'loopdesk.session';
  let id = null;
  try {
    id = localStorage.getItem(KEY);
    if (!id) {
      id = 'sess_' + Math.random().toString(36).slice(2, 12);
      localStorage.setItem(KEY, id);
    }
  } catch (_) {
    id = 'sess_ephemeral';
  }
  return id;
}

/* ---------- capture.js ---------- */
/**
 * Screenshot capture.
 *
 * html2canvas renders the DOM rather than the screen, which is what lets us
 * blur [data-private] content *before* the pixels exist, and avoids a browser
 * permission prompt mid-demo. If it is unavailable we fall back to
 * getDisplayMedia, which still works but asks the user to pick a surface.
 */
const H2C_SRC = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
const PRIVATE_CLASS = 'loopdesk-redacted';

let h2cPromise = null;

function loadHtml2Canvas() {
  if (window.html2canvas) return Promise.resolve(window.html2canvas);
  if (h2cPromise) return h2cPromise;
  h2cPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = H2C_SRC;
    s.onload = () => resolve(window.html2canvas);
    s.onerror = () => {
      // Do not cache the failure: a flaky CDN on the first try must not
      // disable screenshots for the rest of the session.
      h2cPromise = null;
      reject(new Error('html2canvas failed to load'));
    };
    document.head.appendChild(s);
  });
  return h2cPromise;
}

function injectRedactionStyle() {
  if (document.getElementById('loopdesk-redaction-style')) return;
  const style = document.createElement('style');
  style.id = 'loopdesk-redaction-style';
  // html2canvas 1.4 does not render CSS `filter`, so a blur alone would look
  // redacted on screen and leak in the capture. Painting a solid block and
  // hiding the children is rendered faithfully by both capture paths; the
  // blur is kept for the getDisplayMedia fallback, which captures real pixels.
  style.textContent =
    `.${PRIVATE_CLASS}{color:transparent !important;background:#94a3b8 !important;` +
    `border-radius:3px !important;filter:blur(6px);}` +
    `.${PRIVATE_CLASS} *{visibility:hidden !important;}`;
  document.head.appendChild(style);
}

function redact(on) {
  injectRedactionStyle();
  document.querySelectorAll('[data-private]').forEach((el) => {
    el.classList.toggle(PRIVATE_CLASS, on);
  });
}

/** Returns a PNG data URL of the current page, with private content blurred. */
async function capturePage(hideEl) {
  const h2c = await loadHtml2Canvas();
  if (hideEl) hideEl.style.visibility = 'hidden';
  redact(true);
  // One frame so the blur is actually painted before we render.
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

  try {
    const canvas = await h2c(document.body, {
      backgroundColor: '#ffffff',
      scale: Math.min(window.devicePixelRatio || 1, 1.5),
      logging: false,
      useCORS: true,
      windowWidth: document.documentElement.clientWidth,
      windowHeight: document.documentElement.clientHeight,
      x: window.scrollX,
      y: window.scrollY,
      width: window.innerWidth,
      height: window.innerHeight,
    });
    return canvas.toDataURL('image/png');
  } finally {
    redact(false);
    if (hideEl) hideEl.style.visibility = '';
  }
}

/** Fallback path: the browser's own screen capture. */
async function captureViaDisplayMedia() {
  const stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'browser' } });
  const track = stream.getVideoTracks()[0];
  const video = document.createElement('video');
  video.srcObject = stream;
  await video.play();
  await new Promise((r) => setTimeout(r, 250));

  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  track.stop();
  return canvas.toDataURL('image/png');
}

async function captureWithFallback(hideEl) {
  try {
    return await capturePage(hideEl);
  } catch (err) {
    console.warn('[loopdesk] DOM capture failed, trying screen capture', err);
    try {
      return await captureViaDisplayMedia();
    } catch (err2) {
      console.warn('[loopdesk] screen capture unavailable', err2);
      return null; // the report still goes through, just without an image
    }
  }
}

/* ---------- ui.js ---------- */
/**
 * Widget UI. Everything lives in a Shadow DOM so the host app's CSS cannot
 * reach in and ours cannot leak out.
 */
const LD_STYLES = `
:host { all: initial; }
*, *::before, *::after { box-sizing: border-box; }
.root {
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #1b1f24;
  position: fixed; inset: auto 20px 20px auto; z-index: 2147483000;
}
.fab {
  width: 52px; height: 52px; border-radius: 26px; border: 0; cursor: pointer;
  background: #1f6feb; color: #fff; font-size: 20px; line-height: 1;
  box-shadow: 0 6px 20px rgba(16,24,40,.28);
  display: grid; place-items: center; transition: transform .15s ease;
}
.fab:hover { transform: translateY(-2px); }
.panel {
  position: fixed; right: 20px; bottom: 84px; width: 380px; max-width: calc(100vw - 32px);
  max-height: min(680px, calc(100vh - 120px));
  background: #fff; border: 1px solid #d8dee4; border-radius: 14px;
  box-shadow: 0 18px 50px rgba(16,24,40,.22);
  display: flex; flex-direction: column; overflow: hidden;
}
.hd { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid #eaeef2; }
.hd h2 { margin: 0; font-size: 14px; font-weight: 600; flex: 1; }
.hd .sub { font-size: 12px; color: #6b7684; font-weight: 400; }
.x { border: 0; background: transparent; cursor: pointer; font-size: 18px; color: #6b7684; padding: 2px 6px; }
.body { padding: 14px; overflow-y: auto; }
.tabs { display: flex; gap: 4px; padding: 0 14px; border-bottom: 1px solid #eaeef2; }
.tab { border: 0; background: transparent; padding: 8px 10px; cursor: pointer; font-size: 13px; color: #6b7684; border-bottom: 2px solid transparent; }
.tab[aria-selected="true"] { color: #1f6feb; border-bottom-color: #1f6feb; font-weight: 600; }
.muted { color: #6b7684; font-size: 13px; }
.card { border: 1px solid #e3e8ee; border-radius: 10px; padding: 12px; margin-bottom: 10px; background: #fcfdff; }
.card h3 { margin: 0 0 4px; font-size: 13.5px; font-weight: 600; }
.card .steps { margin: 8px 0 0; padding-left: 18px; font-size: 13px; color: #2d333b; }
.card .steps li { margin: 3px 0; }
.meta { display: flex; gap: 6px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.pill { font-size: 11px; padding: 2px 7px; border-radius: 999px; background: #eef2f6; color: #4a5560; }
.pill.ok { background: #e6f6ec; color: #1a7f37; }
.pill.warn { background: #fff4e5; color: #9a6700; }
.pill.bad { background: #ffebe9; color: #b42318; }
button.primary, button.ghost, button.sm {
  font: inherit; cursor: pointer; border-radius: 8px; padding: 9px 12px; border: 1px solid transparent;
}
button.primary { background: #1f6feb; color: #fff; width: 100%; font-weight: 600; }
button.primary:disabled { background: #b6c6e3; cursor: progress; }
button.ghost { background: #fff; border-color: #d8dee4; color: #24292f; width: 100%; }
button.sm { padding: 5px 10px; font-size: 12px; background: #fff; border-color: #d8dee4; }
button.sm.active { background: #1f6feb; color: #fff; border-color: #1f6feb; }
textarea, input[type=text] {
  width: 100%; font: inherit; padding: 9px 10px; border: 1px solid #d8dee4; border-radius: 8px;
  resize: vertical; background: #fff; color: inherit;
}
label { display: block; font-size: 12px; font-weight: 600; margin: 10px 0 4px; color: #4a5560; }
.preview { width: 100%; border: 1px solid #e3e8ee; border-radius: 8px; display: block; }
.row { display: flex; gap: 8px; margin-top: 10px; }
.row > * { flex: 1; }
.banner { padding: 10px 12px; border-radius: 8px; font-size: 13px; margin-bottom: 12px; }
.banner.ok { background: #e6f6ec; color: #1a6b31; }
.banner.warn { background: #fff4e5; color: #8a5a00; }
.banner.bad { background: #fff1f0; color: #9f2d20; }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid #c9d4e3; border-top-color: #1f6feb; border-radius: 50%; animation: s .7s linear infinite; vertical-align: -2px; }
@keyframes s { to { transform: rotate(360deg); } }
.foot { padding: 8px 14px; border-top: 1px solid #eaeef2; font-size: 11px; color: #8b94a0; display: flex; justify-content: space-between; }
a { color: #1f6feb; }
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

function confidencePill(verdict, confidence) {
  const map = {
    confident: ['ok', 'known fix'],
    maybe: ['warn', 'possible match'],
    unknown: ['bad', 'no known fix'],
  };
  const [cls, label] = map[verdict] || map.unknown;
  return h('span', { class: `pill ${cls}`, text: `${label} - ${Math.round(confidence * 100)}%` });
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

    this.fab = h('button', {
      class: 'fab',
      title: 'Report a problem',
      'aria-label': 'Report a problem',
      text: '?',
      onclick: () => this.toggle(),
    });
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
    if (s.source_issue_number) meta.appendChild(h('span', { class: 'pill', text: `from #${s.source_issue_number}` }));
    meta.appendChild(h('span', { class: 'pill', text: s.subproduct }));
    if (rateable && this.state.analysis) {
      meta.appendChild(h('span', { class: 'pill', text: `match ${Math.round(s.relevance * 100)}%` }));
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
        children.push(h('span', { class: 'pill warn', text: `ticket #${r.ticket.number} - ${r.ticket.status}` }));
      } else {
        children.push(h('span', { class: 'pill ok', text: 'resolved without a ticket' }));
      }
      body.appendChild(h('div', { class: 'card' }, children));
    });
  }
}

/* ---------- index.js ---------- */
/**
 * Entry point. Reads configuration off its own <script> tag, honours the
 * route blocklist, and mounts the widget.
 */
function readConfig() {
  const el =
    document.currentScript ||
    document.querySelector('script[src*="widget.js"]') ||
    { dataset: {} };
  const d = el.dataset || {};
  const src = el.src || '';
  let origin = '';
  try {
    origin = new URL(src, window.location.href).origin;
  } catch (_) {
    origin = window.location.origin;
  }
  return {
    api: d.api || origin || window.location.origin,
    key: d.key || 'demo-key',
    subproduct: d.subproduct || 'auto',
    blocklist: (d.blocklist || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  };
}

/** Glob match, so `/settings/*` covers every settings page. */
function routeBlocked(route, patterns) {
  return patterns.some((p) => {
    const re = new RegExp(
      '^' + p.split('*').map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$'
    );
    return re.test(route);
  });
}

function boot() {
  const config = readConfig();

  if (routeBlocked(window.location.pathname, config.blocklist)) {
    // Not rendered at all - no button, no capture, nothing to misfire on a
    // page that shows payment or identity data.
    console.info('[loopdesk] route is blocklisted; widget not mounted');
    return;
  }

  installErrorCapture();
  installNetworkCapture();

  const ui = new LoopDeskUI(config);
  window.LoopDesk = {
    open: () => ui.open(),
    close: () => ui.close(),
    config,
    version: '0.1.0',
  };
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
})();
