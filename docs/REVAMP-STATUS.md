# Classess v3 — UI Revamp Status (living record)

**Purpose:** single source of truth to resume the premium UI revamp if the session stops/restarts. Keep this current at every milestone.
_Last updated: 2026-06-26._

---

## 0. TL;DR — where we are right now
- **Branch:** `v3-design-revamp` (NOT yet merged/deployed). The LIVE site `3.classess.com` is still the OLD pre-revamp build (`main` @ `3845e4b`). Nothing in this revamp is live until the final merge+deploy.
- **Latest commit:** `eb37a79` — visual pass done; ALL lanes matched the bar (I reviewed admin/student/parent/teacher shots myself — genuinely premium now, cool ultramarine, no coral). Hero + revamp + flow build + gaps + visual pass committed; typecheck + 387 tests green.
- **User decisions (2026-06-26):** BUILD a formal marks/grade report-card export (alongside the plain-language card) AND student-to-student DMs (with child-safety screening + moderation).
- **NEXT (now): final-features workflow** (`wbcsvwf9k`): report-card export · peer DMs + safety · Vidya handwritten annotations (sketched Caveat, cool ultramarine, no coral) · demo-school seed for /admin. THEN go live (§4 Step E).
- **Dev server:** `npm run dev -w @classess/web -- --port 3210` (used for screenshots; recipe in §6).
- **Residual minor/by-design gaps** (close in the visual pass, except the design-decisions which need the user): StudyQuadrant→teacher wire, perf bubble chart, sectioned mock paper, notifications drawer, Help/FAQ, fuller admin role catalogue. Design-decisions to confirm with user: raw-marks report-card export, peer-to-peer student chat.

## 1. DESIGN NORTH-STAR (the bar — do not drift)
- **Mercedes-sophisticated, spacey-but-refined, Virgil-intentional.** Cool + soft. **NO coral / warm-orange anywhere.**
- **Brand:** ultramarine signature (`--accent = --ultramarine #1F35E0`); subjects on the cool accent palette. Depth = hairline (0.5px) + tonal steps + frost — **never a shadow**. Mono-caps overline labels. One accent per surface. Reduced-motion honoured.
- **Beauty bar:** `/Users/depl/Downloads/cv3 p/classess-design-system/sample-page.html` (compose the kit's real classes: subject-card, matrix/cell + count, panel, ignite-card, table, tag, segmented, tabs, progress.animate, reveal, breadcrumb, page-head, cols, sched, flag, handnote).
- **v2 experience blueprint:** `docs/V2-EXPERIENCE-MAP.md` (118 v2 screens → v3 routes → data points/visualizations/tabs/drawers/internal-pages/routing + P0–P3 backlog). v2 screens at `/Users/depl/Downloads/Classess v2/{Admin,Teacher,student,parent}` (236 screenshots). v3 = UPGRADE of v2 in the v3 grammar (plain-language bands not raw %, evidence-first, permission ladder, no auto-send).
- **ORDER:** flow first, THEN visual verify (don't screenshot a screen before its flow is right).
- **DONE =** premium visual + v2-experience-complete + live on 3.classess.com + visually verified by me looking. ("I need it all done before you say done.")

## 2. WHAT HAS HAPPENED (done + committed on `v3-design-revamp`)
- `46f65a1` — cool soft on-brand ambient glow (ultramarine/cobalt/violet, no coral) on the home; butter-smooth sticky **ExpandingRail** (labels reveal on hover, fixed overlay, no reflow).
- `0caae7c` — **Vidya orb fix**: opens text-ready, voice opt-in (mic/hold-Space); removed the auto-getUserMedia-on-open that deadlocked the open. Verified opens reliably.
- `3d911a5` — **premium visual revamp**: every deep page recomposed to the sample-page bar; layered depth — right **EvidenceDrawer**, **BottomSheet**, left history, **internal/detail pages** (`teacher/students/[ref]`, `student/topic/[id]`, `admin/section/[ref]`); `SurfaceShell` chrome. typecheck green, no coral.
- `dcc4b8b` — **flow build (P0/P1)**: Holistic Progress Card (+PDF), Attendance heatmap, 6-dim project rubric, Paper analysis + remedial, Bloom donut + perf-trend + success gauge, Calendar/Timetable engine; lesson-notes voice→AI; admin ops (leave/staff/discipline/bulk); student timetable+attendance; deepened topic/detail. New routes `/student/timetable`, `/admin/operations`. typecheck green.
- (Pre-revamp, on `main` @ `3845e4b`, already deployed): Waves 0–2.5, AI-native, functional-completion, remediation, finish-functional, premium-polish, E2E-in-CI. Backend live on Railway, web on Vercel — but that's the OLD visual build.

## 3. WHAT'S HAPPENING (in flight)
- **`w3z81qn6u`** flow-gaps workflow: building the P2/P3 v2 features. New components landed: `MockSession`, `PracticeFormats`, `CourseBrowser`, `AchievementBadges`, `Markbook`, `PtmManager`, `QuestionPaperPreview`; data `courseData.ts`, `mockSession.ts`; route `/teacher/together`. Stage order: StudentGaps ✅ → TeacherGaps ⏳ → AdminGaps → SettingsGaps → Gate.

## 4. HOW TO COMPLETE — runbook (remaining, in order)
> Each step is typecheck-gated (`npm run typecheck -w @classess/web`) and, for UI, visually verified via §6 before moving on. Flow is already done (P0/P1/P2 + most P3); what's left is the visual pass → review → live.

**Step A — finish the VISUAL PASS** (screenshot every route, fix anything templated/sparse/off-brand/janky, close the §0 minor gaps). One serial lane per role + shared. For each route: §6 screenshot → READ → fix → re-shoot → repeat until it matches the §1 bar. Save shots to `/tmp/polish/<role>/`.

**Step B — human (me) review:** read the `/tmp/polish` shots, compare to ${SAMPLE in §1}, do final hands-on fixes on any screen still off.

**Step C — Vidya end-to-end check:** orb opens text-ready (✓), 5-path chat works, ambient watch-and-teach + on-screen annotations are HANDWRITTEN (Caveat, sketched) in COOL ultramarine/acid — **no coral**.

**Step D — confirm the 2 design-decisions with the user:** raw-marks report-card export? peer-to-peer student chat? (build or formally drop.)

**Step E — GO LIVE (exact commands):**
```
cd /Users/depl/Documents/classess-school
bash scripts/ci.sh            # typecheck + vitest(387) + pytest + build — must be green
npm run e2e                   # Playwright (self-manages :3210) — must be green
git checkout main && git merge v3-design-revamp     # fast-forward (no .github changes on this branch → no workflow-scope issue)
git push origin main
# backend:
export RAILWAY_TOKEN="$(grep -E '^RAILWAY_TOKEN=' .env.local | cut -d= -f2- | tr -d '"')"
railway up --service classess-backend --environment production
# web:
export VERCEL_TOKEN="$(grep -E '^VERCEL_TOKEN=' .env.local | cut -d= -f2- | tr -d '"')"
vercel --prod --yes --token "$VERCEL_TOKEN"
# prod smoke:
curl -s -o /dev/null -w '%{http_code}\n' https://3.classess.com
curl -s https://classess-backend-production.up.railway.app/health
```
**Step F — only then say DONE** (per §1 done-definition: premium visual + v2-experience-complete + live + verified-by-me).

### Resuming from a FRESH session (if this one stops)
1. Memory auto-loads → it points here. Read this whole doc + `docs/V2-EXPERIENCE-MAP.md`.
2. `cd /Users/depl/Documents/classess-school && git checkout v3-design-revamp && git log --oneline -8` (confirm latest commit; `git status` for any uncommitted in-flight work — re-verify/redo it).
3. `npm run dev -w @classess/web -- --port 3210` (for §6 screenshots).
4. **NOTE — workflow runs are session-specific** (`resumeFromRunId` only works in the same session). A fresh session CANNOT resume my background workflows; instead **re-do the current step hands-on, or re-author the visual-pass / gap workflow** from the spec in §1 + §4 + `docs/V2-EXPERIENCE-MAP.md` (the design bar, the recipes, and the residual-gap list are all self-contained here).
5. Continue from the step above that isn't done yet (currently: **Step A, visual pass**).

## 5. WHERE WHAT'S THERE (key paths)
- Web app: `surfaces/web/app` (routes) + `surfaces/web/app/_components` (components) + `surfaces/web/lib` (data/hooks).
- Shell/nav: `_components/SurfaceShell.tsx`, `_components/Rail.tsx` (ExpandingRail), `globals.css` (the `.rail` + page CSS), home = `app/page.tsx` → `_components/RoleLanding.tsx` (the glow `BLOOM_BLOBS`).
- Vidya: `_components/VidyaOrb.tsx`, `VidyaCanvas/VidyaSpotlight/VidyaSteps` (annotations — restyle handwritten cool), `lib/useVidya.ts`, `lib/vidyaServer.ts`.
- Drawers: `_components/EvidenceDrawer.tsx`, `BottomSheet.tsx`, `DetailShell.tsx`.
- Viz/feature components: `_components/{AttendanceHeatmap,HolisticProgressCard,ProjectRubric,PaperAnalysis,…,MockSession,PracticeFormats,CourseBrowser,AchievementBadges,Markbook,PtmManager,QuestionPaperPreview}.tsx`.
- Design system: `classess-design-system/{tokens.css,components.css}` (the real primitives) + `packages/design-system`.
- Docs: `docs/V2-EXPERIENCE-MAP.md` (blueprint), `docs/READINESS.md`, dossier `updates/classess-school-v3-build/`.

## 6. SCREENSHOT RECIPE (harness-correct — does NOT hang)
Write a node script under `surfaces/web/e2e` (so `@playwright/test` resolves), with the dev server on :3210:
```
import { chromium } from '@playwright/test';
const b=await chromium.launch(); const ctx=await b.newContext({viewport:{width:1440,height:900}}); const p=await ctx.newPage();
await p.addInitScript(([k,r,v,id])=>{ try{Object.defineProperty(navigator,'mediaDevices',{value:undefined,configurable:true});}catch{} const a={id,role:r,method:'phone-otp',contactHint:'Demo',demo:true,createdAt:new Date().toISOString()}; const raw=localStorage.getItem(k); const s=raw?JSON.parse(raw):{}; s.version=v; s.account=a; s.onboarding={completed:true,step:'welcome',choices:{}}; localStorage.setItem(k,JSON.stringify(s)); },['clss.web.store.v1','teacher',1,'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);
await p.goto('http://localhost:3210'+ROUTE,{waitUntil:'domcontentloaded',timeout:20000}); await p.waitForTimeout(2500);
await p.screenshot({path:'/tmp/shots/<name>.png'}); await b.close();
```
Then Read the PNG. To open the orb without deadlock: `dispatchEvent('click')` (NOT `.click()`), and keep `mediaDevices` removed.

## 7. DEPLOY (when ready — already validated once on `main`)
- **Railway backend** `classess-backend` (project `carefree-inspiration`/production): `RAILWAY_TOKEN` (project token) in `.env.local`; `railway up --service classess-backend --environment production`. Builds `backend/Dockerfile`, healthcheck `/health`.
- **Vercel web** (`3.classess.com`, project linked, CLI installed, `VERCEL_TOKEN` in `.env.local`): `vercel --prod --yes --token $VERCEL_TOKEN`. Env vars already set (incl. `CLSS_GATEWAY_URL`).
- **git push to main** needs `workflow` scope (the E2E CI file). Dev creds in use — rotate before public launch.
