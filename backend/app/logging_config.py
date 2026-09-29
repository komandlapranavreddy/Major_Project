"""
logging_config.py
───────────────────
One logging setup shared by both pipelines in this repo.

Why this exists: before this file, the codebase used bare `print()` for
almost everything (Groq rate-limit messages, Ollama routing warnings, the
triage stub warning, experiment progress) and a handful of unconfigured
`logging.getLogger(__name__)` calls in main.py that, without a configured
handler, silently do nothing below WARNING and never touch disk. That meant
two problems in practice: (1) a crash 40 minutes into an experiment run left
no record of what happened in the preceding 39 minutes once the terminal
scrolled past it, and (2) a live-app 500 error showed the client a one-line
`str(e))` with no server-side trace of which pipeline step actually failed.

What this gives every module that uses it:
  - A single "sequence of steps" trail: `log_step()` writes one line per
    pipeline stage (retrieve -> triage -> route -> accept/escalate, etc.)
    with the inputs that mattered, so a failure's log context reconstructs
    exactly what led up to it, not just where it happened.
  - `log_exception()` always logs the full traceback (`exc_info=True`) plus
    structured context (doc_id, hyp_id, config, ...) — never just the
    exception's string, which is what `str(e)` in an HTTPException detail
    or a bare `except: print(e)` throws away.
  - Everything also lands in `EdgeLegal_CodeBase/logs/edgelegal.log`
    (rotating, 10MB x 5 backups) at DEBUG regardless of what the console
    shows, so a run's full detail survives even if the console was quiet.

Two import roots, one process (see CLAUDE.md "Working conventions"):
research-pipeline files import this as `backend.app.logging_config`;
live-app files import it as `app.logging_config`. Both names can resolve to
this same file inside one process (agent/live_service.py puts both roots on
sys.path), which would otherwise double-configure and duplicate every log
line. `configure_logging()` guards against that by stamping a flag directly
on the process-global root logger object, not on this module — so it stays
idempotent no matter which import name triggered it, or how many times.

Public API:
  get_logger(name: str) -> logging.Logger
      Configures logging on first call (if not already configured) and
      returns a standard logger. Use `get_logger(__name__)` per module.
  log_step(logger, step: str, **context) -> None
      One structured line marking a pipeline stage.
  log_exception(logger, msg: str, **context) -> None
      Logs the current exception's full traceback plus context. Call this
      from inside an `except` block, then re-raise (or handle) as needed —
      it does not swallow or raise anything itself.
  configure_logging(console_level=None) -> None
      Explicit setup call; idempotent. get_logger() calls this
      automatically, so most code never needs to call it directly. main.py
      and experiment_runner.py call it explicitly at startup so the level
      is set before any other module's get_logger() call locks it in.

Controlling verbosity:
  EDGELEGAL_LOG_LEVEL env var (DEBUG/INFO/WARNING/ERROR) sets the CONSOLE
  level; default INFO. The log FILE always captures DEBUG regardless, so
  turning console noise down never loses detail from the saved log.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

_CONFIGURED_ATTR = "_edgelegal_logging_configured"

# EdgeLegal_CodeBase/logs/edgelegal.log — this file lives at
# EdgeLegal_CodeBase/backend/app/logging_config.py, so parent x3.
_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "edgelegal.log"

_FMT = "%(asctime)s %(levelname)-8s %(name)-32s %(funcName)s:%(lineno)d | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Third-party loggers that are chatty at DEBUG and drown out our own lines
# in the log file; capped at WARNING regardless of our own level.
_NOISY_THIRD_PARTY = (
    "httpx", "httpcore", "urllib3", "chromadb", "sentence_transformers",
    "transformers", "torch", "PIL", "fontTools", "groq",
)


def configure_logging(console_level: "str | int | None" = None) -> None:
    """
    Set up the console + rotating file handlers on the root logger, once.

    Safe to call multiple times or from multiple modules/import-paths — the
    guard is a flag on the actual root logger object (process-global), not
    on this module, so re-importing this file under a different name (e.g.
    `app.logging_config` vs `backend.app.logging_config` in the same
    process — see this module's docstring) never double-attaches handlers.

    Handlers are attached only once, but an explicit `console_level` is
    still honored on a later call even after that — e.g. a CLI's
    `--log-level` flag calling this in `main()`, after some earlier
    `get_logger(__name__)` at another module's import time already
    triggered the default setup. Without this, the CLI flag would be
    silently ignored, since setup already "happened".
    """
    root = logging.getLogger()
    if getattr(root, _CONFIGURED_ATTR, False):
        if console_level is not None:
            changed = False
            for handler in root.handlers:
                # RotatingFileHandler subclasses FileHandler subclasses
                # StreamHandler — exclude it so this only touches the
                # console handler, never the always-DEBUG file handler.
                if isinstance(handler, logging.StreamHandler) and not isinstance(
                    handler, logging.FileHandler
                ):
                    handler.setLevel(console_level)
                    changed = True
            if changed:
                logging.getLogger(__name__).info(
                    "Console log level changed to %s", console_level
                )
        return
    setattr(root, _CONFIGURED_ATTR, True)

    if console_level is None:
        console_level = os.getenv("EDGELEGAL_LOG_LEVEL", "INFO").upper()

    root.setLevel(logging.DEBUG)  # handlers below do the actual filtering
    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        file_ok = True
    except OSError as exc:
        file_ok = False
        file_err = exc

    for name in _NOISY_THIRD_PARTY:
        logging.getLogger(name).setLevel(logging.WARNING)

    startup = logging.getLogger(__name__)
    startup.info(
        "Logging configured: console=%s file=%s",
        console_level, _LOG_FILE if file_ok else f"DISABLED ({file_err})",
    )


def get_logger(name: str) -> logging.Logger:
    """Configure logging (idempotent, first call only) and return a logger."""
    configure_logging()
    return logging.getLogger(name)


def log_step(logger: logging.Logger, step: str, **context) -> None:
    """
    Mark one pipeline stage with its relevant inputs/decisions.

    Use this at every meaningful stage transition (retrieve -> triage ->
    route -> accept/escalate; upload -> parse -> index; etc.) so that when
    something fails, the log file already contains the exact sequence of
    steps that ran beforehand and what each one saw — not just the
    exception itself.

    Example: log_step(logger, "triage.done", label="Entailment", conf=0.97)
    """
    if context:
        ctx = " ".join(f"{k}={v!r}" for k, v in context.items())
        logger.info("STEP %-22s | %s", step, ctx)
    else:
        logger.info("STEP %s", step)


def log_exception(logger: logging.Logger, msg: str, **context) -> None:
    """
    Log the current exception's full traceback plus structured context.

    Call this from inside an `except` block (relies on `sys.exc_info()`
    still being set); does not swallow, handle, or re-raise anything — the
    caller decides what to do with the exception afterward.

    Example (inside `except Exception as exc:`):
        log_exception(logger, "triage_predict failed", doc_id=doc_id,
                      hyp_id=hyp_id, clause_len=len(top_clause.text))
        raise
    """
    if context:
        ctx = " ".join(f"{k}={v!r}" for k, v in context.items())
        logger.error("FAILED %s | %s", msg, ctx, exc_info=True)
    else:
        logger.error("FAILED %s", msg, exc_info=True)
