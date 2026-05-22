import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

test("patient component file structure is present", () => {
  [
    "src/components/PatientPortal.jsx",
    "src/components/LeftSidebar.jsx",
    "src/components/ChatPanel.jsx",
    "src/components/MessageBubble.jsx",
    "src/components/SlotCard.jsx",
    "src/components/VoiceRecorder.jsx",
    "src/components/WebRTCCall.jsx",
    "src/components/AgentTrace.jsx",
    "src/components/LanguageBadge.jsx",
    "src/styles/globals.css",
    "src/styles/animations.css",
  ].forEach((path) => assert.doesNotThrow(() => read(path), `${path} should exist`));
});

test("patient input supports bilingual typing and required quick actions", () => {
  const chat = read("src/components/ChatPanel.jsx");
  assert.match(chat, /dir="auto"/);
  assert.match(chat, /Type in English or اردو میں لکھیں\.\.\./);
  assert.match(chat, /🗓 Book appointment/);
  assert.match(chat, /❌ Cancel booking/);
  assert.match(chat, /ℹ️ My appointments/);
});

test("patient API service keeps all backend integration paths wired", () => {
  const service = read("src/services/patientAgentService.ts");
  assert.match(service, /api\.post\("\/chat"/);
  assert.match(service, /api\.post\("\/chat\/message"/);
  assert.match(service, /api\.post\("\/voice\/chat"/);
  assert.match(service, /\/ws\/voice\/\$\{encodeURIComponent\(sessionId\)\}/);
  assert.match(service, /detected_lang/);
  assert.match(service, /suggestedSlots/);
  assert.match(service, /tool_calls/);
});

test("patient portal uses real backend slots and publishes admin refresh events", () => {
  const portal = read("src/components/PatientPortal.jsx");
  assert.doesNotMatch(portal, /DEMO_SLOTS/);
  assert.doesNotMatch(portal, /confirmSlot/);
  assert.match(portal, /publishPortalEvent\(\{\s*type:\s*"appointments:changed"\s*\}\)/);
  assert.match(portal, /crypto\.randomUUID\(\)\.slice\(0,\s*8\)/);
  assert.match(portal, /window\.sessionStorage\.setItem/);
});

test("message bubbles auto-detect Urdu and surface high wait warnings", () => {
  const bubble = read("src/components/MessageBubble.jsx");
  assert.match(bubble, /export const isUrdu = \(text = ""\) => \/\[\\u0600-\\u06FF\]\//);
  assert.match(bubble, /dir=\{urdu \? "rtl" : "auto"\}/);
  assert.match(bubble, /> 30/);
  assert.match(bubble, /Estimated wait is/);
});

test("agent trace shows provider routing and tokens latency summary", () => {
  const trace = read("src/components/AgentTrace.jsx");
  assert.match(trace, /via \{capitalize\(step\.provider \|\| "groq"\)\}/);
  assert.match(trace, /trace-token-summary/);
  assert.match(trace, /Groq\(1\) \+ Gemini\(1\)/);
  assert.match(trace, /s total/);
});

test("dev and production proxies preserve API and websocket routes", () => {
  const vite = read("vite.config.ts");
  const nginx = read("nginx.conf");
  assert.match(vite, /"\/api"/);
  assert.match(vite, /target:\s*"http:\/\/127\.0\.0\.1:8000"/);
  assert.match(vite, /"\/ws"/);
  assert.match(vite, /ws:\s*true/);
  assert.match(nginx, /location \/api\//);
  assert.match(nginx, /proxy_pass http:\/\/backend:8000\/api\//);
  assert.match(nginx, /location \/ws\//);
  assert.match(nginx, /proxy_set_header Upgrade \$http_upgrade/);
});

test("clinical sanctuary theme variables and fonts are defined globally", () => {
  const globals = read("src/styles/globals.css");
  const styles = read("src/styles.css");
  const animations = read("src/styles/animations.css");
  [
    "--bg-base",
    "--bg-surface",
    "--bg-elevated",
    "--accent-teal",
    "--accent-amber",
    "--accent-red",
    "--shadow-glow",
  ].forEach((token) => assert.match(globals, new RegExp(token)));
  assert.match(styles, /DM\+Serif\+Display/);
  assert.match(styles, /IBM\+Plex\+Sans/);
  assert.match(styles, /Noto\+Nastaliq\+Urdu/);
  assert.match(animations, /@keyframes reveal-up/);
  assert.match(animations, /@keyframes message-in-right/);
  assert.match(animations, /@keyframes waveform/);
});
