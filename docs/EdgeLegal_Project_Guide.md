# EdgeLegal: Confidence-Routed Legal Contradiction Detection
## Project Guide — Scoped Implementation & Research Plan

---

## 1. Problem Statement

Legal contract review — checking whether clauses within a contract (or against standard obligations) are consistent, contradictory, or silent — is manual, slow, and expensive. Retrieval-Augmented Generation (RAG) systems built on Large Language Models (LLMs) can automate this, but a pure LLM-driven pipeline has a specific, measurable inefficiency: **every single clause comparison, including trivially obvious ones, requires a full LLM inference call.** On long contracts, or when checking many clauses against many standard obligations, this cost compounds and dominates system latency — especially in privacy-preserving deployments that require a local (non-cloud) LLM, where compute is limited by design.

Separately, small NLI (Natural Language Inference) classifiers — fine-tuned Transformer models like LegalBERT or DeBERTa — can be trained to predict Entailment / Contradiction / Not-Mentioned relationships between a clause and a hypothesis far faster and cheaper than an LLM, but they cannot generate human-readable legal reasoning or explanations, and their predictions are not inherently trustworthy without validation.

**The core research question this project answers is:**

> Can a fine-tuned legal NLI classifier act as a *confidence-gated triage layer* in front of an LLM-based agentic reasoning pipeline — accepting its own predictions when confident and escalating only uncertain cases to the LLM — while preserving overall accuracy, reducing LLM calls, and remaining well-calibrated enough that its confidence scores can be trusted for this routing decision?

This is deliberately **not** a claim of inventing a new model or algorithm. The novelty lies in the *system-level question*: most existing work evaluates legal NLI classifiers in isolation (as a standalone benchmark task) or evaluates agentic RAG pipelines without a lightweight gating mechanism. This project evaluates the **combination** — a trained classifier's decisions embedded inside a live, confidence-routed agent loop — and reports whether that combination is actually worth the added complexity, including whether the classifier's confidence is trustworthy enough to route on (calibration), not just whether it's accurate on average.

If the triage layer does **not** meaningfully reduce LLM calls without hurting accuracy, that is still a valid, honestly reportable research finding — not a failure of the project.

---

## 2. Research Scope — What This Project Is and Is Not

### This project IS:
- An empirical, system-level evaluation of confidence-gated routing between a small fine-tuned NLI classifier and a local LLM.
- Built and evaluated on **ContractNLI** (607 real NDAs, 17 fixed hypotheses, Entailment/Contradiction/NotMentioned labels), a public, free, well-established benchmark.
- Scoped to **one clear question, one dataset, one triage model family (a Transformer NLI classifier), and one honest comparison** against a no-triage baseline and an existing pretrained checkpoint.

### This project IS NOT:
- An attempt to invent a new model architecture or training algorithm.
- A claim that the triage classifier "solves" legal reasoning — it explicitly does not; the LLM remains responsible for all reasoning and explanation.
- A multi-paper, multi-dataset, multi-architecture research program. Scope stays narrow on purpose.

### Explicitly out of scope (deferred to Future Work):
- Graph Neural Network (GNN) clause-relationship modeling.
- Multi-document / cross-contract reasoning.
- Multi-language contracts.
- Federated or active learning for the triage model.
- Reinforcement-learning-based adaptive thresholds (a fixed, validation-tuned threshold is used instead).
- BiLSTM as the primary triage model (considered and rejected — see Section 4).

---

## 3. Why Not BiLSTM (Brief Justification)

An earlier version of this design considered a BiLSTM (+ Attention) as the triage classifier. This was reconsidered because:

- ContractNLI is fundamentally a **pairwise entailment (NLI) task** — given a clause and a hypothesis, predict their logical relationship — not a single-sequence labeling task (like NER or clause-type classification), which is where BiLSTMs have their strongest track record.
- Transformer-based encoders process the (premise, hypothesis) pair jointly through self-attention from the first layer, allowing direct token-to-token comparison across the two spans. A BiLSTM typically encodes each side (semi-)independently and only combines them after compression into fixed vectors — a structurally weaker mechanism for entailment-style comparison.
- Modern NLI research and legal-NLI literature specifically has converged on Transformer-based encoders (BERT-family, DeBERTa) for this exact task family, making this the more defensible, better-supported choice.
- BiLSTM is retained only as a footnote/known-alternative, not implemented as a parallel arm of the experiment, to keep scope tight.

**Decision: DeBERTa-v3-small or LegalBERT-base, fine-tuned by us on ContractNLI's train split, is the triage model used throughout this project.**

---

## 4. System Architecture

```
                              Contract PDF
                                   |
                        PDF Extraction (PyMuPDF)
                                   |
                     Structure-Aware Clause Parser
                    (each clause = independently retrievable
                     unit, with page number + section heading)
                                   |
                 +-----------------+-----------------+
                 v                                   v
         Embedding Model                    Fine-Tuned NLI Classifier
       (BGE-small / E5-base)                (DeBERTa-v3-small or
                 |                            LegalBERT-base)
                 v                                   |
             ChromaDB                                v
         (clause embeddings +               Label + Confidence Score
          metadata, semantic                (Entailment / Contradiction /
          retrieval)                         Not-Mentioned, 0.0-1.0)
                 |                                   |
                 +-----------------+-----------------+
                                   v
                          LangGraph Agent
                    (orchestration + routing logic)
                                   |
                    Confidence >= threshold?
                 +------------------+------------------+
                 | YES                                 | NO
                 v                                     v
        Accept classifier's                  Escalate to Local LLM
        prediction directly                  (Llama 3 8B / Phi-3 Mini,
        (no LLM call)                         via Ollama)
                 |                                     |
                 |                          LLM confirms/overrides label,
                 |                          generates natural-language
                 |                          explanation
                 |                                     |
                 +------------------+------------------+
                                   v
                        Final Contradiction Report
              (label, confidence, source [classifier/LLM],
               evidence clause(s), explanation if LLM-verified)
```

### Component Responsibilities (one job per component — do not blur these)

| Component | Responsibility | Does NOT do |
|---|---|---|
| PDF Extractor (PyMuPDF) | Extract text + page/coordinate metadata | Any classification or reasoning |
| Clause Parser | Segment contract into independently retrievable clause units | Predict labels |
| Embedding Model | Convert clauses into vectors for retrieval | Predict Entailment/Contradiction |
| ChromaDB | Store embeddings + metadata, support semantic + metadata-filtered retrieval | Any model inference |
| **Triage Classifier (DeBERTa/LegalBERT)** | **Fast Entailment/Contradiction/NotMentioned prediction + confidence score** | **Explain *why*; general legal reasoning** |
| LangGraph Agent | Orchestrate control flow; apply the confidence threshold; decide whether to escalate | Predict labels itself; generate explanations |
| Local LLM | Deep legal reasoning, explanation generation, override triage prediction if wrong | Handle every case — only called on escalation |
| Report Generator | Assemble final human-readable report with evidence + explanations | Any prediction logic |

---

## 5. Implementation Plan

### 5.1 Folder Structure

```
edgelegal/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── parsing/
│   │   │   ├── pdf_extractor.py     # PyMuPDF extraction
│   │   │   └── clause_parser.py     # Structure-aware clause segmentation
│   │   ├── embeddings/
│   │   │   └── embedder.py          # BGE-small / E5-base wrapper
│   │   ├── vectorstore/
│   │   │   └── chroma_client.py     # ChromaDB collection management
│   │   ├── triage_model/
│   │   │   ├── model.py             # DeBERTa/LegalBERT wrapper
│   │   │   ├── train.py             # Fine-tuning script (ContractNLI train split)
│   │   │   ├── evaluate.py          # Test-split evaluation + calibration check
│   │   │   └── infer.py             # predict(clause, hypothesis) -> (label, confidence)
│   │   ├── agent/
│   │   │   ├── graph.py             # LangGraph node/edge definitions
│   │   │   └── nodes.py             # retrieve, triage, confidence_check, call_llm nodes
│   │   ├── llm/
│   │   │   ├── ollama_client.py     # Local LLM interface via Ollama
│   │   │   └── prompts.py           # Reasoning/explanation prompt templates
│   │   └── report/
│   │       └── report_generator.py  # Final report assembly
│   ├── data/
│   │   └── contractnli/             # train/val/test splits
│   └── requirements.txt
├── frontend/                        # React UI (upload, chat, report view, PDF viewer)
├── notebooks/                       # Training runs, calibration plots, ablation analysis
└── docs/                            # This guide, diagrams, references
```

### 5.2 Step-by-Step Build Order

1. **Data setup.** Download ContractNLI (public, free — Stanford NLP repository). Confirm train/val/test split sizes.
2. **Fine-tune the triage classifier.** DeBERTa-v3-small or LegalBERT-base, standard HuggingFace `transformers` fine-tuning on the train split. Small number of epochs (3–5 for a Transformer fine-tune), small learning rate (2e-5), early stopping on validation F1 (not accuracy — ContractNLI's Not-Mentioned class is likely imbalanced).
3. **Baseline checkpoint for comparison.** Pull an existing pretrained ContractNLI checkpoint (e.g., a Span-NLI-BERT baseline) and run it on the test split, unmodified, purely as a reference point — do not fine-tune or alter it.
4. **Calibration check.** For the fine-tuned classifier, verify whether stated confidence matches actual correctness (e.g., a reliability diagram: among predictions where confidence ≈ 0.9, is accuracy actually ≈ 90%?). This is a required step, not optional — an uncalibrated classifier makes the routing threshold meaningless.
5. **Threshold selection.** On the validation split only, sweep candidate confidence thresholds (e.g., 0.60 to 0.95), measure accuracy vs. percentage of cases escalated, and freeze the threshold that gives the best accuracy-preserving reduction in escalations. Never tune this against the test split.
6. **Build the parser, embeddings, and ChromaDB retrieval layer.** Structure-aware clause segmentation; embed clauses; store with metadata.
7. **Build the LangGraph routing agent.** Retrieve → run triage classifier → check confidence against frozen threshold → accept directly or escalate to local LLM.
8. **Connect the local LLM.** Served via Ollama, only invoked on escalation, producing a structured (ideally JSON) output: label, reasoning, cited clauses.
9. **Build the report generator and minimal frontend.** Enough to demonstrate the pipeline end-to-end; polish is secondary to the experiment.

---

## 6. Experimental Design

### 6.1 The Three Required Comparisons

| Configuration | Description | Purpose |
|---|---|---|
| **A — No-Triage Baseline** | Every clause pair sent directly to the local LLM | Control: what does the system cost/achieve with zero triage? |
| **B — Existing Checkpoint as Triage** | Pretrained ContractNLI classifier (unmodified) gates the LLM | Answers "why not just use what's already published?" |
| **C — Our Fine-Tuned Triage** | Our fine-tuned DeBERTa/LegalBERT gates the LLM | The project's actual contribution |

All three run on the **same test split**, same confidence threshold selection procedure (frozen from validation), same hardware, same LLM.

### 6.2 Metrics to Report

- **Classification quality:** Accuracy, Precision, Recall, F1 (per class, given likely class imbalance).
- **System efficiency:** Percentage of cases resolved without an LLM call; average latency per query; resource usage (RAM/CPU or GPU, if available).
- **Calibration:** Reliability diagram or Expected Calibration Error (ECE) for the triage classifier's confidence scores.
- **Statistical rigor:** Repeat latency measurements multiple times (mean ± standard deviation, not a single run). Where feasible, apply a paired significance test (e.g., McNemar's test for classification differences) between configurations, given ContractNLI's test split is not large (~150 contracts) — report honestly if a difference is not statistically significant rather than overclaiming.

### 6.3 Interpreting Results Honestly

- If Configuration C does not meaningfully outperform Configuration B, that is a legitimate, reportable finding — it suggests off-the-shelf checkpoints may already be sufficient, which is itself useful information.
- If the triage layer (B or C) does not reduce LLM calls without hurting accuracy relative to A, that supports recommending the simpler no-triage architecture — also a legitimate finding, not a failure.
- Do not tune the confidence threshold after seeing test-split results. Do not cherry-pick favorable runs. Report variance, not just best-case numbers.

---

## 7. Literature Positioning (Brief)

- **ContractNLI** (Koreeda & Manning, EMNLP Findings 2021) — the source dataset and original Span-NLI-BERT baseline.
- **LegalBERT / domain-pretrained legal Transformers** — established track record in legal clause classification and NER; less commonly evaluated as a *routing gate* inside an agentic pipeline specifically.
- **DeBERTa** — disentangled attention mechanism, generally strong on NLI benchmarks; a valid non-legal-domain alternative to LegalBERT.
- **Agentic RAG** (LangGraph-style multi-step orchestration) — a comparatively recent direction; its combination with a calibration-checked lightweight triage gate for legal contradiction detection specifically is the underexplored intersection this project targets.

The claim to make in writing: **not** "we built a new model," but **"we measured whether a fine-tuned legal NLI classifier's confidence can be trusted to safely gate expensive LLM calls in a live agentic pipeline, and report the accuracy/efficiency/calibration trade-off honestly."**

---

## 8. Limitations (State These Explicitly in the Final Report)

- Evaluated only on ContractNLI (NDAs); generalization to other contract types (leases, vendor agreements, employment contracts) is untested.
- ContractNLI's ~600-contract scale is small relative to typical Deep Learning training sets, which constrains how well the fine-tuned classifier can be expected to generalize.
- The system is a decision-support and triage tool, not a replacement for legal review by a qualified professional.
- Overall pipeline quality depends on retrieval quality — a missed clause cannot be reasoned over regardless of classifier or LLM quality downstream.
- Confidence-based routing assumes the classifier's confidence is well-calibrated; this assumption is checked (Section 6.2) rather than presumed.

---

## 9. Definition of Done

The project is considered complete and ready to write up when:

1. The triage classifier is fine-tuned, validated, and its calibration has been checked and reported (good or bad).
2. All three configurations (A, B, C) have been run on the same test split with the metrics in Section 6.2 recorded.
3. The confidence threshold was selected on validation data only, frozen before test evaluation.
4. Results — including any negative or mixed findings — are written up honestly, with variance/significance reported, not just best-case numbers.
5. Limitations (Section 8) are stated explicitly in the final report, not omitted.

This document is the single source of truth for scope. If a new idea or extension comes up mid-project, check it against Sections 2 and 6 first — if it doesn't fit inside the frozen scope, it goes into Future Work, not into the current build.
