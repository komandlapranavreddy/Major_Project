# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: demo audiences and evaluators — a thesis panel, paper reviewers,
and recruiters/engineers viewing it as a resume project. They watch or try a
live run and judge whether the mechanism is real and well built.

Legal reviewers checking NDAs are the product's story and intended future
user, not today's actual user.

## Product Purpose

EdgeLegal checks a contract for clause-level contradictions against a fixed
set of hypotheses. A user uploads a contract PDF, picks a hypothesis, and gets
a verdict (Entailment / Contradiction / NotMentioned) with the exact clauses
and pages it is based on, highlighted in the document.

Success: a viewer understands the verdict, trusts it because the evidence is
shown, and sees the confidence-gated mechanism working.

## Positioning

A small fine-tuned NLI classifier acts as a confidence-gated triage layer in
front of an LLM: confident cases are accepted directly, uncertain ones are
escalated. The goal is fewer LLM calls without losing accuracy, and only if
the classifier's confidence is actually calibrated.

Do not claim the system runs locally / on the edge. It is planned to be
deployed as a hosted web app (frontend on Vercel, backend on Render) and
currently uses a cloud LLM (Groq) in the live app.

## Operating Context

- Input: contract PDFs (NDAs, ContractNLI-style).
- Flow in `/app`: upload -> choose hypothesis -> analysis -> report with
  clickable citations that jump to the source in the PDF viewer.
- `/` is the landing page that explains the product and links into `/app`.

## Capabilities and Constraints

- Dataset: ContractNLI — 607 NDAs, 17 fixed hypotheses, labels Entailment /
  Contradiction / NotMentioned.
- Triage classifier: DeBERTa-v3-base NLI cross-encoder, fine-tuned, with a
  frozen confidence threshold for escalation.
- Retrieval over parsed clauses, LLM reasoning for escalated cases.
- Undecided: final unification of the research and live pipelines; Config
  A/B/C experiment results are not yet run.

## Evidence on Hand

- Real: the dataset, the method, the trained checkpoint, the working app.
- Absent: accuracy, cost-saving, latency, or LLM-call-reduction numbers.
  Do not show or imply any of these until Configs A/B/C are run.
- No customers, testimonials, or deployment claims exist. Do not invent them.

## Product Principles

1. Every verdict shows its evidence — clause text and page, never a bare label.
2. Show the mechanism honestly: confidence and whether a result was escalated.
3. No fabricated numbers or claims; unfinished results are labeled pending.
4. Demo clarity first: a first-time viewer should follow the flow unaided.
