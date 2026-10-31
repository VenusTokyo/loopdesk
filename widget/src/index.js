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
