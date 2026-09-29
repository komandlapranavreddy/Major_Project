import os
import re
import threading
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

try:
    # This file previously had zero `backend.app.*` dependencies (stdlib +
    # groq/dotenv only). Falling back to a plain logger (rather than letting
    # this import fail) preserves that if it's ever imported from a context
    # without the repo root on sys.path (e.g. via live_service.py's `app.`
    # import path, or a future standalone use of this module).
    from backend.app.logging_config import get_logger, log_exception, log_step
except ImportError:
    import logging as _logging

    def get_logger(name):
        return _logging.getLogger(name)

    def log_step(logger, step, **context):
        logger.info("STEP %s | %s", step, context)

    def log_exception(logger, msg, **context):
        logger.error("FAILED %s | %s", msg, context, exc_info=True)

logger = get_logger(__name__)

# Ensure .env is loaded from backend directory
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class GroqKeyRotator:
    """
    Manages a cyclical pool of Groq API keys with thread-safe rotation
    when rate limits (HTTP 429) or quota exhaustion occurs.
    """
    def __init__(self, keys: Optional[List[str]] = None, default_model: str = "openai/gpt-oss-20b"):
        if keys:
            self.keys = [k.strip() for k in keys if k.strip()]
        else:
            raw_keys = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
            self.keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
            
        self.default_model = os.getenv("GROQ_MODEL", default_model)
        self.current_idx = 0
        self._lock = threading.Lock()
        if self.keys:
            masked = [f"...{k[-6:]}" for k in self.keys]
            logger.info("GroqKeyRotator initialized with %d key(s): %s, model=%s",
                        len(self.keys), masked, self.default_model)
        else:
            logger.warning("GroqKeyRotator initialized with 0 keys - "
                           "any chat() call will fail immediately.")
        
    @property
    def has_keys(self) -> bool:
        return len(self.keys) > 0
        
    def get_current_key(self) -> str:
        with self._lock:
            if not self.keys:
                raise ValueError("No Groq API keys configured in environment or .env")
            return self.keys[self.current_idx % len(self.keys)]
            
    def rotate_to_next_key(self) -> str:
        with self._lock:
            if not self.keys:
                raise ValueError("No Groq API keys configured.")
            prev_key = self.keys[self.current_idx % len(self.keys)]
            self.current_idx = (self.current_idx + 1) % len(self.keys)
            next_key = self.keys[self.current_idx]
            logger.warning(
                "Key ...%s rate-limited/failed. Rotated to key ...%s (index %d/%d)",
                prev_key[-6:], next_key[-6:], self.current_idx + 1, len(self.keys),
            )
            return next_key

    @staticmethod
    def _retry_after_seconds(exc: Exception, default: float) -> float:
        """
        Extract Groq's suggested wait time from a rate-limit error.

        NOTE: all keys in this rotator are typically issued under the same
        Groq organization, so rotating keys does NOT reset the org-level
        TPM/RPM limit that produced this error — only waiting does. Prefer
        the `Retry-After` response header when the SDK exposes it; fall back
        to parsing "Please try again in 1.26s" / "...in 375ms" from the
        error message, since that's what Groq actually returns.
        """
        response = getattr(exc, "response", None)
        header = getattr(response, "headers", {}) if response is not None else {}
        try:
            if header and "retry-after" in header:
                return max(float(header["retry-after"]), 0.1)
        except (TypeError, ValueError):
            pass

        match = re.search(r"try again in ([\d.]+)(ms|s)\b", str(exc))
        if match:
            value, unit = match.groups()
            seconds = float(value) / 1000.0 if unit == "ms" else float(value)
            return max(seconds, 0.1)

        return default

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        response_format: Optional[Dict[str, str]] = None,
        temperature: float = 0.0
    ) -> str:
        """
        Sends a chat completion request to Groq. Automatically rotates
        keys and retries if a RateLimitError or 429 status code is encountered.
        """
        try:
            from groq import Groq, RateLimitError, APIStatusError
        except ImportError:
            logger.error("groq package is not installed - cannot make any chat() call.")
            raise ImportError("groq package is not installed. Run: pip install groq")

        if not self.has_keys:
            logger.error("chat() called with 0 Groq keys configured.")
            raise ValueError("No Groq API keys found. Please set GROQ_API_KEYS in backend/.env")

        target_model = model or self.default_model
        # Keys usually share one Groq org, so cycling through them doesn't
        # reset an org-level rate limit — only waiting does. Allow enough
        # rounds through the key list, each preceded by an actual sleep on
        # rate-limit errors, to ride out a full TPM window (~60s) rather
        # than failing the whole experiment run over one busy minute.
        rounds = max(3, len(self.keys))
        total_attempts = len(self.keys) * rounds
        max_total_wait_s = 90.0

        log_step(logger, "groq.chat.start", model=target_model,
                 n_messages=len(messages), n_keys=len(self.keys))

        last_exception = None
        waited_s = 0.0
        for attempt in range(total_attempts):
            key = self.get_current_key()
            try:
                client = Groq(api_key=key)
                kwargs: Dict[str, Any] = {
                    "messages": messages,
                    "model": target_model,
                    "temperature": temperature,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                completion = client.chat.completions.create(**kwargs)
                content = completion.choices[0].message.content or ""
                logger.debug("groq.chat.done attempt=%d/%d response_len=%d",
                            attempt + 1, total_attempts, len(content))
                return content

            except RateLimitError as e:
                last_exception = e
                if waited_s >= max_total_wait_s:
                    logger.warning(
                        "RateLimitError, but already waited %.0fs - giving up "
                        "on this attempt. %s", waited_s, e,
                    )
                    self.rotate_to_next_key()
                    continue
                wait_s = self._retry_after_seconds(e, default=1.0)
                logger.warning(
                    "RateLimitError: %s. Waiting %.2fs then rotating keys "
                    "(shared org TPM limit - rotation alone won't clear this)...",
                    e, wait_s,
                )
                time.sleep(wait_s)
                waited_s += wait_s
                self.rotate_to_next_key()
            except APIStatusError as e:
                if e.status_code == 429 or "rate_limit" in str(e).lower():
                    last_exception = e
                    if waited_s >= max_total_wait_s:
                        logger.warning(
                            "429, but already waited %.0fs - giving up on this "
                            "attempt. %s", waited_s, e,
                        )
                        self.rotate_to_next_key()
                        continue
                    wait_s = self._retry_after_seconds(e, default=1.0)
                    logger.warning(
                        "429 Rate Limit encountered: %s. Waiting %.2fs then "
                        "rotating keys...", e, wait_s,
                    )
                    time.sleep(wait_s)
                    waited_s += wait_s
                    self.rotate_to_next_key()
                else:
                    # Other API error (invalid key, bad payload, etc.) — not a
                    # rate limit, so no point waiting; just try the next key.
                    logger.error("APIStatusError (%s): %s", e.status_code, e)
                    last_exception = e
                    self.rotate_to_next_key()
            except Exception as e:
                logger.error("Unexpected error calling Groq: %r", e, exc_info=True)
                last_exception = e
                self.rotate_to_next_key()

        # log_exception() needs live exception context (sys.exc_info()) and
        # we're past every `except` block here, so pass last_exception's own
        # traceback explicitly via exc_info instead — it still has one
        # attached from when it was caught above.
        logger.error(
            "All Groq API keys exhausted or failed after %d attempts "
            "(waited %.1fs total, model=%s)",
            total_attempts, waited_s, target_model,
            exc_info=last_exception if last_exception is not None else False,
        )
        raise RuntimeError(f"All Groq API keys were exhausted or failed. Last error: {last_exception}")

# Module-level singleton
groq_client = GroqKeyRotator()
