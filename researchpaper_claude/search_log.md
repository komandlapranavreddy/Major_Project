# Search log — 2026-09-25

## Method
WebSearch (general web) + WebFetch (for full-text summarization of specific pages),
scoped where useful with `allowed_domains` to ieeexplore.ieee.org, link.springer.com,
arxiv.org, semanticscholar.org, dl.acm.org. Google Scholar itself blocks automated
fetching (no bot access), so it was not queried directly — its results ultimately point
to the same primary sources (arXiv, ACL Anthology, IEEE Xplore, ACM DL, SpringerLink)
that were searched directly instead.

## Queries run (paraphrased, chronological)
1. ContractNLI Koreeda Manning EMNLP 2021
2. LegalBERT Chalkidis paper
3. DeBERTa / DeBERTaV3 papers
4. ContractNLI leaderboard / SOTA since Span-NLI-BERT
5. LLM cascade / FrugalGPT / confidence routing survey
6. Confident Adaptive Language Modeling (CALM)
7. Adaptive-RAG query complexity routing
8. Legal contract review LLM/RAG/agent papers 2024-2025
9. Calibration (Guo et al. 2017) / legal NLI calibration search (no legal-specific
   calibration paper found — this itself is informative, see literature_review.md)
10. ReAct / Self-RAG tool-use agent papers
11. IEEE-scoped: confidence-gated triage classifier LLM legal contract cascade
12. Springer-scoped: legal NLI contradiction detection triage/routing/calibration
13. arXiv-scoped: legal contract contradiction detection confidence calibration triage
    small model large model → surfaced LegalWiz, ContraVis, Better Call CLAUSE,
    Deterministic Fuzzy Triage, Can Small Models Reason About Legal Documents,
    ContractEval — the most productive single query of the session
14. IEEE conference search for "legal" + "triage" + LLM + confidence routing
15. Semantic Scholar / ACM-scoped: confidence calibration triage NLI classifier LLM legal
16. Multi-Agent Orchestration of Local LLMs for Contract Review (found via query 8,
    could not get full text — ACM 403, no arXiv mirror found)
17. ContractEval, Better Call CLAUSE follow-up searches for method/findings detail
18. NLP for the Legal Domain survey (ACM Computing Surveys) — found, could not read
    in full (403, paywalled)

## Known coverage gaps
- Google Scholar not queried directly (blocks bots) — mitigated by searching the
  underlying sources it indexes.
- Two papers found but not readable in full: "Multi-Agent Orchestration of Local LLMs
  for Contract Review" (ACM, no free preprint found) and "NLP for the Legal Domain: A
  Survey" (ACM Computing Surveys, paywalled). Both flagged as follow-up items in
  literature_review.md.
- PDFs could not be bulk-downloaded into this folder — both the cloud environment and
  the local device's network egress reject arxiv.org at the proxy level (organization
  policy). Every note has a direct link instead; download individually as needed.
- This is a fast-moving area (5 of ~20 papers found are from the last 12 months) — worth
  re-running a similar search again closer to submission time in case something newer
  and closer has appeared.

## Follow-up search — 2026-09-26

Prompted by a planning discussion about extending beyond single-document
hypothesis-vs-clause contradiction detection to (a) within-document clause-vs-clause
contradictions and (b) cross-document clause-vs-clause contradictions.

### Queries run
1. cross-document contradiction detection dataset legal contracts
2. cross-document NLI contradiction dataset legal
3. ContractNLI 17 hypotheses dataset structure contradiction entailment

### Findings
- No existing dataset for cross-document contradiction detection between separate
  contracts. Closest matches: **Better Call CLAUSE** (within-document only, not
  cross-document) and **Clash-of-Leges** (cross-document, but statutory/constitutional
  law, not contracts).
- Full detail and the proposed path forward (using ContractNLI's own hypothesis labels
  to construct free cross-document pairs) written up in
  `notes/09-multilayer-contradiction-future-work.md` and summarized in
  `literature_review.md`'s new "Future work" section.
- One page could not be checked due to a rate limit: arxiv.org/html/2609.27014v1
  ("ContraVis: Evidence-Grounded Visual Analytics for Contradiction Review in Legal
  Contracts") — worth a manual look, title suggested it might be closer to this idea
  than it turned out other candidates were.
