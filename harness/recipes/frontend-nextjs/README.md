# Recipe: frontend-nextjs

A plain-**JavaScript** Next.js (App Router) chat UI — no TypeScript toolchain, so the
non-coder audience can read and edit it without a TS build to learn. It is the tested UI
shell the planner names when the spec has a **web UI**: upload a dataset → ask in natural
language → see the answer rendered as markdown (tables/charts) → deep-link the trace.

**Stamped 2026-06-22, source `feature/data-analysis-agent-2026-06-20`.**
Stack: `next` 15.3.3 · `react` 19.1.0 · `react-markdown` 10.1.0 · `remark-gfm` ^4 ·
`tailwindcss` 3.4.17. (Re-prove green before re-stamping when these move — see
`../README.md` § re-sync.)

---

## What's here

```
app/layout.js        root layout — metadata + Plotly-from-CDN <script> + Tailwind globals
app/page.js          entry — dynamic(import("./ChatPage"), { ssr: false }) to kill SSR
app/ChatPage.js      the whole client app — chat, upload, sessions, markdown, charts
app/globals.css      the three @tailwind directives
next.config.js       rewrites /api/* → http://localhost:8001/* (same-origin proxy, no CORS)
tailwind.config.js   content globs for app/
package.json         deps + dev/build/start scripts (no lockfile — npm install regenerates)
```
`node_modules/` and `.next/` are gitignored — they regenerate from `npm install` / `npm run build`.

## Quickstart

```bash
npm install
npm run dev          # Next dev server (default :3000). Backend must be up on :8001.
```
The backend agent must be running on **:8001** — the UI proxies `/api/*` there via
`next.config.js` rewrites, so a UI with a dead backend is the #1 false "it's broken"
report. `npm run build` then `npm run start` for the production build.

### `NEXT_PUBLIC_API_URL`
The shipped code calls a **relative `/api`** path and lets `next.config.js` rewrite it to
`http://localhost:8001`. If you instead point the browser straight at the backend, read the
base from **`NEXT_PUBLIC_API_URL`** (default **`http://localhost:8001`**) — any var the
browser reads MUST be `NEXT_PUBLIC_`-prefixed, or it's `undefined` client-side:
```js
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
```
Prefer the rewrite (same-origin, no CORS); use the env var only when the UI and backend are
on different origins.

## The three guards (status in this copy)

| Guard | Status | Where |
|---|---|---|
| **SSR-safe localStorage** | ✅ present | `ChatPage.js` `ls` wrapper (try/catch + `window.localStorage`); `page.js` `dynamic(…, { ssr:false })` |
| **`react-markdown` + `remark-gfm`, no raw HTML (XSS guard)** | ✅ present (default-safe) | `ChatPage.js` `<ReactMarkdown remarkPlugins={[remarkGfm]}>` |
| **per-tab session id via `crypto.randomUUID()` + `Math.random` fallback** | ⚠️ partial — `Math.random`-only `genId()`; see note | `ChatPage.js` `genId()` |

### SSR-safe localStorage — present
`ChatPage.js` wraps every `localStorage` call in a `ls` helper (`try { window.localStorage… } catch {}`),
so it never throws on the server or in a privacy-locked browser. Belt-and-braces: `page.js` loads
`ChatPage` with `dynamic(() => import("./ChatPage"), { ssr: false })`, so the browser-only app
(localStorage, the Plotly CDN global) never runs during SSR at all.

### react-markdown + remark-gfm, no raw HTML — present, safe by default
The assistant message renders through `<ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>`
— `remark-gfm` gives GFM tables/strikethrough. **react-markdown 10.x does not render raw HTML**: there is no
`html:true` toggle and `rehype-raw` is intentionally **not** added, so embedded `<script>`/`<img onerror=…>`
in LLM output is escaped, not executed. That is the XSS guard — **do not add `rehype-raw`** to "fix" HTML
passthrough; that re-opens the hole.

### Per-tab session id — recommended hardening (currently `Math.random` only)
This copy mints ids with `genId()` = `Math.random().toString(36) + Date.now().toString(36)` and persists the
thread id under `localStorage["thread_id"]` (so a reload resumes the same conversation — the "my history
vanished" bug). Prefer a collision-resistant **`crypto.randomUUID()` with a `Math.random` fallback** for the
session/thread id:
```js
function genId() {
  try { return crypto.randomUUID(); }   // collision-resistant, available in all modern browsers
  catch { return Math.random().toString(36).slice(2) + Date.now().toString(36); }  // SSR / old-browser fallback
}
```
Drop-in for the existing `genId()`; the persistence wiring already in `ChatPage.js` is unchanged.

## Wiring notes for the planner / executor
- The page reads the FastAPI **`{ ok, data }` envelope** (`json.data.answer`, `.run_id`, `.chart_spec`,
  `.cost_usd`, `.input_tokens`/`.output_tokens`) — keep the server's envelope in sync (`spec/patterns/fastapi.md`).
- Charts: `layout.js` loads **Plotly from the CDN** (no npm dep, no SSR crash); a `chart_spec` of
  `{ data, layout }` renders via `window.Plotly.newPlot`. Swap for `react-markdown`-only if the spec has no charts.
- Trace deep-link points at `http://localhost:8001/traces` (the server renders the timeline — don't rebuild it).
