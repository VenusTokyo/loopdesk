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
