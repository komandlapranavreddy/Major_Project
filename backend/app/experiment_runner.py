"""
experiment_runner.py
──────────────────────
Runs the three required experiment configurations (Project Guide §6.1) over
a set of ContractNLI documents, records every metric §6.2 asks for, persists
the run to disk, and reports McNemar significance between any two configs.

Public API (matches architecture123.md §4):
  run_experiment(config, documents, hypotheses, ...) -> ResultsDict
  compute_significance(results_a, results_b) -> McNemarResult

Configurations:
  A_no_triage         — every pair goes straight from retrieval to the LLM.
                        Triage never runs: no classifier latency, and no
                        triage pre-label in the prompt (prompts.py and
                        test_pipeline.py both define Config A that way).
  B_pretrained_triage — off-the-shelf cross-encoder/nli-deberta-v3-base,
                        zero ContractNLI fine-tuning (infer "pretrained" mode).
                        Same architecture as C, so B vs C isolates exactly the
                        effect of domain fine-tuning. Note this is a generic-NLI
                        baseline, not the Project Guide's original "existing
                        ContractNLI checkpoint (e.g. Span-NLI-BERT)" wording —
                        state that choice explicitly when writing up.
  C_finetuned_triage  — the project's own fine-tuned checkpoint.

Metrics recorded per run (Project Guide §6.2):
  • Classification — accuracy, macro P/R/F1, and per-class P/R/F1/support.
  • Efficiency     — % of pairs resolved with no LLM call, LLM call count,
                     end-to-end latency per query (mean ± SD, p50, p95),
                     broken out by routing branch, plus peak RSS / mean CPU.
  • Calibration    — ECE over the triage classifier's confidences, scored
                     against the gold label.
  • Rigor          — `repeats` re-measures latency over the same pairs so SD
                     is across real repeated runs, not a single pass; any pair
                     whose label changed between repeats is flagged `unstable`.

IMPORTANT — the calibration number this produces is NOT the same number as the
dev-split ECE in CLAUDE.md (0.0285). That one was measured with gold evidence
spans as the premise; this one scores the classifier on the premise it actually
receives in the deployed pipeline (the rank-1 retrieved clause). They are
different quantities and the gap between them is itself a reportable finding.

Runs are written to `results/<config>_<timestamp>.json` and can be reloaded
with `ResultsDict.load(path)`, so McNemar comparisons don't require re-running
the configs together in one process.

Run from the EdgeLegal_CodeBase root (same convention as test_pipeline.py):
    cd EdgeLegal_CodeBase && python -m backend.app.experiment_runner --configs A B C
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from backend.app.agent.graph import build_graph
from backend.app.embeddings.embedder import Embedder
from backend.app.llm.ollama_client import OllamaClient
from backend.app.parsing.clause_parser import segment_clauses
from backend.app.triage_model.evaluate import (
    ClassMetrics,
    ECEResult,
    Metrics,
    compute_calibration,
)
from backend.app.triage_model.infer import (
    DEFAULT_CHECKPOINT_PATH,
    PRETRAINED_SENTINEL,
    reset_cache,
)
from backend.app.triage_model.model import HF_CHECKPOINT
from backend.app.vectorstore.chroma_client import add_clauses, init_collection
from backend.app.logging_config import configure_logging, get_logger, log_exception, log_step

logger = get_logger(__name__)

Config = Literal["A_no_triage", "B_pretrained_triage", "C_finetuned_triage"]

# Resolved per run, never inherited from the previous run's environment —
# otherwise running B then C in one process would score C with B's model.
_DEFAULT_CHECKPOINTS: dict = {
    "B_pretrained_triage": PRETRAINED_SENTINEL,
    "C_finetuned_triage": DEFAULT_CHECKPOINT_PATH,
}

# Frozen on the ContractNLI dev split only, never on test (Project Guide §6.3).
# See CLAUDE.md "Frozen threshold" — do not change this to chase test numbers.
FROZEN_THRESHOLD = 0.95

# Checkpoint's native head order (dataset.LABEL2ID) — NOT alphabetical.
LABEL_ORDER: tuple[str, ...] = ("Contradiction", "Entailment", "NotMentioned")

CONFIG_ALIASES: dict[str, Config] = {
    "A": "A_no_triage",
    "B": "B_pretrained_triage",
    "C": "C_finetuned_triage",
}

DEFAULT_RESULTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "results")
)


# ─────────────────────────────────────────────────────────────────────────────
# Resource sampling (Project Guide §6.2 "resource usage")
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResourceUsage:
    available: bool
    peak_rss_mb: Optional[float] = None
    mean_cpu_percent: Optional[float] = None
    note: str = ""


class _ResourceSampler:
    """Best-effort peak-RSS / mean-CPU tracker. Degrades silently without psutil."""

    def __init__(self) -> None:
        self._proc = None
        self._peak_rss = 0.0
        self._cpu_samples: list[float] = []
        try:
            import psutil  # type: ignore

            self._proc = psutil.Process()
            self._proc.cpu_percent(interval=None)  # prime the first delta
            self._peak_rss = self._proc.memory_info().rss / 1048576
        except Exception:
            self._proc = None

    def sample(self) -> None:
        if self._proc is None:
            return
        try:
            self._peak_rss = max(self._peak_rss, self._proc.memory_info().rss / 1048576)
            self._cpu_samples.append(self._proc.cpu_percent(interval=None))
        except Exception:
            pass

    def result(self) -> ResourceUsage:
        if self._proc is None:
            return ResourceUsage(
                available=False,
                note="psutil not installed — RAM/CPU not recorded (Project Guide "
                     "§6.2 asks for it). Fix: pip install psutil",
            )
        active = [c for c in self._cpu_samples if c > 0]
        return ResourceUsage(
            available=True,
            peak_rss_mb=round(self._peak_rss, 1),
            mean_cpu_percent=round(statistics.fmean(active), 1) if active else None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Latency
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LatencyStats:
    n: int
    mean_s: float
    sd_s: float
    p50_s: float
    p95_s: float
    min_s: float
    max_s: float

    def __repr__(self) -> str:
        # ASCII only: this line gets piped into log files on Windows (cp1252),
        # where a literal "±" comes back as mojibake.
        return (
            f"{self.mean_s:.3f}s +/- {self.sd_s:.3f}  "
            f"(p50 {self.p50_s:.3f}s, p95 {self.p95_s:.3f}s, n={self.n})"
        )


def _percentile(sorted_vals: list, p: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _latency_stats(values) -> Optional[LatencyStats]:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return LatencyStats(
        n=len(vals),
        mean_s=statistics.fmean(vals),
        sd_s=statistics.stdev(vals) if len(vals) > 1 else 0.0,
        p50_s=_percentile(vals, 0.50),
        p95_s=_percentile(vals, 0.95),
        min_s=vals[0],
        max_s=vals[-1],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Result containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PredictionRow:
    doc_id: object
    hyp_id: str
    predicted: str
    gold: str
    source_engine: str                   # "classifier" | "llm"
    triage_confidence: Optional[float]
    triage_label: Optional[str] = None
    latencies_s: list = field(default_factory=list)   # one entry per repeat
    unstable: bool = False               # a repeat produced a different label
    error: Optional[str] = None          # set when the graph raised instead of returning

    @property
    def correct(self) -> bool:
        return self.predicted == self.gold

    @property
    def triage_correct(self) -> Optional[bool]:
        if self.triage_label is None:
            return None
        return self.triage_label == self.gold

    @property
    def mean_latency_s(self) -> Optional[float]:
        return statistics.fmean(self.latencies_s) if self.latencies_s else None


@dataclass
class McNemarResult:
    statistic: float
    p_value: float
    significant_at_05: bool
    b: int   # correct under A, wrong under B
    c: int   # wrong under A, correct under B

    def __repr__(self) -> str:
        verdict = "SIGNIFICANT" if self.significant_at_05 else "not significant"
        return (
            f"chi2={self.statistic:.4f}  p={self.p_value:.4f}  "
            f"b={self.b} c={self.c}  -> {verdict} at p<0.05"
        )


@dataclass
class ResultsDict:
    config: Config
    threshold: Optional[float]                # None for Config A (triage bypassed)
    rows: list = field(default_factory=list)  # list[PredictionRow]
    checkpoint_path: Optional[str] = None
    llm_provider: Optional[str] = None
    repeats: int = 1
    n_documents: int = 0
    resource: Optional[ResourceUsage] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    host: Optional[str] = None

    # ── Classification ────────────────────────────────────────────────────
    def _valid_rows(self) -> list:
        """Rows where the pipeline actually returned a prediction.

        Excludes pairs where the LLM call errored out (e.g. Groq's org-level
        rate limit outlasted the client's retry budget) — those are infra
        failures, not model predictions, and counting them as wrong would
        silently bias accuracy down. They're still visible via `error_count`
        and kept in `rows`/the saved JSON for debugging.
        """
        return [r for r in self.rows if r.error is None]

    @property
    def accuracy(self) -> float:
        valid = self._valid_rows()
        if not valid:
            return 0.0
        return sum(r.correct for r in valid) / len(valid)

    def classification_metrics(self) -> Metrics:
        """Accuracy + macro and per-class P/R/F1 (Project Guide §6.2)."""
        from sklearn.metrics import precision_recall_fscore_support

        valid = self._valid_rows()
        if not valid:
            return Metrics(0.0, 0.0, 0.0, 0.0, [])

        gold = [r.gold for r in valid]
        pred = [r.predicted for r in valid]

        p, r, f1, support = precision_recall_fscore_support(
            gold, pred, labels=list(LABEL_ORDER), zero_division=0
        )
        macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
            gold, pred, labels=list(LABEL_ORDER), average="macro", zero_division=0
        )
        return Metrics(
            accuracy=self.accuracy,
            macro_precision=float(macro_p),
            macro_recall=float(macro_r),
            macro_f1=float(macro_f1),
            per_class=[
                ClassMetrics(
                    label=label,
                    precision=float(p[i]),
                    recall=float(r[i]),
                    f1=float(f1[i]),
                    support=int(support[i]),
                )
                for i, label in enumerate(LABEL_ORDER)
            ],
        )

    # ── Efficiency ────────────────────────────────────────────────────────
    @property
    def llm_call_count(self) -> int:
        return sum(r.source_engine == "llm" for r in self._valid_rows())

    @property
    def escalation_rate(self) -> float:
        """Fraction of pairs that reached the LLM (always 1.0 for Config A)."""
        valid = self._valid_rows()
        if not valid:
            return 0.0
        return self.llm_call_count / len(valid)

    @property
    def no_llm_rate(self) -> float:
        """Fraction resolved without an LLM call — the efficiency headline."""
        return 1.0 - self.escalation_rate

    def latency(self) -> Optional[LatencyStats]:
        return _latency_stats([v for r in self._valid_rows() for v in r.latencies_s])

    def latency_by_engine(self) -> dict:
        out = {}
        for engine in ("classifier", "llm"):
            stats = _latency_stats(
                [v for r in self._valid_rows() if r.source_engine == engine
                 for v in r.latencies_s]
            )
            if stats is not None:
                out[engine] = stats
        return out

    # ── Calibration ───────────────────────────────────────────────────────
    def triage_calibration(self, n_bins: int = 10) -> Optional[ECEResult]:
        """
        ECE over the triage classifier's confidence, scored against gold.

        Measured on the premise the classifier actually receives in the
        pipeline (the rank-1 retrieved clause) — see this module's docstring
        on why this differs from the dev-split ECE in CLAUDE.md.
        """
        pairs = [
            (r.triage_confidence, r.triage_correct)
            for r in self._valid_rows()
            if r.triage_confidence is not None and r.triage_label is not None
        ]
        if not pairs:
            return None
        return compute_calibration(
            [c for c, _ in pairs], [ok for _, ok in pairs], n_bins=n_bins
        )

    # ── Integrity ─────────────────────────────────────────────────────────
    @property
    def unstable_count(self) -> int:
        return sum(r.unstable for r in self.rows)

    @property
    def error_count(self) -> int:
        """Pairs where the pipeline raised instead of returning a prediction."""
        return sum(r.error is not None for r in self.rows)

    @property
    def paper_grade(self) -> bool:
        """False when the run used a cloud LLM — see CLAUDE.md 'LLM provider switch'."""
        return (self.llm_provider or "").lower() != "groq"

    # ── Reporting ─────────────────────────────────────────────────────────
    def summary_text(self) -> str:
        n_hyp = len(self.rows) // self.n_documents if self.n_documents else 0
        lines: list[str] = []
        lines.append("=" * 72)
        threshold = "n/a, triage bypassed" if self.threshold is None else self.threshold
        lines.append(f"  {self.config}   (threshold={threshold})")
        lines.append("=" * 72)
        lines.append(f"Pairs              : {len(self.rows)} "
                     f"({self.n_documents} documents x {n_hyp} hypotheses)")
        lines.append(f"Checkpoint         : {self.checkpoint_path or 'n/a, triage bypassed'}")
        lines.append(f"LLM provider       : {self.llm_provider or 'ollama'}"
                     f"{'' if self.paper_grade else '   <-- NOT PAPER-GRADE'}")
        lines.append(f"Latency repeats    : {self.repeats}")
        lines.append("")
        lines.append("-- Classification (Guide 6.2) " + "-" * 42)
        lines.append(repr(self.classification_metrics()))
        lines.append("")
        lines.append("-- Efficiency (Guide 6.2) " + "-" * 46)
        lines.append(f"Resolved w/o LLM   : {self.no_llm_rate:.1%}")
        lines.append(f"LLM calls          : {self.llm_call_count} / {len(self.rows)}")
        overall = self.latency()
        lines.append(f"Latency / query    : {overall!r}" if overall
                     else "Latency / query    : (not measured)")
        for engine, stats in self.latency_by_engine().items():
            lines.append(f"  via {engine:<12}: {stats!r}")
        if self.resource is not None:
            if self.resource.available:
                lines.append(f"Peak RSS           : {self.resource.peak_rss_mb} MB")
                lines.append(f"Mean CPU           : {self.resource.mean_cpu_percent}%")
            else:
                lines.append(f"Resources          : {self.resource.note}")
        lines.append("")
        lines.append("-- Triage calibration (Guide 6.2) " + "-" * 37)
        ece = self.triage_calibration()
        lines.append(repr(ece) if ece is not None
                     else "(no triage confidences recorded)")
        if self.unstable_count:
            lines.append("")
            lines.append(f"WARNING: {self.unstable_count} pair(s) changed label between "
                         "repeats — the pipeline is not fully deterministic.")
        if self.error_count:
            lines.append("")
            lines.append(f"WARNING: {self.error_count} pair(s) errored out (e.g. Groq "
                         "rate limit outlasted retries) and were EXCLUDED from the "
                         "metrics above, not counted as wrong. Re-run with a smaller "
                         "batch or on Ollama to recover full coverage.")
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        metrics = self.classification_metrics()
        ece = self.triage_calibration()
        overall = self.latency()
        return {
            "config": self.config,
            "threshold": self.threshold,
            "checkpoint_path": self.checkpoint_path,
            "llm_provider": self.llm_provider,
            "paper_grade": self.paper_grade,
            "repeats": self.repeats,
            "n_documents": self.n_documents,
            "n_pairs": len(self.rows),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "host": self.host,
            "classification": {
                "accuracy": metrics.accuracy,
                "macro_precision": metrics.macro_precision,
                "macro_recall": metrics.macro_recall,
                "macro_f1": metrics.macro_f1,
                "per_class": [
                    {
                        "label": cm.label,
                        "precision": cm.precision,
                        "recall": cm.recall,
                        "f1": cm.f1,
                        "support": cm.support,
                    }
                    for cm in metrics.per_class
                ],
            },
            "efficiency": {
                "no_llm_rate": self.no_llm_rate,
                "escalation_rate": self.escalation_rate,
                "llm_calls": self.llm_call_count,
                "latency_overall": vars(overall) if overall else None,
                "latency_by_engine": {
                    k: vars(v) for k, v in self.latency_by_engine().items()
                },
                "resource": vars(self.resource) if self.resource else None,
            },
            "calibration": (
                {
                    "ece": ece.ece,
                    "n_bins": len(ece.bin_counts),
                    "bin_confidences": ece.bin_confidences,
                    "bin_accuracies": ece.bin_accuracies,
                    "bin_counts": ece.bin_counts,
                }
                if ece else None
            ),
            "integrity": {
                "unstable_pairs": self.unstable_count,
                "errored_pairs": self.error_count,
            },
            "rows": [
                {
                    "doc_id": r.doc_id,
                    "hyp_id": r.hyp_id,
                    "predicted": r.predicted,
                    "gold": r.gold,
                    "source_engine": r.source_engine,
                    "triage_label": r.triage_label,
                    "triage_confidence": r.triage_confidence,
                    "latencies_s": r.latencies_s,
                    "unstable": r.unstable,
                    "error": r.error,
                }
                for r in self.rows
            ],
        }

    def save(self, directory: Optional[str] = None, filename: Optional[str] = None) -> str:
        directory = directory or DEFAULT_RESULTS_DIR
        os.makedirs(directory, exist_ok=True)
        if filename is None:
            stamp = self.finished_at or datetime.now(timezone.utc).isoformat()
            stamp = stamp.replace(":", "").replace("-", "").split(".")[0]
            filename = f"{self.config}_{stamp}.json"
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "ResultsDict":
        """Reload a saved run so McNemar can be computed without re-running."""
        with open(path, encoding="utf-8") as fh:
            blob = json.load(fh)

        res = cls(
            config=blob["config"],
            threshold=blob["threshold"],
            checkpoint_path=blob.get("checkpoint_path"),
            llm_provider=blob.get("llm_provider"),
            repeats=blob.get("repeats", 1),
            n_documents=blob.get("n_documents", 0),
            started_at=blob.get("started_at"),
            finished_at=blob.get("finished_at"),
            host=blob.get("host"),
        )
        resource = (blob.get("efficiency") or {}).get("resource")
        if resource:
            res.resource = ResourceUsage(**resource)
        res.rows = [
            PredictionRow(
                doc_id=row["doc_id"],
                hyp_id=row["hyp_id"],
                predicted=row["predicted"],
                gold=row["gold"],
                source_engine=row["source_engine"],
                triage_confidence=row.get("triage_confidence"),
                triage_label=row.get("triage_label"),
                latencies_s=row.get("latencies_s", []),
                unstable=row.get("unstable", False),
                error=row.get("error"),
            )
            for row in blob.get("rows", [])
        ]
        return res


# ─────────────────────────────────────────────────────────────────────────────
# Checkpoint activation
# ─────────────────────────────────────────────────────────────────────────────

def _activate_checkpoint(checkpoint_path: str, allow_stub: bool) -> str:
    """
    Point triage_model.infer at `checkpoint_path` and clear its cached model.

    Both halves are mandatory, not defensive: infer.py caches the loaded model
    in a module global AND reads TRIAGE_CHECKPOINT_PATH from the environment,
    so skipping either one lets Config C silently run with Config B's model.
    Returns a human-readable description of what was activated, for the log.
    """
    if checkpoint_path.strip().lower() == PRETRAINED_SENTINEL:
        os.environ["TRIAGE_CHECKPOINT_PATH"] = PRETRAINED_SENTINEL
        reset_cache()
        return f"{PRETRAINED_SENTINEL}:{HF_CHECKPOINT} (no ContractNLI fine-tuning)"

    effective = os.path.abspath(checkpoint_path)
    os.environ["TRIAGE_CHECKPOINT_PATH"] = effective
    reset_cache()

    if not os.path.isfile(effective) and not allow_stub:
        raise RuntimeError(
            f"No triage checkpoint at '{effective}'.\n"
            "infer.predict() would fall back to the untrained lexical-overlap "
            "STUB and this run would produce meaningless accuracy and "
            "calibration numbers. Point --checkpoint-c (or "
            "TRIAGE_CHECKPOINT_PATH) at a real checkpoint, or pass "
            "--allow-stub if you are deliberately smoke-testing the plumbing."
        )
    return effective


def _llm_provider() -> str:
    # ollama_client calls load_dotenv() at import, so backend/.env is already applied.
    return os.getenv("LLM_PROVIDER", "ollama").lower()


# ─────────────────────────────────────────────────────────────────────────────
# The runner
# ─────────────────────────────────────────────────────────────────────────────

def run_experiment(
    config: Config,
    documents: list,
    hypotheses: dict,
    *,
    threshold: float = FROZEN_THRESHOLD,
    llm_client: Optional[OllamaClient] = None,
    gold_label_fn=None,
    repeats: int = 1,
    checkpoint_path: Optional[str] = None,
    allow_stub: bool = False,
    progress: bool = True,
) -> ResultsDict:
    """
    Run the full retrieve -> triage -> route -> (accept | LLM) pipeline over
    every (document, hypothesis) pair, recording Project Guide §6.2 metrics.

    Args:
        config:         Which configuration to run. Config A skips triage
                        entirely; B and C differ only in which model is loaded.
        documents:      ContractNLI-format documents, e.g. from
                        test_pipeline.load_test_documents().
        hypotheses:     {hyp_id: hypothesis_text}, from
                        test_pipeline.load_hypothesis_texts().
        threshold:      Frozen confidence threshold (default FROZEN_THRESHOLD,
                        selected on the dev split only). Ignored for Config A.
        llm_client:     Defaults to a real local OllamaClient(). Inject a fake
                        for tests — never default this to Groq; these numbers
                        are meant to be reproducible local results.
        gold_label_fn:  Defaults to test_pipeline.gold_label. Override only for
                        tests with synthetic documents.
        repeats:        How many times to re-measure latency over the same
                        pairs. §6.2 asks for mean ± SD across repeated
                        measurements, not a single run. Predictions are taken
                        from the first pass; later passes add latency samples
                        and flag any label that changed as `unstable`.
        checkpoint_path: Triage checkpoint for this config: a .pt path, or
                        "pretrained". None uses the config's default (B:
                        "pretrained", C: the fine-tuned checkpoint). Ignored
                        for Config A.
        allow_stub:     Permit the untrained stub classifier. Off by default so
                        a missing checkpoint fails loudly instead of quietly
                        producing fake numbers.

    Returns:
        ResultsDict with one PredictionRow per (document, hypothesis) pair.
    """
    if repeats < 1:
        raise ValueError("repeats must be >= 1")

    from backend.app.test_pipeline import doc_to_page_block

    if gold_label_fn is None:
        from backend.app.test_pipeline import gold_label as gold_label_fn
    if llm_client is None:
        llm_client = OllamaClient()

    skip_triage = config == "A_no_triage"
    if skip_triage:
        effective_checkpoint = None
        effective_threshold = None
    else:
        effective_checkpoint = _activate_checkpoint(
            checkpoint_path or _DEFAULT_CHECKPOINTS[config], allow_stub
        )
        effective_threshold = threshold

    log_step(logger, "experiment.start", config=config, n_documents=len(documents),
             n_hypotheses=len(hypotheses), threshold=effective_threshold,
             checkpoint=effective_checkpoint, repeats=repeats,
             llm_provider=_llm_provider())

    sampler = _ResourceSampler()
    embedder = Embedder()
    embedder.load()
    graph = build_graph()

    results = ResultsDict(
        config=config,
        threshold=effective_threshold,
        checkpoint_path=effective_checkpoint,
        llm_provider=_llm_provider(),
        repeats=repeats,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        host=f"{platform.system()} {platform.machine()} py{platform.python_version()}",
    )

    # ── Pass 0: parse + embed + index every document once ─────────────────
    prepared: list[tuple] = []
    skipped_empty = 0
    for i, doc in enumerate(documents, start=1):
        try:
            clauses = segment_clauses(doc_to_page_block(doc))
        except Exception:
            log_exception(logger, "Document preparation failed", doc_id=doc.get("id"),
                          progress=f"{i}/{len(documents)}")
            raise
        if not clauses:
            skipped_empty += 1
            logger.warning("Skipping doc_id=%s: segment_clauses() returned 0 clauses "
                           "(%d/%d prepared so far)", doc.get("id"), i, len(documents))
            continue
        try:
            collection = init_collection(f"experiment_doc_{doc['id']}")
            add_clauses(collection, clauses, embedder.embed([c.text for c in clauses]))
        except Exception:
            log_exception(logger, "Document indexing failed", doc_id=doc.get("id"),
                          n_clauses=len(clauses))
            raise
        prepared.append((doc, collection))
        if progress:
            msg = f"  [prep] {i}/{len(documents)} doc {doc['id']} ({len(clauses)} clauses)"
            print(msg, flush=True)
            logger.debug(msg)

    log_step(logger, "experiment.prep.done", n_prepared=len(prepared),
             n_skipped_empty=skipped_empty, config=config)
    results.n_documents = len(prepared)

    # ── Passes 1..repeats: invoke the graph, timing every pair ────────────
    rows_by_key: dict = {}
    total_pairs = len(prepared) * len(hypotheses)

    for rep in range(repeats):
        done = 0
        for doc, collection in prepared:
            for hyp_id, hyp_text in hypotheses.items():
                key = (doc["id"], hyp_id)
                started = time.perf_counter()
                try:
                    final_state = graph.invoke({
                        "document_id": str(doc["id"]),
                        "hypothesis": hyp_text,
                        "collection": collection,
                        "embedder": embedder,
                        "llm_client": llm_client,
                        "threshold": effective_threshold,
                        "skip_triage": skip_triage,
                    })
                except Exception as exc:
                    # A single pair failing (most commonly: Groq's org-level
                    # rate limit outlasting the client's own retry budget —
                    # see llm/groq_client.py) must not discard every other
                    # pair already computed in this run. Record it as an
                    # explicit error instead of a wrong prediction (excluded
                    # from accuracy/ECE/latency, not silently counted).
                    elapsed = time.perf_counter() - started
                    sampler.sample()
                    log_exception(
                        logger, "Pair failed - recorded as errored, continuing",
                        config=config, doc_id=doc["id"], hyp_id=hyp_id,
                        rep=rep + 1, done=done + 1, total_pairs=total_pairs,
                    )
                    if progress:
                        print(f"  [ERROR] doc={doc['id']} hyp={hyp_id}: "
                              f"{exc!r} - recorded as errored, continuing "
                              f"(full traceback in logs/edgelegal.log).",
                              flush=True)
                    if key not in rows_by_key:
                        rows_by_key[key] = PredictionRow(
                            doc_id=doc["id"],
                            hyp_id=hyp_id,
                            predicted="ERROR",
                            gold=gold_label_fn(doc, hyp_id),
                            source_engine="error",
                            triage_confidence=None,
                            error=repr(exc),
                        )
                    rows_by_key[key].latencies_s.append(elapsed)
                    done += 1
                    continue

                elapsed = time.perf_counter() - started
                sampler.sample()

                label = final_state.get("final_label") or "NotMentioned"

                if key not in rows_by_key:
                    rows_by_key[key] = PredictionRow(
                        doc_id=doc["id"],
                        hyp_id=hyp_id,
                        predicted=label,
                        gold=gold_label_fn(doc, hyp_id),
                        source_engine=final_state.get("source_engine") or "llm",
                        triage_confidence=final_state.get("triage_confidence"),
                        triage_label=final_state.get("triage_label"),
                    )
                elif rows_by_key[key].predicted != label:
                    rows_by_key[key].unstable = True

                rows_by_key[key].latencies_s.append(elapsed)
                done += 1

                if done % 50 == 0:
                    logger.info("[run %d/%d] %d/%d pairs (config=%s)",
                               rep + 1, repeats, done, total_pairs, config)
                    if progress:
                        print(f"  [run {rep + 1}/{repeats}] {done}/{total_pairs} pairs",
                              flush=True)

    results.rows = list(rows_by_key.values())
    results.resource = sampler.result()
    results.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log_step(logger, "experiment.done", config=config, n_rows=len(results.rows),
             n_errors=results.error_count, accuracy=round(results.accuracy, 4))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Significance
# ─────────────────────────────────────────────────────────────────────────────

def compute_significance(results_a: ResultsDict, results_b: ResultsDict) -> McNemarResult:
    """
    McNemar's paired significance test between two configurations run on the
    SAME (doc_id, hyp_id) pairs — required before claiming Config C beats A/B
    (Project Guide §6.2), since ContractNLI's test split (~150 contracts) is
    too small to trust an unpaired comparison.

    Args:
        results_a: ResultsDict from run_experiment() — the baseline.
        results_b: ResultsDict from run_experiment() — the comparison config.

    Returns:
        McNemarResult with the continuity-corrected chi-square statistic,
        p-value, and whether the difference is significant at p < 0.05.

    Raises:
        ValueError: if the two results don't cover the exact same pairs.
    """
    from scipy.stats import chi2

    index_a = {(r.doc_id, r.hyp_id): r for r in results_a.rows}
    index_b = {(r.doc_id, r.hyp_id): r for r in results_b.rows}

    if index_a.keys() != index_b.keys():
        raise ValueError(
            "results_a and results_b must cover the exact same (doc_id, hyp_id) "
            "pairs — run both configs on the same test split."
        )

    b = 0  # A correct, B wrong
    c = 0  # A wrong, B correct
    for key, row_a in index_a.items():
        row_b = index_b[key]
        if row_a.correct and not row_b.correct:
            b += 1
        elif not row_a.correct and row_b.correct:
            c += 1

    if b + c == 0:
        return McNemarResult(statistic=0.0, p_value=1.0, significant_at_05=False, b=b, c=c)

    statistic = (abs(b - c) - 1) ** 2 / (b + c)
    p_value = float(1 - chi2.cdf(statistic, df=1))

    return McNemarResult(
        statistic=statistic,
        p_value=p_value,
        significant_at_05=p_value < 0.05,
        b=b,
        c=c,
    )


def comparison_table(runs: dict) -> str:
    """Side-by-side §6.2 headline table plus every pairwise McNemar test."""
    lines = ["", "=" * 72, "  CROSS-CONFIG COMPARISON (Project Guide 6.2)", "=" * 72]
    header = (f"{'Config':<22}{'Acc':>8}{'MacroF1':>10}"
              f"{'NoLLM%':>9}{'Lat(s)':>10}{'ECE':>8}")
    lines.append(header)
    lines.append("-" * len(header))
    for name, res in runs.items():
        metrics = res.classification_metrics()
        latency = res.latency()
        ece = res.triage_calibration()
        lines.append(
            f"{name:<22}{metrics.accuracy:>8.4f}{metrics.macro_f1:>10.4f}"
            f"{res.no_llm_rate * 100:>8.1f}%"
            f"{(latency.mean_s if latency else 0):>10.3f}"
            f"{(ece.ece if ece else float('nan')):>8.4f}"
        )

    names = list(runs)
    if len(names) > 1:
        lines.append("")
        lines.append("McNemar (paired, continuity-corrected):")
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                try:
                    mc = compute_significance(runs[a], runs[b])
                    lines.append(f"  {a} vs {b}: {mc!r}")
                except ValueError as exc:
                    lines.append(f"  {a} vs {b}: SKIPPED — {exc}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Configs A/B/C on ContractNLI and report Guide 6.2 metrics.",
    )
    parser.add_argument("--configs", nargs="+", default=["A", "B", "C"],
                        choices=["A", "B", "C"],
                        help="Which configurations to run (default: all three).")
    parser.add_argument("--threshold", type=float, default=FROZEN_THRESHOLD,
                        help=f"Frozen dev-split threshold (default {FROZEN_THRESHOLD}). "
                             "Never retune this against test.")
    parser.add_argument("--repeats", type=int, default=1,
                        help="Latency measurement passes over the same pairs "
                             "(use >=3 for the final paper numbers).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Use only the first N documents (for smoke runs).")
    parser.add_argument("--checkpoint-b", default=None,
                        help=f"Checkpoint for Config B: a .pt path, or "
                             f"'{PRETRAINED_SENTINEL}' (default) = off-the-shelf "
                             f"{HF_CHECKPOINT} with no ContractNLI fine-tuning.")
    parser.add_argument("--checkpoint-c", default=None,
                        help="Fine-tuned checkpoint for Config C (default: "
                             "triage_model/checkpoints/current/best_model.pt).")
    parser.add_argument("--out", default=None,
                        help=f"Results directory (default {DEFAULT_RESULTS_DIR}).")
    parser.add_argument("--no-save", action="store_true",
                        help="Print results without writing JSON.")
    parser.add_argument("--allow-stub", action="store_true",
                        help="Permit the untrained stub classifier (plumbing tests only).")
    parser.add_argument("--log-level", default=None,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Console log verbosity (default: $EDGELEGAL_LOG_LEVEL or "
                             "INFO). The log file always captures DEBUG regardless — "
                             "see logs/edgelegal.log.")
    args = parser.parse_args()

    configure_logging(console_level=args.log_level)
    logger.info("=== experiment_runner CLI start: configs=%s threshold=%s "
                "repeats=%s limit=%s ===",
                args.configs, args.threshold, args.repeats, args.limit)

    from backend.app.test_pipeline import load_hypothesis_texts, load_test_documents

    documents = load_test_documents()
    if args.limit:
        documents = documents[: args.limit]
    hypotheses = load_hypothesis_texts()
    log_step(logger, "cli.data_loaded", n_documents=len(documents),
             n_hypotheses=len(hypotheses))

    if _llm_provider() == "groq":
        logger.warning("LLM_PROVIDER=groq - results from this run are NOT paper-grade.")
        print("\n" + "!" * 72)
        print("  LLM_PROVIDER=groq — these are NOT paper-grade numbers.")
        print("  Groq is a cloud GPU: it cannot demonstrate the inference cost")
        print("  the triage layer exists to cut, and it breaks the local/private")
        print("  claim. Switch backend/.env to LLM_PROVIDER=ollama before")
        print("  generating any number that goes into the paper (CLAUDE.md).")
        print("!" * 72 + "\n")

    checkpoints = {
        "B_pretrained_triage": args.checkpoint_b or _DEFAULT_CHECKPOINTS["B_pretrained_triage"],
        "C_finetuned_triage": args.checkpoint_c or _DEFAULT_CHECKPOINTS["C_finetuned_triage"],
    }

    if ("B" in args.configs and "C" in args.configs
            and checkpoints["B_pretrained_triage"] == checkpoints["C_finetuned_triage"]):
        print("WARNING: Config B and Config C resolve to the same checkpoint, so "
              "the B-vs-C comparison is meaningless.\n")

    runs: dict = {}
    for alias in args.configs:
        config = CONFIG_ALIASES[alias]
        print(f"\n>>> Running {config} on {len(documents)} documents x "
              f"{len(hypotheses)} hypotheses ...")
        result = run_experiment(
            config,
            documents,
            hypotheses,
            threshold=args.threshold,
            repeats=args.repeats,
            checkpoint_path=checkpoints.get(config),
            allow_stub=args.allow_stub,
        )
        print()
        print(result.summary_text())
        if not args.no_save:
            print(f"\nSaved -> {result.save(args.out)}")
        runs[config] = result

    if len(runs) > 1:
        print(comparison_table(runs))


if __name__ == "__main__":
    main()
