/**
 * generate-index.mjs
 *
 * After `vite build` with prerendering disabled, TanStack Start does NOT
 * emit an index.html because it expects a Node SSR runtime.
 *
 * Since we deploy to nginx as a static SPA, we need an index.html that
 * bootstraps the TanStack Router client.
 *
 * This script reads the built server manifest to discover the clientEntry
 * and route preloads, then generates a proper index.html with the TSR
 * stream-barrier bootstrap script that TanStack Start expects.
 *
 * Usage:  node scripts/generate-index.mjs <distDir>
 */

import { readFileSync, readdirSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import { pathToFileURL } from "url";

const distDir = process.argv[2];
if (!distDir) {
  console.error("Usage: node scripts/generate-index.mjs <distDir>");
  process.exit(1);
}

const clientDir = join(distDir, "client");
const assetsDir = join(clientDir, "assets");
const serverAssetsDir = join(distDir, "server", "assets");

if (!existsSync(assetsDir)) {
  console.error(`Assets dir not found: ${assetsDir}`);
  process.exit(1);
}

// ── 1. Read the server manifest to get clientEntry and route info ──
let manifest = null;
if (existsSync(serverAssetsDir)) {
  const manifestFile = readdirSync(serverAssetsDir).find((f) =>
    f.startsWith("_tanstack-start-manifest")
  );
  if (manifestFile) {
    const manifestPath = join(serverAssetsDir, manifestFile);
    const manifestUrl = pathToFileURL(manifestPath).href;
    try {
      const mod = await import(manifestUrl);
      manifest = mod.tsrStartManifest();
    } catch (e) {
      console.warn("  Warning: Could not load manifest, falling back to file scan");
    }
  }
}

// ── 2. Determine client entry and CSS ──
let clientEntry;
if (manifest?.clientEntry) {
  // manifest.clientEntry is like "/assets/index-BRLaJBn2.js"
  clientEntry = manifest.clientEntry;
} else {
  // Fallback: find the largest index-*.js (the React bundle)
  const files = readdirSync(assetsDir);
  const indexFiles = files
    .filter((f) => /^index-.*\.js$/.test(f))
    .map((f) => ({
      name: f,
      size: readFileSync(join(assetsDir, f)).length,
    }))
    .sort((a, b) => b.size - a.size);
  clientEntry = indexFiles.length ? `/assets/${indexFiles[0].name}` : null;
}

if (!clientEntry) {
  console.error("Could not determine client entry JS");
  process.exit(1);
}

const cssFile = readdirSync(assetsDir).find((f) => /^styles.*\.css$/.test(f));

// ── 3. Build route preloads for the root route ──
const rootPreloads = manifest?.routes?.__root__?.preloads || [clientEntry];

// ── 4. Build the TSR bootstrap script (mimics what prerendering produces) ──
// This tells TanStack Router's client that the page was "server rendered"
// with just the root route, so it can hydrate properly.
const tsrBootstrap = `(self.$R=self.$R||{})["tsr"]=[];self.$_TSR={h(){this.hydrated=!0,this.c()},e(){this.streamEnded=!0,this.c()},c(){this.hydrated&&this.streamEnded&&(delete self.$_TSR,delete self.$R.tsr)},p(e){this.initialized?e():this.buffer.push(e)},buffer:[]};$_TSR.router=($R=>$R[0]={manifest:$R[1]={routes:$R[2]={__root__:$R[3]={preloads:$R[4]=${JSON.stringify(rootPreloads)},assets:$R[5]=[$R[6]={tag:"script",attrs:$R[7]={type:"module",async:!0},children:"import(\\"${clientEntry}\\")"}]}}},matches:$R[8]=[$R[9]={i:"__root__\\u0000",u:${Date.now()},s:"success",ssr:!0}],lastMatchId:"__root__\\u0000"})($R["tsr"]);$_TSR.e();document.currentScript.remove()`;

// ── 5. Build modulepreload links ──
const preloadLinks = rootPreloads
  .map((p) => `  <link rel="modulepreload" href="${p}"/>`)
  .join("\n");

// ── 6. Generate the HTML ──
const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charSet="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MediFlow \u2014 AI Clinic Operations</title>
<meta name="description" content="AI-powered clinic operations platform with smart scheduling, voice booking, and real-time ops monitoring."/>
<meta property="og:title" content="MediFlow \u2014 AI Clinic Operations"/>
<meta property="og:description" content="AI-powered clinic operations platform."/>
<meta property="og:type" content="website"/>
${preloadLinks}
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin=""/>${cssFile ? `\n<link rel="stylesheet" href="/assets/${cssFile}"/>` : ""}
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet"/>
</head>
<body>
<div class="min-h-screen grid place-items-center"><div style="width:40px;height:40px;border-radius:50%;border:2px solid rgba(99,102,241,0.3);border-top-color:rgb(99,102,241);animation:spin 1s linear infinite"></div></div>
<style>@keyframes spin{to{transform:rotate(360deg)}}</style>
<script class="$tsr" id="$tsr-stream-barrier">${tsrBootstrap}</script>
<script type="module" async="">import("${clientEntry}")</script>
</body>
</html>
`;

const outPath = join(clientDir, "index.html");
writeFileSync(outPath, html, "utf-8");
console.log(`\u2713 Generated ${outPath}`);
console.log(`  Client entry: ${clientEntry}`);
if (cssFile) console.log(`  CSS: ${cssFile}`);
