# Adjacent legal-NLP benchmarks and retrieval papers (background/positioning, not competitors)

## ContractEval
"ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial
Contracts." ACL Anthology, NLLP Workshop 2025.
- arXiv: https://arxiv.org/abs/2508.03080
- ACL Anthology: https://aclanthology.org/2025.nllp-1.19/

Benchmarks LLMs on identifying risky clauses in commercial contracts (not NDAs
specifically, not ContractNLI). Useful as a "the field is actively benchmarking LLMs on
legal clause-level tasks right now" citation; not a triage/routing paper.

## Better Call CLAUSE
"Better Call CLAUSE: A Discrepancy Benchmark for Auditing LLMs Legal Reasoning
Capabilities." EACL Findings 2026.
- arXiv: https://arxiv.org/abs/2511.00340
- ACL Anthology: https://aclanthology.org/2026.findings-eacl.305/

A benchmark specifically auditing where LLMs' legal reasoning goes wrong/inconsistent.
Good citation for motivating *why* you don't want to trust an LLM blindly on every case
(supports the "LLM alone isn't fully reliable, hence triage matters" framing) — but
again, not a routing/triage system itself.

## ACORD
"ACORD: An Expert-Annotated Retrieval Dataset for Legal Contract Drafting." ACL 2025.
- arXiv: https://arxiv.org/abs/2501.06582
- ACL Anthology: https://aclanthology.org/2025.acl-long.1206/

Graded clause-relevance dataset for contract *drafting* assistance (finding the right
boilerplate clause to insert), a different task from contradiction/entailment detection.
Mentioned here because the Deterministic Fuzzy Triage paper (note 05) trains on it —
useful if you want to understand that paper's setup, not directly relevant otherwise.

## Summary-Augmented Chunking (retrieval quality for legal RAG)
NLLP Workshop 2025 paper (title not separately confirmed; found via ACL Anthology,
pages 17-30 of the NLLP 2025 proceedings).
- ACL Anthology PDF: https://aclanthology.org/2025.nllp-1.3.pdf

Identifies "Document-Level Retrieval Mismatch" in legal RAG (retriever pulls from the
wrong document entirely due to lexical/structural similarity across legal documents) and
fixes it by prepending a short GPT-4o-mini-generated document summary to every chunk
before embedding. Evaluated on **LegalBench-RAG**, a benchmark suite covering CUAD, MAUD,
**ContractNLI**, and PrivacyQA.

**Two useful things here:** (1) LegalBench-RAG is worth knowing about as a broader
retrieval benchmark that already includes ContractNLI — check whether it's worth citing
or even using for a retrieval-quality robustness check alongside your own
`retrieval_accuracy_check.py`. (2) This paper is purely about retrieval-side accuracy, no
routing/triage/calibration content — relevant background for discussing why your
structure-aware clause parser + adaptive gap filter matter, not a competing method.

## The broad legal-NLP survey
**Author/year:** Farid Ariai, Gianluca Demartini (2024). ACM Computing Surveys.
- https://dl.acm.org/doi/10.1145/3777009

**Idea:** A systematic review of 131 studies on NLP for legal text. Covers document
summarization, entity recognition, question answering, argument mining, classification,
and judgment prediction; evaluates specialized legal language models vs. adapting
general-purpose models. Identifies sixteen open research challenges, with the abstract
specifically flagging bias in legal AI and the need for more interpretable/explainable
systems.

**What you need from it:** Good citation for your related-work section's opening
paragraph — "a comprehensive, up-to-date survey of legal NLP" is exactly what belongs
there. I could not get the full text (ACM paywalled it — 403 on two attempts), so I only
have the abstract, which does not explicitly mention calibration or confidence-based
routing among its named challenges — but the abstract only teases the 16 challenges, it
doesn't list all of them, so I can't confirm or rule out that calibration/routing is one
of the sixteen. If your institution has ACM Digital Library access, this is worth reading
in full specifically to check that list before you claim the calibration gap is
completely unaddressed in the survey literature.
