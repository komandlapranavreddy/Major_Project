# ContractNLI (the benchmark this whole project runs on)

**Citation:** Yuta Koreeda, Christopher D. Manning. "ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts." Findings of EMNLP 2021.

**Links:**
- arXiv: https://arxiv.org/abs/2110.01799
- ACL Anthology (PDF, open access): https://aclanthology.org/2021.findings-emnlp.164.pdf
- Official site + baseline code: https://stanfordnlp.github.io/contract-nli/ , https://github.com/stanfordnlp/contract-nli-bert

**What it is:** 607 real NDAs, 17 fixed hypotheses (standard NDA clauses like "sharing with third parties is allowed", "confidentiality survives termination", etc.), each contract x hypothesis pair labeled Entailment / Contradiction / NotMentioned, plus gold evidence spans. Splits: train 423 / dev 61 / test 123 (matches what's already downloaded in `backend/data/contractnli/`). Original baseline: Span-NLI-BERT, which jointly predicts the label and the supporting span.

**Relevance to EdgeLegal:** This is the dataset and task definition the entire project is built on. Every claim in the paper needs to be evaluated on this same test split for comparability with the original paper and with the newer papers below that also use it.

**Gap it leaves open:** The original paper evaluates a single fine-tuned classifier standalone — no LLM-in-the-loop, no confidence-based escalation, no calibration check. That gap is exactly where a triage-routing paper can sit.
