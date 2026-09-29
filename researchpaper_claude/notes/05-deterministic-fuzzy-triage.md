# Deterministic Fuzzy Triage for Legal Compliance Classification and Evidence Retrieval

- arXiv: https://arxiv.org/abs/2603.07390 (~March 2026, very recent)

## What it does
Trains a RoBERTa-base dual encoder on ACORD (graded clause-relevance) then fine-tunes on
CUAD-derived binary compliance labels. Its "fuzzy triage" is a three-way decision band
from two learned thresholds: below τ_low = auto-noncompliant, above τ_high =
auto-compliant, in between = routed to human review. Grid-searched thresholds constrain
auto-region error to ≤2%.

## Why it's adjacent, not competing
- **No LLM anywhere in the pipeline** — deliberately avoids "opaque LLM copilots" in
  favor of a lightweight logistic head on cosine-similarity scores. Your escalation
  target (a local LLM) is exactly what this paper avoids.
- **Different datasets:** ACORD and CUAD, not ContractNLI.
- **Escalates to a human, not a bigger model.** Structurally a different kind of triage
  (classifier-to-human) than yours (classifier-to-LLM).
- **Calibration:** mentions ECE/"calibration metrics" as part of its evaluation
  methodology but does not report actual ECE values or reliability diagrams in results —
  so even here, the calibration check is more claimed than delivered.

## Relevance
Good citation for "triage" as an established framing in legal AI generally, and for
threshold-selection methodology (grid search under an error constraint is a legitimate
alternative framing to your validation-sweep approach) — but not a paper that overlaps
your actual contribution.
