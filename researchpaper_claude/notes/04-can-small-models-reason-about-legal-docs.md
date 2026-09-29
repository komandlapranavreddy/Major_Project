# Can Small Models Reason About Legal Documents? A Comparative Study

- arXiv: https://arxiv.org/abs/2603.25944 (~March 2026, very recent)

## What it does
Evaluates 9 models (7 open-weight, 3B-9B parameters, plus GPT-4o-mini and Claude 3.5
Haiku) across 3 legal benchmarks — **ContractNLI**, CaseHOLD, and ECtHR — using 5
prompting strategies (direct, chain-of-thought, few-shot, BM25 RAG, dense RAG). 405
total experiments, bootstrap confidence intervals, McNemar's test between models. Total
cost: $62 via cloud APIs, no dedicated GPU — relevant data point for your own
no-GPU-team situation.

## Key finding
A Mixture-of-Experts model activating only 3B parameters roughly matches GPT-4o-mini on
average and beats it on legal holding identification. Architecture/training quality
matters more than raw parameter count. Best results still lag published fine-tuned
baselines by 3.5-4.1 points, so prompting-only small models aren't quite there yet.

## What it does NOT do (the gap)
Zero discussion of calibration, confidence scoring, or routing/escalation to a larger
model based on predicted difficulty. It's a pure "how good is small model X at zero/few-
shot legal reasoning" comparison — not a triage or cascade system at all. It supports
your premise (small models are viable on ContractNLI specifically) without touching your
actual research question (can a small model's *confidence* be trusted to *route*).

## Relevance
Good supporting citation for "small models are a credible choice for legal NLI tasks
including ContractNLI specifically" — strengthens your motivation section. Not a
competing paper.
