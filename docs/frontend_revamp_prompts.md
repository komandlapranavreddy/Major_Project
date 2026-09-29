# EdgeLegal Frontend Revamp — Prompt Set

Drafted 2026-09-27. A set of separate, independently-buildable prompts for
Claude Code (or Antigravity) — hand them over one at a time, in order.
Ordered so each one builds on a working result from the last, and the
early ones are the fastest/lowest-risk.

**Stack reality check first** (so the prompts below don't waste time
re-discovering this): the frontend already has `react-router-dom`,
`framer-motion`, Radix UI primitives (`accordion`, `dialog`, `switch`,
`tabs`), `lucide-react`, and `next-themes` installed — plus a working
`theme-provider`/`theme-toggle` and a real `LandingPage.tsx` + `AppPage.tsx`
routed through `App.tsx`. None of that needs to be set up from scratch; the
gap is that almost none of it is actually *used* yet beyond the two
existing pages. Every prompt below leans on what's already installed
instead of adding new dependencies, except where called out.

---

## Prompt 1 — Premium visual polish + motion (fastest, do this first)

Uses the `impeccable` skill (`.claude/skills/impeccable/`). Paste as-is.

```
Use the impeccable skill for this whole task. This is a REFINEMENT pass on
the EdgeLegal frontend (frontend/src/), not a redesign: keep the current
visual identity, copy, and behavior. Only visuals and motion change.

Stack: React 19 + TypeScript + Vite + Tailwind. framer-motion, Radix UI,
lucide-react and next-themes (theme-provider.tsx / theme-toggle.tsx) are
already installed. Add NO new dependencies.

STEP 0 — impeccable setup
- Run impeccable's `context` launcher once (on Windows use
  .claude/skills/impeccable/scripts/impeccable.cmd).
- No PRODUCT.md or DESIGN.md exists yet. Run `/impeccable init` to write
  PRODUCT.md: EdgeLegal checks contracts for clause-level contradictions
  against a set of hypotheses (ContractNLI-style), using a small classifier
  with confidence-gated escalation to an LLM. Users: legal reviewers.
  Do not invent features, metrics or claims — ask me if unsure.
- Run `/impeccable document` to record the CURRENT look (index.css,
  tailwind.config.js, existing components) into DESIGN.md. Treat that as
  the incumbent visual truth for everything below.
- Surface modes: "/" LandingPage = Persuade. "/app" AppPage = Operate
  (scanability and task speed beat decoration there).

STEP 1 — `/impeccable animate` on App.tsx, pages/, components/
1. Page transitions: wrap <Routes> in App.tsx with AnimatePresence
   (keyed on location) so "/" <-> "/app" crossfades/slides, no hard cut.
2. AppPage.tsx: animate the flow upload -> hypothesis selection -> report
   with framer-motion layout animations; each panel enters as it becomes
   active.
3. Loading skeletons (CSS/Tailwind shimmer, no library) for ReportPanel
   while an analysis runs and PDFViewer while a document loads.
4. Micro-interactions: whileHover/whileTap on buttons and cards; subtle
   glow/border animation on the focused hypothesis in HypothesisPanel.tsx;
   an animated filling confidence meter wherever ReportPanel.tsx shows a
   confidence score (keep the number visible too).
5. Respect prefers-reduced-motion everywhere (framer-motion
   useReducedMotion / MotionConfig reducedMotion="user").

STEP 2 — `/impeccable polish` (visual refresh)
6. Add a small set of surface tokens/utilities in index.css (subtle
   gradients, soft shadows, backdrop-blur for panels/modals) and apply them
   to the main panels and cards for a less flat look. Record the new tokens
   in DESIGN.md. Must work in BOTH light and dark theme.
7. Follow impeccable's craft-floor bans (no generic AI-gradient slop, no
   glass on dense data areas where it hurts readability in Operate mode).

STEP 3 — `/impeccable audit` (quick, scoped to what changed)
8. Check contrast in both themes, focus states, keyboard nav, reduced
   motion, and that animations don't cause layout shift or jank.

HARD CONSTRAINTS
- Do NOT change API calls, data flow, state logic, or component
  props/interfaces. Purely visual + motion.
- Do not touch backend/ at all.

VERIFY (one bounded pass, per impeccable)
- `npm run build` and `npm run lint` in frontend/ must pass.
- Run `npm run dev`, check "/" and "/app" at desktop + mobile width, in
  light + dark: upload a PDF, select hypotheses, run an analysis. Fix
  everything found in one batch, confirm once, then stop.
- Finish with a short list of files changed and anything you couldn't
  verify.
```

---

## Prompt 2 — SQLite history layer + History page (new page)

```
Add persistent history to EdgeLegal: every analysis run gets saved, and a
new /history page lists past runs.

Backend (FastAPI, backend/app/):
1. Add a SQLite layer (this was already scoped in CLAUDE.md but never
   built): a `documents` table (id, filename, uploaded_at, page_count) and
   an `analyses` table (id, document_id FK, hypothesis, label, confidence,
   source ["classifier"|"llm"], created_at, report_json). Use SQLAlchemy or
   plain sqlite3 — whichever is faster to wire in given the rest of the
   codebase's style; check backend/app/schemas.py and main.py's existing
   patterns first and match them.
2. Wire persistence into the existing POST /analyze endpoint — every
   result it returns also gets written to the analyses table (don't
   change the response shape).
3. Add two new endpoints: GET /history (paginated list of past analyses,
   newest first, with document filename + hypothesis + label + confidence)
   and GET /history/{id} (full report for one past analysis, same shape
   POST /analyze returns so the frontend can reuse ReportPanel.tsx).

Frontend (frontend/src/):
4. New route /history (add to App.tsx same as the existing two routes),
   new page component pages/HistoryPage.tsx: a searchable/filterable list
   (filter by label, by document, by date) of past analyses, each row
   animated in with framer-motion (staggered fade/slide, matching Prompt
   1's motion language if that's already done). Clicking a row opens the
   full report using the existing ReportPanel.tsx component fed from
   GET /history/{id} — reuse it, don't rebuild it.
5. Add a "History" nav link/button visible from AppPage.tsx.
```

---

## Prompt 3 — Analytics dashboard (new page, product-facing)

```
Add an analytics/insights page to EdgeLegal that aggregates data from the
history endpoint built in the previous prompt — this is a product-facing
feature: something a legal team using this tool would actually want to see
across all the contracts they've checked, not just one at a time.

Backend:
1. Add GET /analytics (or compute client-side from GET /history if the
   dataset is small enough — decide based on how many analyses exist;
   either is fine, prefer server-side aggregation if it's not much extra
   work) returning: total documents analyzed, total contradictions found,
   contradiction rate (% of all clause/hypothesis checks that came back
   Contradiction), the most-frequently-flagged hypotheses (top 5, by
   count of Contradiction results), average classifier confidence, and
   the classifier-accept vs. LLM-escalate ratio (using the existing
   `source` field).

Frontend:
2. Add the `recharts` package (not currently installed — check it's
   compatible with the installed React 19 before adding).
3. New route /analytics, new page pages/AnalyticsPage.tsx: a dashboard
   grid of stat cards (use the same card/glass-panel styling from Prompt
   1) for the headline numbers, a bar chart of top-flagged hypotheses, and
   a donut/pie chart of classifier-accept vs. LLM-escalate ratio. Animate
   the stat cards counting up on load (framer-motion or a simple
   requestAnimationFrame counter) rather than just appearing with the
   final number.
4. Add an "Analytics" nav link alongside the "History" one from the
   previous prompt.
```

---

## Prompt 4 — Agent transparency panel (shows the actual routing decision)

```
EdgeLegal's backend routes each clause/hypothesis check through a
confidence-gated agent (backend/app/agent/ — retrieve -> triage ->
confidence_check -> accept or escalate to the LLM). Right now the frontend
doesn't show this decision process at all. Surface it, since it's the
actual mechanism the whole project is about and it's a genuinely
impressive thing to demo.

1. Confirm backend/app/schemas.py's ReportResult already carries `source`
   ("classifier" or "llm") and `confidence` per result — it does, per
   CLAUDE.md, but check it's actually populated end to end from
   agent/nodes.py through to the API response before building the UI
   against it.
2. In ReportPanel.tsx, for each result add a small expandable "How this
   was decided" section: if source is "classifier", show the triage
   label + confidence and a short "accepted — confidence above threshold"
   note; if source is "llm", show that it was escalated (confidence was
   below the frozen threshold), plus the LLM's reasoning/explanation text
   if the API returns one.
3. Style this as a small animated timeline/flow (retrieve -> triage ->
   [accept | escalate to LLM]) using framer-motion — a simple horizontal
   step indicator that highlights which path was taken for that specific
   result, not a generic static diagram repeated identically everywhere.
4. Keep this collapsed/secondary by default (a "Show reasoning" toggle per
   result) so the main report view stays clean — this is a power-user /
   demo feature, not the default view.
```

---

## Prompt 5 — Research page (helps the actual paper, not just the demo)

```
Add a /research page to EdgeLegal that visualizes the actual model
evaluation artifacts already produced for the paper — this is meant to
double as something you can screenshot directly for the write-up, and as
an impressive "we did real ML evaluation" page for anyone demoing the
product.

1. Backend: add a way to serve the evaluation artifacts as JSON — either a
   new GET /research/metrics endpoint reading from wherever
   verify_checkpoint.py / experiment_runner.py write their output
   (training_log.json, the calibration bin data, the threshold sweep
   table), or a static JSON file checked into the frontend if the backend
   route is more work than it's worth — pick whichever is faster given
   what already exists on disk.
2. Frontend: new page pages/ResearchPage.tsx (using recharts, added in
   Prompt 3) with three sections:
   - A reliability diagram (calibration curve): predicted confidence
     (x-axis) vs. actual accuracy (y-axis) per bin, with a dashed
     y=x reference line showing perfect calibration, using the real
     bin_confidences/bin_accuracies/bin_counts data.
   - The threshold sweep chart: coverage and macro-F1 as two lines across
     the swept tau values (0.60-0.95), with the frozen threshold (0.95)
     marked.
   - A Config A/B/C comparison table (accuracy, macro-F1, LLM-call count,
     latency) — leave this as a clearly-labeled "pending" placeholder if
     those experiments haven't been run yet, don't fabricate numbers.
3. Add a "Research" nav link. This page can be visually more restrained/
   technical than the rest of the app (it's for evaluators and the paper,
   not a sales pitch) — clean chart styling matters more than animation
   here.
```

---

## Optional / stretch — Multi-document comparison view

```
Only do this once Prompts 1-5 are done and if there's time left. Add a
/compare page: upload or select two already-analyzed documents (from
history) and show their flagged clauses for the same hypothesis set
side-by-side, so a user can visually spot where two contracts (e.g. a
template vs. a new draft) diverge on the same clause type. This is a pure
UI feature — it does NOT run real cross-document contradiction detection
(that's still a research/future-work item per literature_review.md's
"Future work" section), it's just presenting two existing single-document
analyses next to each other for manual comparison. Say so honestly if
asked — this is a UI convenience, not a new ML capability.
```

---

## Notes on ordering

Prompts 1-3 are pure frontend + one small backend addition (SQLite), safe
to do without touching the research pipeline at all. Prompt 4 needs the
agent's `source`/`confidence` fields actually flowing through end-to-end —
worth a quick manual check before handing that prompt over. Prompt 5 is
genuinely useful for the paper itself, not just the demo, so don't leave
it for last if the write-up deadline is tighter than the demo deadline.
