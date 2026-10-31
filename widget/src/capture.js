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
