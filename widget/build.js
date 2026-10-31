/**
 * Build: concatenate the source modules into one IIFE.
 *
 * No bundler on purpose - the widget must stay a single readable file that
 * anyone can drop into any host app, and the build must not need a toolchain
 * at demo time.
 *
 * Order matters: api.js grabs the native fetch before metadata.js wraps it.
 */
const fs = require('fs');
const path = require('path');

const ORDER = ['api.js', 'metadata.js', 'capture.js', 'ui.js', 'index.js'];
const src = path.join(__dirname, 'src');
const out = path.join(__dirname, 'dist', 'widget.js');

const parts = ORDER.map((f) => {
  const body = fs.readFileSync(path.join(src, f), 'utf8').trim();
  return `/* ---------- ${f} ---------- */\n${body}`;
});

const banner = `/*! LoopDesk widget v0.1.0 | MIT | built ${new Date().toISOString()} */`;
const bundle = `${banner}\n(function () {\n'use strict';\n\n${parts.join('\n\n')}\n})();\n`;

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, bundle, 'utf8');
console.log(`widget/dist/widget.js  ${(bundle.length / 1024).toFixed(1)} kB`);
