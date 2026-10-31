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
