# LLM cascades / confidence-based routing (the general-ML prior art for "triage")

This is the category that matters most for your novelty claim: the abstract idea of "a
cheap model gates calls to an expensive model" is NOT new in ML generally. Read this
note before writing your contribution paragraph.

## FrugalGPT
**Citation:** Lingjiao Chen, Matei Zaharia, James Zou. "FrugalGPT: How to Use Large
Language Models While Reducing Cost and Improving Performance." 2023.
- arXiv: https://arxiv.org/abs/2305.05176

Cascades cheaper LLM APIs before expensive ones, using a learned scoring function to
decide whether to accept a cheap answer or escalate. Foundational citation for "LLM
cascade" framing generally. Not legal-domain, not calibration-checked, not classifier-based
(cascades between LLMs of different cost tiers, not a small classifier + LLM).

## CALM (Confident Adaptive Language Modeling)
**Citation:** Tal Schuster et al. NeurIPS 2022.
- arXiv: https://arxiv.org/abs/2207.07061

Confidence-based early-exit *within* a single Transformer's layers to save compute per
token, not a two-model routing setup. Good citation for "confidence-gated early
termination" as a general principle, but architecturally different from your setup.

## Adaptive-RAG
**Citation:** Soyeong Jeong et al. "Adaptive-RAG: Learning to Adapt Retrieval-Augmented
Large Language Models through Question Complexity." NAACL 2024.
- ACL Anthology (PDF): https://aclanthology.org/2024.naacl-long.389.pdf

Trains a small classifier to predict query complexity and routes to different
retrieval/generation strategies accordingly (no-retrieval / single-step / multi-step).
Conceptually the closest "spirit match" outside legal NLP: a small classifier gating
which expensive pipeline runs. Worth citing directly as the RAG-side analogue of your
NLI-side triage idea.

## Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey
- arXiv: https://arxiv.org/abs/2603.04445 (very recent, ~March 2026)

**This is the single most useful search result for honestly framing your novelty.**
I had this survey fetched and summarized directly. Key findings:
- It categorizes routing into six paradigms: difficulty-aware, preference-aligned,
  clustering-based, reinforcement-learning-based, uncertainty-based, and cascading.
- **Calibration is NOT standard practice**: the survey states that verbalized/self-reported
  confidence in routing systems "consistently exhibit[s] low alignment between reported
  uncertainty and prediction correctness," and explicit ECE/reliability-diagram checks are
  described as largely absent from standard evaluation practice in this literature (its
  Section 9.2).
- **Legal-domain applications are not covered at all** in this survey — no mention of
  legal NLI, contract review, or contradiction detection anywhere in it.

So: confirmed by the field's own survey literature, from two independent angles
(routing-in-general AND legal-NLP-specifically), that calibration-checked routing is a
real, currently open gap — not something you need to hedge about, it's directly stated.

## Calibration methodology (cite this for your ECE/reliability-diagram method)
**Citation:** Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger. "On Calibration of
Modern Neural Networks." ICML 2017.
- arXiv: https://arxiv.org/abs/1706.04599

The standard citation for temperature scaling and Expected Calibration Error (ECE) as a
metric — cite this directly in your Section 6.2 methodology.
