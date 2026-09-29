# Agentic / tool-use retrieval papers (grounding for the cross-reference retrieval feature)

Relevant if the cross-reference retrieval agent feature discussed earlier gets built
(an LLM autonomously issuing a follow-up retrieval call when a clause references another
section it hasn't seen, e.g. "Except as provided in Section 4...").

## ReAct
Shunyu Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023.
- arXiv: https://arxiv.org/abs/2210.03629

The foundational "reasoning + tool-calling interleaved" agent pattern. Standard citation
for any LLM that autonomously decides to take an action (like an extra retrieval call)
mid-reasoning rather than following a fixed pipeline.

## Self-RAG
Akari Asai et al. "Self-RAG: Learning to Retrieve, Generate, and Critique through
Self-Reflection." ICLR 2024.
- arXiv: https://arxiv.org/abs/2310.11511

Trains a model to decide *when* retrieval is needed and to critique its own generations
against retrieved evidence. Relevant precedent for "the model decides whether it has
enough context," which is exactly the judgment call your cross-reference feature would
need to make.

## Adaptive-RAG
Already covered in note 02 (LLM cascades) — also directly relevant here as the
small-classifier-decides-retrieval-strategy pattern.

## How to use these
If you build the cross-reference retrieval feature, cite ReAct for the general
tool-use-agent framing and Self-RAG for the "model decides it needs more context"
framing specifically. Keep the actual implementation simple (a conditional second
retrieval call keyed on detecting a cross-reference pattern like "Section \d+" in the
clause text) — you don't need to reproduce either paper's full training setup, just
their conceptual framing for how to describe the feature honestly in the paper.
