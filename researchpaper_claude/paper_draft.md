# EdgeLegal: Confidence-Routed Legal Contradiction Detection — Paper Draft

Working draft for the conference paper. Sections marked **[PENDING NUMBERS]**
need the matched Config A/B/C run (see CLAUDE.md "Experiment runs") before
they can be finished — everything else here can be finalized now. Do not
fill placeholder numbers with guesses; leave them marked until the real run
lands, per Project Guide §6.3 ("do not cherry-pick, report honestly").

---

## Working title

"Can a Fine-Tuned Legal NLI Classifier Be Trusted to Gate LLM Escalation?
A Calibration-Checked Confidence-Routing Study on ContractNLI"

(Alt, shorter: "Confidence-Gated Triage for Legal Contradiction Detection:
An Honest Calibration Check")

---

## Abstract **[PENDING NUMBERS — draft shape only]**

Legal contradiction detection with LLMs is accurate but expensive: every
clause-hypothesis pair costs a full LLM call. We evaluate whether a small,
fine-tuned NLI classifier can safely gate escalation to an LLM — accepting
its own prediction when confident, escalating only uncertain cases — on the
ContractNLI benchmark. Unlike prior confidence-gated legal contradiction
work (LegalWiz, 2025), which does not verify calibration, we explicitly
measure whether the classifier's confidence can be trusted for routing
(Expected Calibration Error, reliability diagrams) before relying on it,
and compare a no-triage baseline (Config A), an off-the-shelf pretrained
checkpoint (Config B), and our fine-tuned classifier (Config C) on the same
test split with paired significance testing. [RESULT SENTENCE PENDING —
this is where the calibration finding goes: on held-out validation data the
classifier is well-calibrated (ECE = 0.0285), but under deployment
conditions — real single-clause retrieval instead of oracle evidence spans —
calibration degrades substantially (ECE = 0.44 in a preliminary run),
demonstrating that dev-set calibration does not guarantee deployment-time
trustworthiness for routing decisions.] [Efficiency/accuracy trade-off
numbers pending the paper-grade run.]

---

## 1. Introduction

Legal contract review — checking whether clauses are consistent,
contradictory, or silent relative to a standard obligation — is manual,
slow, and expensive. LLM-based retrieval-augmented generation (RAG)
systems can automate this, but every clause comparison requires a full LLM
inference call, which compounds in cost and latency on long contracts or
when checking many clauses against many standard obligations — especially
in privacy-preserving deployments constrained to local (non-cloud) LLMs.

Small NLI classifiers (fine-tuned Transformers such as DeBERTa or
LegalBERT) can predict Entailment/Contradiction/NotMentioned relationships
between a clause and a hypothesis far faster and cheaper than an LLM, but
cannot generate human-readable legal reasoning, and their predictions are
not inherently trustworthy without validation.

**Research question**: Can a fine-tuned legal NLI classifier act as a
confidence-gated triage layer in front of an LLM-based reasoning pipeline —
accepting its own predictions when confident and escalating only uncertain
cases — while preserving accuracy, reducing LLM calls, and remaining
well-calibrated enough that its confidence can actually be trusted for that
routing decision?

This is not a claim of a new model or algorithm. The contribution is the
system-level question and an honest answer to it, including whether the
classifier's confidence is trustworthy enough to route on — not just
whether it is accurate on average. If the triage layer does not reduce LLM
calls without hurting accuracy, or if its confidence turns out not to be
trustworthy, that is still a valid, honestly reportable finding.

---

## 2. Related Work

- **ContractNLI** (Koreeda & Manning, EMNLP Findings 2021) — source dataset
  and the original Span-NLI-BERT baseline. We use the standard 3-way
  Entailment/Contradiction/NotMentioned formulation exactly as defined
  there; no new label taxonomy is proposed.
- **LegalWiz** (2025) — the closest prior work: NLI-confidence-gated
  escalation to GPT-4o for legal contradiction detection. Uses 50
  synthetically generated documents and performs no calibration analysis
  of the routing confidence itself.
- **LLM cascades / confidence-based early exit / Adaptive-RAG** — the
  general routing mechanism is established outside the legal domain; a
  March-2026 survey on model routing/cascading notes that explicit
  ECE/reliability-diagram checks are largely absent from standard practice
  even there.
- **"Can Small Models Reason About Legal Documents?"** (Mar 2026) — uses
  ContractNLI, but for zero/few-shot generative LLM comparison, not
  routing.
- **Deterministic Fuzzy Triage** — mentions calibration metrics in its
  methodology but does not report actual ECE values.
- **LegalBERT / domain-pretrained legal Transformers** — established for
  legal clause classification/NER; less commonly evaluated as a routing
  gate inside an agentic pipeline specifically.
- **DeBERTa** — disentangled attention, strong general NLI performance; a
  valid non-legal-domain alternative to LegalBERT, used here via
  `cross-encoder/nli-deberta-v3-base`, warm-started from its native 3-class
  NLI head rather than a randomly initialized head.
- **ContraGen** (arXiv:2510.03418, Oct 2025) — closest *concurrent* work:
  a multi-agent framework combining NLI and LLM scores (confidence-weighted
  hybrid scoring) for contradiction detection in synthetic enterprise
  documents. Differs from this project on every axis that matters here: no
  ContractNLI/legal-contract focus, no accept-or-escalate threshold gate
  (it blends scores rather than routing), and no calibration/ECE analysis.

**The gap this paper targets** (confirmed from three independent angles —
see `literature_review.md` for full detail): (1) calibration is checked
nowhere in this specific space, (2) nobody has run a confidence-gated
triage system on the standard ContractNLI benchmark itself, (3) the
three-way honest comparison (no-triage vs. pretrained vs. fine-tuned, same
test split, paired significance testing) does not appear in the literature
found.

**Contribution statement**: We evaluate whether a fine-tuned legal NLI
classifier's confidence can be trusted to gate escalation to a local LLM
for contradiction detection on the ContractNLI benchmark. Unlike prior
confidence-gated legal contradiction detection, which applies
confidence-weighted escalation without verifying calibration, we explicitly
measure whether the routing classifier's confidence is calibrated (ECE,
reliability diagram) before treating it as trustworthy for routing, under
both idealized (oracle evidence span) and deployment (real retrieval)
conditions — and compare a no-triage baseline, an off-the-shelf pretrained
checkpoint, and our fine-tuned classifier on the same test split.

---

## 3. System Architecture

Pipeline: PDF -> clause segmentation (structure-aware, not naive
block-chunking) -> embedding (BAAI/bge-small-en) -> semantic retrieval with
an adaptive gap filter (keep rank-1, drop any candidate with a >15%
relative distance jump from it) -> confidence-routed agent:

```
retrieve -> triage -> confidence_check --accept----> accept    -> END
                                        \--escalate--> call_llm -> END
```

The triage classifier is a pairwise (premise, hypothesis) NLI model
(`cross-encoder/nli-deberta-v3-base`, fine-tuned on ContractNLI's train
split), run once against the single highest-ranked retrieved clause. If its
confidence is at or above a frozen threshold (tau = 0.95, selected on the
validation split only, never touched against test), its label is accepted
directly with no LLM call. Below threshold, all gap-filtered candidate
clauses are sent to the LLM for reasoning and a final label. Implemented as
a LangGraph state machine (`agent/graph.py`), used identically by the
research evaluation harness and the live demo application (see
implementation note below).

**Implementation note (system contribution, not just an experiment
script)**: the live demonstration application and the offline evaluation
harness run the exact same agent graph, retrieval pipeline, and triage
model — not two separate implementations that happen to agree. This
matters for the calibration finding in Section 5/6: the deployment-time
calibration measurement is not a simulation of the live system, it *is* the
live system's own code path, run offline against labeled data.

---

## 4. Experimental Design

Three configurations, run on the same test split, same threshold-selection
procedure, same hardware, same LLM:

| Configuration | Description | Purpose |
|---|---|---|
| A — No-Triage Baseline | Every clause pair sent directly to the LLM | Control |
| B — Existing Checkpoint | Off-the-shelf `cross-encoder/nli-deberta-v3-base`, no ContractNLI fine-tuning, gates the LLM | "Why not just use what's already published?" |
| C — Our Fine-Tuned Triage | Fine-tuned on ContractNLI's train split, gates the LLM | The project's actual contribution |

Metrics: classification quality (accuracy, per-class precision/recall/F1
given class imbalance — Contradiction is the minority class at ~9% of
data and the class the whole system is about); system efficiency (% of
cases resolved without an LLM call, mean/p50/p95 latency, resource usage);
calibration (ECE, reliability diagram) for the triage classifier's
confidence, measured both on held-out validation data (oracle evidence
spans) and under deployment conditions (real single-clause retrieval);
paired significance testing (McNemar's test) between configurations, given
ContractNLI's test split is not large (~123 contracts).

Threshold tau = 0.95 was selected on the validation split only, before any
test-split evaluation, and not revisited afterward.

## 5. Results **[PENDING NUMBERS]**

**5.1 Held-out validation calibration** (complete): accuracy 0.9701,
macro-F1 0.9391 (per-class F1: Entailment 0.9699, NotMentioned 0.9988,
Contradiction 0.8485), ECE = 0.0285 on 1037 validation examples using
oracle evidence-span premises.

**5.2 Deployment-condition calibration** (complete, preliminary sample —
20 documents / 340 pairs, not yet the full test split): accuracy dropped to
0.5324, macro-F1 to 0.4796, ECE rose to 0.4396. At the routing threshold
(tau=0.95), 89.1% of real pairs were still accepted directly, at roughly
55% accuracy among the highest-confidence bin — indicating the
classifier's confidence is not currently trustworthy for routing under
real retrieval conditions, despite excellent calibration on
validation-style oracle premises. [Root-cause note for methods/discussion:
training data gives NotMentioned examples the full document as premise
while Entailment/Contradiction get a short evidence span; deployment always
supplies one short retrieved clause regardless of label — a likely,
not-yet-fully-isolated mismatch between training and deployment premise
distributions.]

**5.3 Config A/B/C comparison** — PENDING the full paper-grade run
(123-document test split, matched sample across all three configs,
repeated latency measurements). A preliminary matched run at smaller scale
is in progress as of this draft.

**5.4 Significance testing** — PENDING; McNemar's test is implemented and
ready to run once 5.3 lands.

## 6. Discussion **[Skeleton — fill in once 5.3/5.4 land]**

- Does fine-tuning (C) meaningfully outperform the off-the-shelf checkpoint
  (B)? If not, that's a legitimate finding (off-the-shelf may already be
  sufficient).
- Does triage (B or C) reduce LLM calls without hurting accuracy relative
  to the no-triage baseline (A)? If not, that supports recommending the
  simpler architecture.
- The calibration finding (5.2) is itself a primary result, independent of
  5.3/5.4: it demonstrates that validation-style calibration checks are
  insufficient evidence of deployment trustworthiness for this class of
  system, and argues for always measuring calibration under the actual
  retrieval conditions the classifier will see in production, not just on
  oracle-premise benchmark splits.

## 7. Limitations

- Evaluated only on ContractNLI (NDAs); generalization to other contract
  types (leases, vendor agreements, employment contracts) is untested.
- ContractNLI's ~600-contract scale is small relative to typical deep
  learning training sets, constraining how well the fine-tuned classifier
  can be expected to generalize.
- The system is a decision-support and triage tool, not a replacement for
  legal review by a qualified professional.
- Overall pipeline quality depends on retrieval quality — a missed clause
  cannot be reasoned over regardless of classifier or LLM quality
  downstream.
- Confidence-based routing assumes the classifier's confidence is
  well-calibrated; this assumption was checked, not presumed, and (per
  Section 5.2) found not to hold under deployment conditions as currently
  trained — reported honestly rather than omitted.
- The deployment-condition calibration measurement (5.2) is itself a
  preliminary sample (20 of 123 test documents); the full test split has
  not yet been run.

## 8. Conclusion **[PENDING — write last, once 5/6 are final]**

---

## Notes for whoever finishes this draft

- Every number above is either already verified (5.1, 5.2) or explicitly
  marked pending (5.3, 5.4, abstract, conclusion). Do not fill a pending
  slot with anything other than a real run's output.
- If the full paper-grade run confirms the calibration problem persists at
  scale, the honest framing is: "we built the mechanism, checked
  calibration rigorously under both idealized and deployment conditions,
  and found it currently fails to hold under deployment — this is a
  negative-but-legitimate result per the project's own definition of done
  (Project Guide §9.1), and future work is to retrain with
  deployment-realistic premises."
- Full reference details per paper are in `researchpaper_claude/notes/`.
