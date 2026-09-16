"""
llm/ollama_client.py
────────────────────
Client for a locally-running Ollama server.

Public API (matches architecture123.md):
  class OllamaClient
    .generate(prompt: str, model: str | None = None) -> str
    .query_llm(clauses: list[str], hypothesis: str, triage_label: str = "") -> LLMResult

  Default timeout: 300 s (multi-clause CPU inference can take 180–240 s).
  generate() retries once on TimeoutError/OSError before raising
  OllamaConnectionError, so callers never see a raw TimeoutError.

  class OllamaConnectionError(RuntimeError)
  LLMResult dataclass: label, reasoning, cited_clauses, raw_response
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from backend.app.llm.prompts import build_reasoning_prompt, VALID_LABELS


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LLMResult:
    """Structured output from query_llm()."""
    label: str                            # one of VALID_LABELS
    reasoning: str
    cited_clauses: list[str] = field(default_factory=list)
    raw_response: str = ""                # unparsed LLM text (for debugging)


class OllamaConnectionError(RuntimeError):
    """Raised when the Ollama server is unreachable."""


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class OllamaClient:
    """
    HTTP client for a local Ollama inference server.

    Usage::

        client = OllamaClient(model="llama3.1:8b")
        result = client.query_llm(clause_text, hypothesis_text)
        print(result.label, result.reasoning)

    If Ollama is not running, `query_llm` raises OllamaConnectionError.
    Call `is_reachable()` first to guard gracefully.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 300,   # 300 s: multi-clause CPU inference can take 180-240 s
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model    = model
        self.timeout  = timeout

    # ------------------------------------------------------------------
    # Low-level: raw text generation
    # ------------------------------------------------------------------

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Send a prompt to Ollama and return the full response text.

        Args:
            prompt: The prompt string.
            model:  Override the instance default model.

        Returns:
            Raw response string from the LLM.

        Raises:
            OllamaConnectionError: if the server is not reachable.
            RuntimeError:          on non-200 HTTP responses.
        """
        import urllib.request
        import urllib.error
        import time

        target_model = model or self.model
        payload = json.dumps({
            "model":  target_model,
            "prompt": prompt,
            "stream": False,
            # temperature=0: greedy decoding — required for a classification /
            # judgment task.  Non-zero temperature caused the same document to
            # score 82.4 % in one run and 58.8 % in another with identical
            # retrieval (confirmed all gold-evidence clauses present in both).
            # top_p / top_k / repeat_penalty are deliberately omitted: they
            # are only consulted when tokens are sampled; at temperature=0 the
            # model always selects the argmax token, so they have no effect.
            "options": {"temperature": 0},
        }).encode("utf-8")

        url = f"{self.base_url}/api/generate"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.base_url}. "
                f"Is 'ollama serve' running?\nOriginal error: {exc}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            # Single retry after a short pause — handles transient load spikes.
            # If the retry also times out, raise OllamaConnectionError so the
            # caller's existing guard records this hypothesis as an error/skip
            # rather than crashing the whole script.
            print(
                f"        [TIMEOUT] {type(exc).__name__} on first attempt. "
                f"Retrying in 5 s ..."
            )
            time.sleep(5)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8")
            except (TimeoutError, OSError) as retry_exc:
                raise OllamaConnectionError(
                    f"Ollama timed out after {self.timeout}s (retry also failed). "
                    f"Consider reducing clause count or increasing timeout.\n"
                    f"First: {exc}  Retry: {retry_exc}"
                ) from retry_exc

        data = json.loads(body)
        return data.get("response", "")

    # ------------------------------------------------------------------
    # High-level: structured NLI query
    # ------------------------------------------------------------------

    def query_llm(
        self,
        clauses: list[str],
        hypothesis: str,
        triage_label: str = "",
    ) -> LLMResult:
        """
        Run NLI reasoning on one or more clauses against a hypothesis.

        All clauses are presented to the model in a single prompt call
        (labeled Clause A, B, …).  One generate() call, one label returned.

        Builds the prompt via prompts.build_reasoning_prompt(), calls generate(),
        and parses the JSON response. Falls back gracefully if JSON is malformed.

        Args:
            clauses:      List of contract clause texts (gap-filtered, 1 or more).
            hypothesis:   NDA hypothesis string.
            triage_label: Classifier pre-label (empty in Config A).

        Returns:
            LLMResult with label, reasoning, cited_clauses, raw_response.

        Raises:
            OllamaConnectionError: if the server is not reachable.
        """
        prompt = build_reasoning_prompt(clauses, hypothesis, triage_label)
        raw    = self.generate(prompt)

        return _parse_llm_response(raw)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def is_reachable(self) -> bool:
        """
        Return True if the Ollama server responds to a health check.
        Does NOT raise; always returns bool.
        """
        import urllib.request
        import urllib.error
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/api/tags", timeout=5
            ):
                return True
        except (urllib.error.URLError, OSError):
            return False


# ─────────────────────────────────────────────────────────────────────────────
# JSON response parsing
# ─────────────────────────────────────────────────────────────────────────────

# Sometimes models wrap JSON in a markdown fence — strip it.
_RE_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _parse_llm_response(raw: str) -> LLMResult:
    """
    Parse the LLM's response into an LLMResult.

    Strategy:
      1. Strip markdown fences if present.
      2. Try json.loads on the full string.
      3. If that fails, extract the first {...} block via regex.
      4. If all else fails, return NotMentioned with the raw text as reasoning.
    """
    text = raw.strip()

    # Strip markdown fence
    fence_match = _RE_JSON_FENCE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Attempt 1: parse the whole thing
    parsed = _try_parse_json(text)

    # Attempt 2: extract first {...} block
    if parsed is None:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            parsed = _try_parse_json(brace_match.group(0))

    if parsed is not None:
        label = str(parsed.get("label", "NotMentioned")).strip()
        # Normalise label to one of the valid set
        label = _normalise_label(label)
        reasoning    = str(parsed.get("reasoning", "")).strip()
        cited        = parsed.get("cited_clauses", [])
        cited_clauses = cited if isinstance(cited, list) else [str(cited)]
        return LLMResult(
            label=label,
            reasoning=reasoning,
            cited_clauses=cited_clauses,
            raw_response=raw,
        )

    # Fallback: could not parse JSON
    return LLMResult(
        label="NotMentioned",
        reasoning=f"[JSON parse failed] Raw response: {raw[:500]}",
        cited_clauses=[],
        raw_response=raw,
    )


def _try_parse_json(text: str) -> Optional[dict]:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _normalise_label(label: str) -> str:
    """Case-insensitive match to one of the three valid labels."""
    normalised = {v.lower(): v for v in VALID_LABELS}
    return normalised.get(label.lower(), "NotMentioned")
