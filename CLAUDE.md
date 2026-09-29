# EdgeLegal — Context for Claude

Read this first, before exploring the repo. Last updated 2026-09-27 (evening)
by a Cowork session doing a full resync: read every file in the repo fresh
(not just this file's own history) because 3+ chats/sessions are working on
this in parallel — training pipeline, frontend, research — and none of them
reliably update this file when they finish. If something you built isn't
reflected here, that's why. Update this file before you end your session.

Last updated 2026-09-29 by the Claude Code session working from the
`major project/` folder (VS Code): corrected the Frontend / live-pipeline
sections below with who built what and what was actually tested, marked
`dev_eval_results.json` as generated, and logged the matched Config A/B/C
run under "Experiment runs".

## What this project is

A research project (thesis-style), not just an app. Core question: can a
small fine-tuned NLI classifier (DeBERTa-v3-small or LegalBERT) act as a
confidence-gated triage layer in front of a local LLM for legal
contradiction detection, escalating only uncertain cases — cutting LLM calls
without hurting accuracy, and only if its confidence is actually calibrated?

Full plan: `EdgeLegal_Project_Guide.md` (scope, architecture, the 3 required
experiment configs A/B/C, metrics, definition of done — this is the source
of truth for scope). `EdgeLegal_Implementation_Summary.md` claims ~40%
complete; that number is optimistic — see "Actual state" below.

Dataset: ContractNLI (607 NDAs, 17 fixed hypotheses, Entailment /
Contradiction / NotMentioned). Already downloaded at
`backend/data/contractnli/{train,dev,test}.json` (423/61/123 contracts).

## Actual state — the two-pipeline problem is RESOLVED (2026-09-27)

This used to be the biggest open architectural problem in this file. It
isn't anymore — someone (not this session) wired the real agent into the
live app. Keeping the history because the "why" still matters:

**Research/eval pipeline** (unchanged): `backend/app/parsing/clause_parser.py`
(structure-aware clause segmentation), `embeddings/embedder.py`
(BAAI/bge-small-en), `vectorstore/chroma_client.py` (adaptive gap-filter
retrieval: keep rank-1, drop anything with a >15% relative distance jump),
`llm/ollama_client.py` + `llm/prompts.py` (multi-clause JSON prompting,
local Ollama only for paper numbers, greedy decoding). Exercised by
`test_pipeline.py`, `retrieval_accuracy_check.py`, and now
`experiment_runner.py` (see the new section below on that).

**Live app pipeline — NOW UNIFIED with the research pipeline**:
`main.py` no longer imports `rag_engine.py` at all. It now goes through
`backend/app/agent/live_service.py` (new file), which runs the *same*
`agent/graph.py` state machine (retrieve → triage → confidence_check →
accept/call_llm) that the research pipeline and `experiment_runner.py` use —
same `clause_parser.py` segmentation, same bge-small embedder, same
gap-filter retrieval, same triage classifier, `FROZEN_THRESHOLD = 0.95`
hardcoded in `live_service.py` (kept in sync with
`experiment_runner.FROZEN_THRESHOLD` by convention, not import — it's a
plain constant since a long-running web server shouldn't import a CLI
script). Only the LLM transport differs: live app still uses Groq
(`GroqAgentClient`, adapts `groq_client` to the same `.query_llm()`
interface `OllamaClient` exposes) for demo speed — intentional, same
reasoning as the LLM provider switch section below. `document_processor.py`
and `rag_engine.py` are now dead code — nothing imports them. Don't delete
them without checking nothing external still depends on them, but don't
extend them either.

Practical effect: the live demo now runs the actual thesis mechanism
(confidence-gated triage, real routing decisions, real citations from the
clause the classifier/LLM actually saw) instead of a disconnected toy
pipeline. `ReportPanel.tsx`'s `DecisionTrail` component (see Frontend
section below) now shows something real.

Details worth knowing (from the session that built it, 2026-09-27):
- `live_service.py` puts the project root on `sys.path` so the
  `backend.app.*` agent imports work inside the `app.*` live server — it
  does NOT change either import convention.
- Live documents are indexed into a separate persistent Chroma store,
  `backend/live_chroma_db/` (gitignored), one collection per upload
  (`live_<doc_id>`). The research pipeline's own collections are untouched.
- `agent/nodes.py`, `agent/state.py`, `agent/graph.py` were NOT modified —
  `live_service.py` only reads keys the graph already sets
  (`retrieved_clauses`, `triage_label`, `triage_confidence`,
  `routing_decision`, `source_engine`, `final_label`, `reasoning_text`,
  `cited_clauses`). Confirmed `experiment_runner.py` doesn't read
  `cited_clauses`, so nothing in the eval pipeline is affected.
- `ReportResult` gained an additive `triage` field (`TriageDetail`:
  `label`, `confidence`, `threshold`, `decision`) for the decision-trail
  panel. `confidence` keeps its old meaning (set only when
  `source == "classifier"`).
- Citations come from `clause_parser.Clause`, which has a page number but
  no bbox — so clicking a citation jumps to the right PDF page but shows no
  highlight box. Adding bbox capture to `clause_parser.py` is a possible
  follow-up.
- Tested end-to-end via FastAPI `TestClient` with the real checkpoint:
  accept path (e.g. "Governing law is New York" → Contradiction, correctly
  citing the Delaware clause) and the escalate path (threshold forced up for
  the test only → real Groq call, including a real 429 rate-limit + key
  rotation recovery).

## Triage classifier — TRAINED, INTEGRATED, VERIFIED (2026-09-27)

Pranav's checkpoint (`cross-encoder/nli-deberta-v3-base`, warm-started from
its native NLI head rather than a random 3-class head) is trained,
integrated, and confirmed correct end-to-end. This is the actual thesis
mechanism — no longer a stub.

- **Checkpoint**: `backend/app/triage_model/checkpoints/current/best_model.pt`
  (raw `state_dict`, ~738MB, fp32). Trained on Kaggle (T4 GPU), 3 epochs,
  early-stopped on macro-F1 (patience=2), batch 32, lr 2e-5.
- **Dev-split results** (ContractNLI, 1037 examples): accuracy **0.9701**,
  macro P/R/F1 **0.9305 / 0.9486 / 0.9391**. Per-class F1: Entailment
  0.9699, NotMentioned 0.9988, **Contradiction 0.8485** (weakest — it's the
  minority class at ~9% of data, and the one the whole project is about, so
  this number matters more than the headline accuracy).
- **Calibration**: ECE (10 bins) = **0.0285** on dev — well-calibrated
  *on dev premises only*. **CONFIRMED BROKEN in deployment conditions
  (2026-09-27) — this is now a blocker, not a suspicion.**

  Measured for real: `run_experiment("C_finetuned_triage", ...)` on 20 real
  test documents (340 pairs) with a fake LLM client (zero API cost, only the
  triage model runs), scoring `triage_label`/`triage_confidence` against
  gold via `ResultsDict.triage_calibration()`. Full numbers + reasoning:
  https://wandb.ai/katta-saimanideep-gokaraju-rangaraju-institute-of-engine/edgelegal
  (see the "CRITICAL" report). Headline:

  | Metric | Dev (gold spans) | In-pipeline (real retrieval) |
  |---|---|---|
  | Accuracy | 0.9701 | **0.5324** |
  | Macro-F1 | 0.9391 | **0.4796** |
  | ECE | 0.0285 | **0.4396** |
  | Coverage @ τ=0.95 | 98.4% | 89.1% |

  The damning number: at confidence ≈0.994 (309 of 340 pairs), in-pipeline
  accuracy is **55%** — a coin flip at the exact confidence level used to
  justify skipping the LLM. At the frozen threshold, 89.1% of real pairs
  would still be silently accepted.

  Leading cause (not yet isolated further): `dataset.py` gives
  Entailment/Contradiction a short evidence-span premise but gives
  NotMentioned the *full document* instead — likely teaching the model to
  key off premise length/structure, a cue that's completely absent in
  deployment (every premise is one short retrieved clause). All three
  classes collapsed in-pipeline, not just NotMentioned, so there may be more
  to it than this one cause.

  **DO NOT run Configs A/B/C for numbers that go in the paper on this
  checkpoint** — the comparison would be measuring a broken classifier.
  This is a legitimate, reportable finding either way, not a failure of the
  project (Project Guide §6.3: negative results are still results) — but it
  has to be reported as "we checked calibration and it failed under
  deployment conditions," not skipped past.

  **Second cause found (2026-09-27, same session): retrieval itself has a
  real gap, independent of the classifier.** Ran
  `retrieval_accuracy_check.py` (zero LLM, zero classifier — full 123-doc
  test split, 1188 real Entailment/Contradiction cases): the gold evidence
  clause is only included in the gap-filtered retrieval set **73.1%** of the
  time (Entailment 72.7%, Contradiction 74.5%). In the other **27%**, the
  classifier is scored against the wrong clause entirely — no amount of
  retraining fixes that, since the input itself is wrong. This is a hard
  ceiling on triage accuracy independent of the NotMentioned-premise issue
  above.

  **Two separate fixes needed, not one:**
  1. Retrain the classifier with deployment-realistic premises (retrieved-
     style clauses, not gold spans) for every class, including NotMentioned
     — addresses the train/inference mismatch.
  2. Improve retrieval's 73%→higher inclusion rate — separate problem.
     Candidates worth checking before assuming a fix: is the 15%
     `GAP_THRESHOLD` in `chroma_client.py` too aggressive (cutting off the
     correct clause in favor of a closer-but-wrong one)? Is `bge-small-en`
     precise enough for legal phrasing, or does hybrid dense+BM25 retrieval
     help here specifically (this is the one place that idea is now
     justified by measured data, not by novelty-chasing — see the earlier
     research-scope discussion for why it was rejected as a general
     direction)?

  Retraining the classifier alone caps out around ~73% regardless of
  training quality until retrieval also improves. **Re-run both this
  in-pipeline triage check AND `retrieval_accuracy_check.py` after any fix**
  before touching Configs A/B/C again.
- **Frozen threshold**: tau = **0.95**, selected on the dev split only
  (never touched test) — 98.4% coverage, macro-F1 0.9511 among kept cases.
  Full sweep (0.60-0.95) logged in git history of this file / see
  `verify_checkpoint.py`'s output.
- **Files**:
  - `backend/app/triage_model/model.py` — `TriageModel`, warm-started from
    `cross-encoder/nli-deberta-v3-base`'s own 3-class NLI head (not a fresh
    random head — the checkpoint's native `id2label` is reused directly).
    `.load(checkpoint_path, device)` loads the fine-tuned `state_dict` on
    top of that architecture; `.predict(premise, hypothesis) -> (label,
    confidence)`.
  - `backend/app/triage_model/dataset.py` — `ContractNLIDataset`,
    `LABEL2ID`/`ID2LABEL`, `compute_class_weights()`. **Label order is
    Contradiction=0, Entailment=1, NotMentioned=2** — matches the
    checkpoint's native head order, NOT alphabetical or the order named in
    `architecture123.md`'s prose. Premise = concatenated evidence-span text
    when spans exist; falls back to the full (tokenizer-truncated) document
    text when they don't (always true for NotMentioned in this dataset —
    verified: all 423 dev NotMentioned examples have empty `spans`). This
    fallback was reverse-engineered by testing against the real checkpoint
    until dev-set numbers matched Pranav's Kaggle run exactly — see
    `verify_checkpoint.py`.
  - `backend/app/triage_model/train.py` — Pranav's training loop
    (class-weighted cross-entropy, linear warmup, grad accumulation, F1
    early stopping). `python -m backend.app.triage_model.train --smoke` for
    a 2-3 min CPU sanity check.
  - `backend/app/triage_model/evaluate.py` — `evaluate(model, dataloader,
    device)`, `compute_calibration(confidences, correct)`,
    `select_threshold(model, dataloader, device)`,
    `_collect_predictions(...)`. Signature takes a model + dataloader
    directly (not `(predicted, gold)` label lists as `architecture123.md`
    originally sketched) — matches what `kaggle_train.ipynb` actually calls.
  - `backend/app/triage_model/infer.py` — `predict(clause, hypothesis) ->
    (label, confidence)`. Fixed 2026-09-27: previously checked
    `os.path.isdir()` and imported a nonexistent `LABELS` tuple with the
    WRONG order (Entailment=0) — would have silently swapped
    Entailment/Contradiction predictions. Now checks `os.path.isfile()` on
    `TRIAGE_CHECKPOINT_PATH` (defaults to
    `triage_model/checkpoints/current/best_model.pt`) and delegates
    directly to `TriageModel.predict()`.
  - `backend/app/triage_model/verify_checkpoint.py` — one-off script that
    reproduced Pranav's exact Kaggle numbers locally (CPU) as a
    correctness check before trusting any of the above. Not part of the
    runtime path; keep for future re-verification if the checkpoint or
    preprocessing changes.
- **Still using the stub**: none of the above changes `infer.py`'s
  lexical-overlap fallback behavior — it's now simply unreachable in normal
  operation since a real checkpoint exists at the default path. Left in
  place as a safety net if `TRIAGE_CHECKPOINT_PATH` is ever unset/missing.

**Config definitions (decided 2026-09-27):**
- **A** — retrieval → LLM directly. Triage never runs: no classifier
  latency, no triage pre-label in the prompt. The earlier design ran A
  through the full graph with an unreachable threshold, which ran triage
  on every pair AND injected its guess into A's prompts — contaminating
  the baseline and inflating A's latency (which flattered B/C). Fixed via
  a `skip_triage` edge in `agent/graph.py`. Any Config A number produced
  before this fix (e.g. the 72.5% 3-doc Groq smoke run) is not clean.
- **B** — raw `cross-encoder/nli-deberta-v3-base`, zero ContractNLI
  fine-tuning (`TRIAGE_CHECKPOINT_PATH=pretrained`; the runner's default for
  B). Its native head order matches LABEL2ID index-for-index — verified
  against the HF config. Same architecture as C, so B vs C isolates the
  effect of domain fine-tuning. NOTE: the Project Guide's literal wording
  for B was "an existing pretrained ContractNLI checkpoint (e.g.
  Span-NLI-BERT)". This is a generic-NLI baseline instead — defensible
  (it's also what LegalWiz uses: off-the-shelf bart-large-mnli), but say
  so explicitly in the write-up.
- **C** — the fine-tuned checkpoint at the default path.

`python -m backend.app.experiment_runner --configs A B C` now needs no
checkpoint flags. The runner resolves each config's checkpoint per run
(never from the previous run's env var), so B then C in one process can't
leak B's model into C.

## Experiment runs — Config A/B/C smoke-scale results exist (2026-09-27), NOT paper-grade

`experiment_runner.py` has actually been run now — 4 result files sit in
`results/` (`A_no_triage_*.json`, `B_pretrained_triage_*.json`,
`C_finetuned_triage_*.json` x2). Every one has `"paper_grade": false` and
`"llm_provider": "groq"` — correctly self-flagged as not usable for the
paper (per the LLM provider switch rule below: Groq numbers never go in the
paper). The calibration collapse these runs exposed is written up in full
under "Triage classifier" above (with a wandb link) — someone was editing
that section into a much better version of what this session first found,
literally while this resync was in progress, so don't duplicate it here.
What's still worth flagging separately:

- **Tiny, uneven samples**: A and B ran on 2 documents (34 pairs) each; C
  was run twice, once at 2 docs and once at 20 documents (340 pairs). None
  of these touch the real 123-contract test split. These 4 files can't be
  paired for McNemar — see the matched run below.
- **`/research` now reads real `results/*.json` (2026-09-29, another
  session)**: `research.py`'s `get_research_metrics()` loads the newest run
  per config; `ConfigResult` gained `paper_grade`, `n_pairs`,
  `errored_pairs`, `run_at` (Python + TS types in sync). The page shows two
  guard banners (non-paper-grade / split mismatch). Right now the newest C
  run (340 pairs) doesn't match A/B (34 pairs), so the mismatch banner
  fires — it goes away once A/B/C are re-run together in one invocation on
  the same split. Not verified by this session beyond reading the code.
- `backend/app/triage_model/dev_eval_results.json` — **generated
  2026-09-27**. `verify_checkpoint.py` now also writes this file (it used
  to only print). One real CPU inference pass over the full dev split (1037
  examples, ~15 min) reproduced the Kaggle numbers exactly: accuracy
  0.9701, macro-F1 0.9391, ECE 0.0285, sweep choosing τ=0.95. `/research`
  renders it. This is the **dev-premise** calibration only; it does not
  contradict the deployment-calibration failure above.

### Matched 20-doc A/B/C run — PRELIMINARY, not paper-grade (2026-09-29)

**Status: IN PROGRESS** (started 2026-09-29 07:01 IST). Command, from
`EdgeLegal_CodeBase/` with `backend/venv`:
`python -m backend.app.experiment_runner --configs A B C --limit 20`.
All three configs run on the same first 20 test documents (340 pairs each)
so they can be paired for McNemar. Groq is the LLM (`LLM_PROVIDER=groq`),
so every file is self-flagged `paper_grade: false`. Groq's shared 8k
tokens/minute org limit causes constant 429 retries. Pairs that exhaust
their retries are recorded as `error` rows: accuracy/ECE exclude them, but
`compute_significance()` would count them as wrong. So McNemar will be
reported two ways: on the pairs clean in all 3 configs (primary), and on the
raw files. Results and the significance numbers go here when the run
finishes. Paper numbers still need the full 123-doc test split,
`--repeats`, and Ollama.

## What's NOT built yet

Still genuinely missing:
- **A real, paper-grade Config A/B/C run**: full ContractNLI test split
  (123 contracts), local Ollama (not Groq), `--repeats` for the resource
  metrics variance the Project Guide asks for. The smoke runs above prove
  the plumbing works end-to-end; they are not results.
- Fix (or at least characterize) the deployment-calibration gap above
  before any paper-grade Config C run, or the headline calibration claim
  won't survive review.
- McNemar significance testing between configs — implemented in
  `experiment_runner.py`; a preliminary matched 20-doc run is in progress
  (see "Experiment runs"). Not yet run on the full test split.

Frontend (`frontend/`) is now well beyond what the plan called for at this
stage — see the new Frontend section below for the full rundown (history,
analytics, research, and decision-trail pages all now exist).

## Housekeeping / gotchas

- Only one git commit ("Initial Commit"); everything since is uncommitted.
  `chroma_db/` and `__pycache__/` got tracked before `.gitignore` excluded
  them, so `git status` is noisy with binary diffs — clean this up
  (`git rm -r --cached backend/chroma_db backend/app/**/__pycache__`) before
  the next real commit.
- `backend/.env` holds real Groq keys (gitignored correctly) — never print
  or commit its contents.
- Planned folder layout in the Project Guide nests everything under
  `edgelegal/backend/...`; actual repo has `backend/` at root with no
  `edgelegal/` wrapper. Non-issue, just don't be confused by path mismatches
  when reading the docs literally.
- `backend/app/triage_model/checkpoints/current/PARTIAL_DELETE_ME.pt`
  (~101MB leftover partial-copy artifact) is STILL sitting there as of
  2026-09-27 evening — needs manual deletion (Cowork's device bridge can't
  delete without explicit permission). The root-level `best_model.pt` stub
  from the same incident has since been cleaned up.
- `kaggle_training/` (new top-level folder) holds a second copy of
  Pranav's `train.py`/`model.py`/`kaggle_train.ipynb` and the checkpoint
  zip. It's an archival copy of the original files he sent, kept separate
  from the live `backend/app/triage_model/` copies. Don't edit the
  `triage_model/` copies and forget this one exists, or vice versa.
  (Created 2026-09-27 during a folder cleanup that moved these files from
  the repo root. The same cleanup created `pdfs/`, `scripts/`, and moved
  the loose root `.md` files into `docs/`. The ~840MB `best_model.pt.zip` +
  extracted folder in `kaggle_training/` duplicate the real checkpoint and
  can be deleted if space matters.)
- New top-level `pdfs/` (demo contract + hypotheses PDFs) and `scripts/`
  (`generate_demo_contract.py`, `generate_playbook.py`) - demo-data
  generation utilities, not part of the app or eval pipeline.
- `.claude/agents/frontend-engineer.md`, `backend-engineer.md`,
  `research-lead.md` added 2026-09-27 for an experimental Claude Code
  "agent teams" setup (each scoped to one workstream, told to read this
  file first and update it when done) - not yet actually tried, sitting
  ready if wanted.
- `DESIGN.md`, `PRODUCT.md`, `.impeccable/`, `skills-lock.json` - artifacts
  of the `impeccable` design-guidance skill (color tokens, product schema)
  used while building the frontend revamp. Reference material, not runtime
  code.

## Publication target

This project is expected to produce two Scopus-indexed publications: one
conference paper and one journal paper. This shapes scope and sequencing —
see the Project Guide's Sections 6-9 for what content each write-up needs
(claim framing, required metrics, calibration, limitations, definition of
done). Likely split: conference paper covers the core system + Configs A/B/C
on ContractNLI; journal paper extends it with material the conference
version won't have room for (deeper calibration analysis, more ablations,
possibly a second contract-type dataset) — journals generally expect
~30%+ new material over a prior conference version, not a resubmission of
the same content. No venues have been chosen yet.

## LLM provider switch (added 2026-09-25)

Decision: use Groq now for speed (no Ollama installed on the dev laptops,
no GPU, 12-16GB RAM), switch to local Ollama before generating the final
numbers that go into the paper. This is intentionally risky if done
casually (easy to accidentally submit Groq-sourced "local" results), so it's
now enforced explicitly rather than left implicit:

- `backend/app/llm/ollama_client.py` (used by `test_pipeline.py` and
  therefore by any paper numbers) previously silently switched to Groq
  whenever `.env` had Groq keys present - this was a real landmine, since
  Groq keys are needed for the demo app anyway, so the eval pipeline was
  ALREADY silently running on Groq without anyone deciding that on purpose.
  Fixed: it now only uses Groq when `LLM_PROVIDER=groq` is explicitly set in
  `.env`; unset or anything else uses real local Ollama. `is_reachable()`
  follows the same rule. A loud print statement flags every Groq call as
  "not local/private - do not use as final evaluation numbers."
- `backend/app/rag_engine.py` (the live demo app) is UNCHANGED - it still
  auto-prefers Groq whenever keys exist, regardless of `LLM_PROVIDER`. This
  is fine and intentional: the demo's job is to be fast, not to produce
  paper numbers, so it doesn't carry the same risk.
- `.env` currently has `LLM_PROVIDER=groq` (matches current dev plan).
  `.env.example` documents the flag with `LLM_PROVIDER=ollama` as the
  template default, since that's the safe default for anyone cloning fresh.

**Before generating any number that will appear in the paper**: install
Ollama (no GPU needed, ~5-10 min, works fine on 12-16GB RAM with a small
model like Llama 3.2 3B or Phi-3-mini given the CPU latency budget), pull
the model `test_pipeline.py` expects (currently `llama3.1:8b` - consider
swapping to a smaller model given team hardware, but that's a separate
decision), then remove or flip `LLM_PROVIDER` in `.env` to `ollama` and
re-run the full eval suite. Do not report Groq-sourced numbers as the
paper's results under any circumstances - it breaks both the privacy claim
and the efficiency argument the triage layer is supposed to demonstrate
(Groq is cloud-GPU-fast, so it can't show the cost the triage layer exists
to cut).

## Literature review (added 2026-09-25)

See `researchpaper_claude/literature_review.md` for a full gap analysis against current
publications (searched arXiv, ACL Anthology, IEEE Xplore, ACM DL, SpringerLink). Short
version: the core triage mechanism isn't novel in the abstract (LLM cascades exist, and
one legal-specific paper - LegalWiz, Oct 2025 - already does NLI-confidence-gated
escalation to an LLM for legal contradiction detection). The genuine, still-open gap is
combining that mechanism with an explicit calibration check (ECE), on the standard
ContractNLI benchmark specifically, with the full A/B/C comparison - nobody has done
that combination yet. Read `researchpaper_claude/notes/03-legalwiz-CLOSEST-COMPETITOR.md`
before writing related work. One paper could not be accessed
("Multi-Agent Orchestration of Local LLMs for Contract Review under Resource
Constraints", ACM ICBAR 2025) and is flagged as a priority follow-up - closest title
match found, contents unverified.

## Future work — multi-layer contradiction detection (added 2026-09-26)

Scoped for the **journal paper**, not the conference paper above — do not start until
Configs A/B/C + calibration are done. Idea: extend beyond single-document
hypothesis-vs-clause checking to also catch (1) clause-vs-clause contradictions within
the same document, and (2) clause-vs-clause contradictions across different documents
(e.g. a new contract vs. a template, or a base agreement vs. an amendment), unified by an
agent (LangGraph) that runs whichever check(s) apply and merges the results. Confirmed via
search: within-document has reusable prior art/data (Better Call CLAUSE, EACL 2026), but
no dataset exists yet for cross-document contract contradictions — cheapest fix is
deriving pairs from ContractNLI's own hypothesis labels (two contracts, same hypothesis,
opposite label = a free contradiction pair). Full writeup:
`researchpaper_claude/notes/09-multilayer-contradiction-future-work.md` and the "Future
work" section in `researchpaper_claude/literature_review.md`.

## Frontend — fully revamped (2026-09-27)

All 5 prompts in `docs/frontend_revamp_prompts.md` are built. They were built
and tested by the Claude Code session working from `major project/` (VS Code),
using the `impeccable` design skill for Prompt 1 (it produced `PRODUCT.md` /
`DESIGN.md`) and the `dataviz` skill for chart colors. A Cowork resync first
documented this without knowing who built it; corrected here.

**Routing & shell**: `App.tsx` now has 5 routes — `/` (landing), `/app`
(analyze), `/history`, `/analytics`, `/research` — each wrapped in a
`PageFade` (opacity only, because a transform would break the landing
navbar's `position: fixed`). `AppHeader.tsx` is a shared nav bar
(Analyze / History / Analytics / Research). On phones it hides "Back to
site"; the logo still links home. `lib/design.ts` centralizes motion easings
(`easeOut`) and shared panel styles (`panelSurface`). `lib/api.ts` holds
`API_BASE` = `VITE_API_URL` or `http://localhost:8000`. Set `VITE_API_URL`
when deploying the frontend to Vercel with the backend on Render.
`lib/verdict.ts` holds shared verdict colors/icons.

**Prompt 1 (motion/polish)**: step rail in the `/app` header, glow on the
active panel, skeleton loaders, the verdict "blur-to-sharp" reveal plus an
animated confidence bar, a spinning ring on the hypothesis being checked,
and `prefers-reduced-motion` support. Also a real bug fix in
`PDFViewer.tsx`: pages now fit the column via a `ResizeObserver`, and the
citation highlight uses the same render scale. Before this, the highlight
landed in the wrong place in narrow columns (History, mobile).

**History (Prompt 2)**: `backend/app/history_db.py` - SQLite (`documents` +
`analyses` tables, DB at `backend/edgelegal_history.sqlite3`, path
overridable via `EDGELEGAL_HISTORY_DB`). `init_db()`, `record_document()`,
`record_analysis()`, `list_analyses()` (filters: limit/offset/label/
document_id/q/since), `list_documents()`, `get_analysis()`, `get_analytics()`
(used by `/analytics`, see below). Wired into `main.py`: `/upload` records a
document, `/analyze` records an analysis. Endpoints: `GET /history`,
`GET /history/documents`, `GET /history/{analysis_id}`,
`GET /documents/{doc_id}/file`. New schemas: `HistoryItem`, `HistoryPage`,
`HistoryDocument`, `Analytics`. Frontend: `pages/HistoryPage.tsx`.

**Analytics dashboard (Prompt 3)**: `GET /analytics` -> `history_db.
get_analytics()` (documents analyzed, total analyses, contradiction rate,
avg classifier confidence, classifier-vs-LLM call split, top 5
most-contradicted hypotheses). Frontend: `pages/AnalyticsPage.tsx`, using
`recharts` (newly added to `package.json`) for the bar chart, `StatTile.tsx`
for the KPI cards, colors picked via the `dataviz` skill's palette
validator (documented inline in the file).

**Agent transparency panel (Prompt 4)**: `ReportPanel.tsx` now has a
`DecisionTrail` component showing the real retrieve -> triage ->
confidence_check -> accept/escalate path per result (which engine resolved
it, the triage confidence and threshold, accept vs. escalate). This is now
showing real data because of the live-pipeline unification above - it
would have had nothing meaningful to show before that.

**Research page (Prompt 5)**: `backend/app/research.py` serves
`GET /research/metrics`. It reads real artifacts only, with no fabricated
numbers. It reads `dev_eval_results.json` (now generated, see "Experiment
runs") for the stat tiles, reliability diagram and threshold sweep. Config
A/B/C is still hard-coded `"pending"` because `results/*.json` isn't wired
in. Frontend: `pages/ResearchPage.tsx`:
- The reliability diagram draws each bin as a dot sized by example count,
  with no connecting line: 1027 of the 1037 dev examples sit in one bin, so
  joining the 1–5-example bins with a line looked like wild miscalibration.
- The threshold-sweep y-axis zooms to 90–100% so the coverage vs macro-F1
  trade-off is visible.
- If you start the backend without `--reload`, restart it after backend
  edits, or `/research/metrics` will 404 even though the code is there.

**Design system artifacts**: `DESIGN.md` (color tokens, night/paper theme
values) and `PRODUCT.md` (platform/users/purpose) were generated via the
`impeccable` skill installed earlier - reference material for whoever
touches the frontend next, not runtime code.

**How it was verified**:
- `npm run build` + `npm run lint` pass. The 8 remaining oxlint warnings
  are old ones in landing/theme files.
- Backend history/analytics tests were written and run with FastAPI
  `TestClient`. They cover filters, search escaping, pagination,
  path-traversal on `/documents/{id}/file`, and the empty-DB analytics case.
- Every page was screenshotted with Playwright (real Chrome) at desktop and
  mobile sizes, in dark and light themes, with no console errors. These runs
  used a real backend (with RAG stubbed or with the real agent) and checked
  empty, loading, error and populated states.
- The decision trail was checked against the real agent for the accept
  path; for the escalate branch the `/analyze` response was mocked. Not a
  test suite checked into the repo — the test scripts were one-off.

**Frontend-adjacent gotchas**:
- Stopping a backgrounded `npm run dev` on Windows can leave the child
  `node` process holding the port. Check `netstat -ano | findstr 5173` and
  kill the PID.
- `backend/.env` must have `GROQ_API_KEYS` for the live `/analyze` escalate
  path.

## Claude Code tooling (added 2026-09-25)

Added `.mcp.json` at repo root (project-scoped MCP servers, requires one-time
approval the first time you open an interactive Claude Code session in this
folder — it'll prompt you):
- `context7` — up-to-date library docs for fast-moving deps (React 19, Vite,
  FastAPI, shadcn/ui) instead of relying on stale training data. No API key
  needed to start; get a free one at context7.com if you hit rate limits.
- `playwright` — browser automation, for verifying frontend fixes (bbox
  coordinate math, batch-report list) and screenshotting the landing page.
- `chroma` — lets a Claude Code session query the actual ChromaDB collection
  directly (pointed at `backend/chroma_db`) instead of writing throwaway
  debug scripts. Requires `uv`/`uvx` installed (`pip install uv` if missing).
- `huggingface` — for pulling/searching DeBERTa-v3-small / LegalBERT-base
  checkpoints when the triage-classifier fine-tuning work starts. Optional
  `HF_TOKEN` env var for private/rate-limited access.

NOT auto-installed for you (Claude Code plugins can't be silently installed
into a repo the way MCP servers can — the project-scope `enabledPlugins`
mechanism is confirmed flaky per Anthropic's own open GitHub issues, so this
was deliberately left manual): run these once inside an interactive Claude
Code session, ~10 seconds each —
`/plugin install commit-commands@claude-plugins-official`,
`/plugin install claude-md-management@claude-plugins-official`,
`/plugin install code-review@claude-plugins-official`,
`/plugin install frontend-design@claude-plugins-official`.

Not set up (deferred, no confident config found / not needed yet): Kaggle's
official MCP server (exists, exact CLI invocation unconfirmed as of this
search — check kaggle.com's MCP docs directly when the fine-tuning work
starts), a SQLite MCP server (pointless until the SQLite persistence layer
actually exists), GitHub's official MCP (redundant with `commit-commands`
for a solo/small-team project).

## Working conventions

- **Two different import roots for the two pipelines — this tripped up a
  session on 2026-09-26, worth being deliberate about:**
  - Research/eval pipeline (`chroma_client.py`, `ollama_client.py`,
    `test_pipeline.py`, `retrieval_accuracy_check.py`, and the new
    `triage_model/`/`agent/`/`experiment_runner.py`) all import via
    `from backend.app.xxx import yyy` — these must be run with
    **`EdgeLegal_CodeBase/` as the working directory** (not `backend/`),
    e.g. `cd EdgeLegal_CodeBase && python -m backend.app.test_pipeline` /
    `python -m backend.app.retrieval_accuracy_check` /
    `python -m backend.app.experiment_runner`. (Confirmed by actually
    running the imports — `backend.app.x` genuinely fails from `backend/`
    as cwd; this is not a hypothetical.)
  - Live app (`main.py`, `rag_engine.py`, `document_processor.py`,
    `groq_client.py`) imports via `from app.xxx import yyy` and is run with
    **`backend/` as the working directory**, as before:
    `cd backend && uvicorn app.main:app --reload`.
  - The two pipelines never import each other, so this split doesn't
    actually break anything at runtime — it was just undocumented.
- Frontend, unchanged: `cd frontend && npm run dev`.
- Never tune the confidence threshold against the test split (Project
  Guide Section 6.3) — validation split only, frozen before test eval.
- To swap in a real triage checkpoint once trained: drop it at
  `backend/app/triage_model/checkpoints/current/`, or point
  `TRIAGE_CHECKPOINT_PATH` at wherever it actually lives — no code changes
  needed, `triage_model/infer.py` picks it up automatically.
- Keep this file updated as milestones land — update "Actual state" and
  "What's NOT built yet" rather than letting them drift out of sync with
  the code.

## Logging & debugging (added 2026-09-29)

Before this, the codebase was print()-only (Groq rate-limit messages, Ollama
routing warnings, experiment progress) plus a couple of unconfigured
`logging.getLogger(__name__)` calls in main.py that did nothing below
WARNING and never touched disk. A crash 40 minutes into an experiment run
left no record of the preceding 39 minutes once the terminal scrolled past
it; a live-app 500 gave the client `str(e)` with no server-side trace.

`backend/app/logging_config.py` is the shared setup now, used by both
pipelines (research imports it as `backend.app.logging_config`, the live
app as `app.logging_config` — same file, see "Working conventions" above
for why there are two import roots). Every log line lands in
`EdgeLegal_CodeBase/logs/edgelegal.log` (rotating, 10MB x 5 backups) at
DEBUG regardless of console verbosity, so a run's full detail survives
even if the console was quiet or scrolled past.

- `get_logger(__name__)` — standard logger, auto-configures on first call.
- `log_step(logger, "stage.name", **context)` — one line per pipeline stage
  (retrieve -> triage -> route -> accept/escalate; upload -> parse ->
  index; etc.) with the inputs that mattered, so a failure's log context
  reconstructs the exact sequence that led up to it.
- `log_exception(logger, "what failed", **context)` — call from inside an
  `except` block; always logs the full traceback (`exc_info=True`) plus
  structured context (doc_id, hyp_id, config, ...), never just `str(e)`.
- `EDGELEGAL_LOG_LEVEL` env var (or `--log-level` on `experiment_runner.py`)
  controls console verbosity; the file always captures DEBUG regardless.

Instrumented so far: the whole agent graph (`agent/nodes.py` logs every
routing decision — retrieval count, gap-filter keep count, triage
label/confidence, threshold comparison, accept-vs-escalate, LLM result),
`triage_model/infer.py` + `model.py` (checkpoint load path, predict calls),
`llm/ollama_client.py` + `llm/groq_client.py` (every LLM call, the JSON
parse-failure fallback that used to silently default to NotMentioned,
Groq's rate-limit/rotation behavior), `parsing/clause_parser.py` +
`embeddings/embedder.py` + `vectorstore/chroma_client.py` (parse/embed/
retrieve/gap-filter steps, and the "0 clauses out of a scanned PDF" failure
mode that previously had no diagnostic at all), `agent/live_service.py` +
`main.py` (upload/analyze request lifecycle, plus a FastAPI middleware
that logs and traces ANY unhandled exception in ANY route — including ones
in `history_db.py`/`research.py`, which have no try/except of their own —
instead of letting it fall through to a bare unlogged 500),
`experiment_runner.py` (per-pair failures no longer kill the whole run —
recorded as an explicit `error` field, excluded from accuracy/ECE/latency
rather than silently counted as wrong, with the full traceback logged).

Gotcha worth knowing: `clause_parser.py`, `embedder.py`, `chroma_client.py`,
`groq_client.py`, and `model.py` previously had zero (or only
TYPE_CHECKING-guarded) `backend.app.*` dependencies — they were standalone
leaf modules. Their new logging import is wrapped in `try/except ImportError`
with a plain-stdlib-logger fallback specifically so they stay importable
from a context that doesn't have the repo root on `sys.path` (e.g.
`train.py`'s documented `python -m triage_model.train` run with
cwd=`backend/app/`) — don't remove that fallback when touching these files,
it's not defensive boilerplate, it's covering a real invocation path
(verified: `triage_model.model` etc. import fine with only `backend/app/`
on sys.path, falling back to an unconfigured `logging.Logger`).

Not yet instrumented (lower priority — these are interactively-run, one-off
scripts with their own print-based reporting already, not unattended
production paths): `data_setup.py` stayed untouched entirely (it advertises
itself as dependency-free and is run once to bootstrap data);
`test_pipeline.py`, `retrieval_accuracy_check.py`, and `train.py`'s
`if __name__ == "__main__":` blocks got a `log_exception()` safety net so an
unhandled crash still lands a full traceback in `logs/edgelegal.log`, but
their internal print-based phase reporting was left as-is.
