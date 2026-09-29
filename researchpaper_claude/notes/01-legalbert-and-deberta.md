# The two candidate triage-classifier backbones

## LEGAL-BERT
**Citation:** Ilias Chalkidis, Manos Fergadiotis, Prodromos Malakasiotis, Nikolaos Aletras, Ion Androutsopoulos. "LEGAL-BERT: The Muppets straight out of Law School." Findings of EMNLP 2020.
- arXiv: https://arxiv.org/abs/2010.02559
- ACL Anthology (PDF): https://aclanthology.org/2020.findings-emnlp.261.pdf
- Weights: https://huggingface.co/nlpaueb/legal-bert-base-uncased

Domain-pretrained BERT on legal text (contracts, legislation, court cases). Strong track record on legal clause classification / NER; not itself an NLI-specific architecture.

## DeBERTa / DeBERTaV3
**Citation:** Pengcheng He et al. "DeBERTa: Decoding-enhanced BERT with Disentangled Attention." ICLR 2021.
- arXiv: https://arxiv.org/abs/2006.03654
**DeBERTaV3:** He et al. "DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing." 2021.
- arXiv: https://arxiv.org/abs/2111.09543
- Weights: https://huggingface.co/microsoft/deberta-v3-small (the size the Project Guide targets)

Disentangled attention processes premise and hypothesis jointly from layer 1 — the architectural reason the Project Guide gives for preferring it over a BiLSTM for this pairwise NLI task. Well-supported, non-legal-domain alternative to LegalBERT.

**Relevance:** These are the two candidate backbones named in the Project Guide (Section 3) for the triage classifier. No new search needed to justify picking one over the other beyond what the Guide already argues; cite both papers directly for the architecture choice.
