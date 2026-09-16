"""
llm/prompts.py
──────────────
Prompt templates for the LLM reasoning step.

Public API (matches architecture123.md):
  build_reasoning_prompt(clauses, hypothesis, triage_label="") -> str
"""

from __future__ import annotations

# Valid labels — keep in sync with the triage model's label set.
VALID_LABELS = ("Entailment", "Contradiction", "NotMentioned")

# Label letters used in the multi-clause prompt (A, B, C, …)
_CLAUSE_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def build_reasoning_prompt(
    clauses: list[str],
    hypothesis: str,
    triage_label: str = "",
) -> str:
    """
    Build the LLM prompt for NLI reasoning on one or more clauses vs. a hypothesis.

    For Configuration A (no-triage), triage_label is always empty.
    For Configuration B/C, triage_label carries the classifier's pre-label.

    All clauses that passed the adaptive gap filter are presented together in
    a single prompt (labeled Clause A, Clause B, …).  The model must examine
    all of them and return ONE final label.

    The prompt instructs the model to respond with ONLY valid JSON:
        {
          "label": "Entailment" | "Contradiction" | "NotMentioned",
          "reasoning": "...",
          "cited_clauses": ["..."]
        }

    Args:
        clauses:      List of contract clause texts (1 or more).
        hypothesis:   The NDA hypothesis to evaluate.
        triage_label: Pre-label from the triage classifier (empty in Config A).

    Returns:
        Formatted prompt string.
    """
    triage_section = ""
    if triage_label:
        triage_section = (
            f"\nA fast classifier has pre-labelled this pair as: "
            f"**{triage_label}**. Confirm or override based on your reading.\n"
        )

    # Build the labeled clause block
    clause_lines = []
    for idx, text in enumerate(clauses):
        label = _CLAUSE_LABELS[idx] if idx < len(_CLAUSE_LABELS) else str(idx + 1)
        clause_lines.append(f"Clause {label}:\n{text}")
    clauses_block = "\n\n".join(clause_lines)

    plural = "S" if len(clauses) > 1 else ""

    prompt = f"""You are a legal NLI expert reviewing a Non-Disclosure Agreement (NDA).

Your task: determine whether the CONTRACT CLAUSE{plural} below entail, contradict, or
do not mention the HYPOTHESIS. Examine ALL provided clauses together in this one pass.
{triage_section}
HYPOTHESIS:
{hypothesis}

CONTRACT CLAUSE{plural} (examine all):

{clauses_block}

Instructions:
- Choose exactly ONE label: Entailment, Contradiction, or NotMentioned.
  * Entailment    — at least one clause DIRECTLY and SPECIFICALLY supports the
                    hypothesis. The connection must be explicit in the text, not
                    inferred or implied.
  * Contradiction — at least one clause DIRECTLY conflicts with the hypothesis.
                    The conflict must be clear and specific, not a matter of
                    interpretation.
  * NotMentioned  — none of the clauses genuinely address the hypothesis.
                    If the connection requires inference or guessing, or the
                    clause only tangentially relates, use NotMentioned.
- Err strongly on the side of NotMentioned when in doubt.
- Cite the specific clause letter (A, B, …) and the verbatim excerpt that
  drove your decision.
- Be concise in your reasoning (2–4 sentences).

Respond with ONLY valid JSON — no markdown, no preamble, no trailing text:
{{
  "label": "<Entailment|Contradiction|NotMentioned>",
  "reasoning": "<your reasoning here>",
  "cited_clauses": ["<verbatim excerpt 1>", "..."]
}}"""

    return prompt
