# Future work: multi-layer contradiction detection (journal-paper scope)

Added 2026-09-26 from a planning discussion. Not part of the conference paper
(Configs A/B/C + calibration on ContractNLI, single-document hypothesis-vs-clause task).
This is the candidate journal-paper extension.

## The idea

The conference paper only checks one relationship: does a clause in *this* document
entail/contradict/not-mention *this* fixed hypothesis. Two more relationships are also
useful and currently unaddressed together:

1. Does clause X contradict clause Y **within the same document** (e.g. Section 3 says
   30-day payment terms, Section 12 says 45-day)?
2. Does clause X in document A contradict clause Y in **document B** (e.g. a new NDA vs.
   a company's standard template, or a base MSA vs. a later amendment)?

## Prior art per layer

- **Within-document**: *Better Call CLAUSE* (EACL 2026 Findings, arXiv 2511.00340).
  Perturbation-based benchmark, ~23,955 examples generated from CUAD + ContractNLI
  contracts (~12,869 from CUAD, ~11,086 from ContractNLI), 10 anomaly types split into
  "legal" (violates external statute/regulation) and "in-text" (conflicts with another
  part of the same document) variants. Human validation agreement 98.58%. Tests three
  capabilities: binary detection, contradiction-type classification, span+explanation.
  **This is directly reusable** as training/eval data for the within-document layer —
  filter to the in-text subset.
- **Cross-document**: *Clash-of-Leges* (ScienceDirect, bilingual IT/EN). Built from
  Italian Constitutional Court rulings — conflicts between statutory/constitutional
  articles, not contracts. 632 conflicting article pairs (1,010/126/127 train/val/test
  for conflict detection; smaller splits for explanation and reference-retrieval
  subtasks). Negative examples are real dismissed-claim pairs, not random pairing —
  worth copying that design choice if we build a contract analog.
  **No contract-domain cross-document contradiction dataset exists.** Confirmed via
  search (2026-09-26) — this is a genuine, currently-open gap.

## Building the cross-document dataset cheaply

ContractNLI applies the same 17 fixed hypotheses independently across 607 NDAs. For a
given hypothesis H, different contracts get different ground-truth labels (Entailment /
Contradiction / NotMentioned). Any two contracts where H is labeled Entailment in one and
Contradiction in the other are, by construction, taking opposing positions on the same
clause type — a free cross-document contradiction pair, no new annotation required.
Caveat: this captures "two unrelated contracts disagree," not the more realistic
"contract + its own amendment now contradicts it" case. For that flavor, either (a)
LLM-generate a synthetic contradicting amendment per contract and spot-check by hand
(same approach CLAUSE and LegalWiz already use for perturbations), or (b) hand-pull a
small real gold set from SEC EDGAR contract families (MSA + amendments + SOWs filed as
separate documents for the same deal) for a credible test set, training on the synthetic/
derived data.

## Architecture

Same DeBERTa-small (or LegalBERT) classifier backbone as the conference paper's triage
model. Only the input pair changes per layer:
- Layer 1 (existing): (hypothesis, clause)
- Layer 2 (new): (clause, clause) from the same document
- Layer 3 (new): (clause, clause) from two different documents

An orchestrating agent (LangGraph — already planned in the roadmap for routing) decides
which layer(s) to run depending on what's being compared (one document vs. a set of
related documents) and merges hits from all three into a single report, e.g.: "this
clause conflicts with Section 12 (same document)" + "conflicts with Contract B's
equivalent clause (cross-document)" + "contradicts hypothesis H."

## Why this is a genuine gap, not a manufactured one

Each of the three layers individually has prior art (ContractNLI/LegalWiz for layer 1,
CLAUSE for layer 2, Clash-of-Leges for layer 3 — different domain). Nobody combines all
three into one system for contracts, let alone runs it through a confidence-gated triage
layer with calibration checking like the conference paper does for layer 1 alone. That
unification is the contribution.

## Sequencing

Do not start this before the conference paper (Configs A/B/C + calibration, layer 1 only)
is finished — the model architecture and calibration methodology this extension reuses
don't exist yet. This is next-phase work, scoped for the journal paper per the
publication-target section in `literature_review.md` and `CLAUDE.md`.
