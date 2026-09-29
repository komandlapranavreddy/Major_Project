# LegalWiz — READ THIS ONE FIRST. Closest existing paper to your core mechanism.

**Citation:** "LegalWiz: A Multi-Agent Generation Framework for Contradiction Detection
in Legal Documents." arXiv, October 2025.
- arXiv: https://arxiv.org/abs/2510.03418

## Why this is the most important paper in this folder

Its pipeline already does the literal core mechanism your project is built around:
**an NLI classifier's confidence gates whether a case is accepted directly or escalated
to an LLM.** Specifically, its "Contradiction Mining Agent" runs staged filtering —
semantic similarity, then NLI classification (facebook/bart-large-mnli), then LLM
judgment (GPT-4o) — and pairs with NLI confidence ≤ 0.7 are escalated to the LLM, with
hybrid scoring weights derived from the model's own confidence. That is your triage
mechanism, already published, one year ago.

## Why EdgeLegal is still different (this is your differentiation paragraph, basically free)

1. **Dataset:** LegalWiz evaluates on 50 *synthetic* documents it generates itself (a
   fictional aerospace company, 6 injected contradiction types), not on ContractNLI or
   any established public benchmark. EdgeLegal evaluates on the standard, independently-
   annotated ContractNLI test split — directly comparable to prior published baselines.
2. **Purpose:** LegalWiz's goal is generating a *stress-test benchmark* for RAG systems
   (contradiction injection + detection as a data-generation pipeline). EdgeLegal's goal
   is evaluating whether the *triage decision itself* is trustworthy and worth the added
   complexity — a different research question even though the mechanism overlaps.
3. **Calibration — this is the clean, verifiable gap.** I had this paper's full text
   checked directly: it uses confidence-weighted scoring but performs **no calibration
   analysis** — no ECE, no reliability diagram, nothing verifying whether its 0.7
   threshold or its confidence-derived weights are actually trustworthy. That is
   explicitly the question your Project Guide's Section 6.2 makes mandatory. This is the
   single cleanest, most defensible sentence for your contribution paragraph: *"Unlike
   LegalWiz (2025), which uses NLI confidence to weight escalation decisions without
   verifying that confidence is calibrated, we explicitly evaluate whether the triage
   classifier's confidence is trustworthy enough to route on."*
4. **Comparison design:** LegalWiz doesn't run a no-triage baseline vs. pretrained-
   checkpoint vs. fine-tuned-triage comparison (your Configs A/B/C) or a McNemar
   significance test between configurations.

## Action item
You should cite this paper explicitly in related work and use it as your primary
"closest prior art" contrast — don't let a reviewer discover it before you do. Read the
full PDF yourself before finalizing the related-work section; this note is a thorough
summary but not a substitute for reading it directly.
