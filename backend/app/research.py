"""
app/research.py
────────────────
Serves the real evaluation artifacts backend/app/triage_model/
verify_checkpoint.py produces (dev-set accuracy/calibration/threshold
sweep) to GET /research/metrics, for the frontend's /research page.

No fabricated numbers: the calibration and sweep data are read straight
from that script's own JSON output, produced by one real inference pass
over the dev set. The Config A/B/C comparison stays 'pending' until
experiment_runner.py has actually been run and produces its own output —
there is no fallback that invents those numbers.
"""

import glob
import json
import os

RESULTS_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "triage_model", "dev_eval_results.json"
)

# experiment_runner.py writes one JSON per config run here, named
# "<config>_<UTC timestamp>.json" (see its ResultsDict.save()).
EXPERIMENT_RESULTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "results")
)

# The three required experiment configs (Project Guide §6.1 / CLAUDE.md).
# Real config ids, not placeholders — only the numbers are pending.
_CONFIG_NAMES = [
    ("A_no_triage", "Config A — No triage (LLM only)"),
    ("B_pretrained_triage", "Config B — Pretrained triage"),
    ("C_finetuned_triage", "Config C — Fine-tuned triage"),
]


def _pending_config(key: str, label: str) -> dict:
    return {
        "config": key,
        "label": label,
        "status": "pending",
        "accuracy": None,
        "macro_f1": None,
        "llm_call_count": None,
        "avg_latency_s": None,
        "paper_grade": None,
        "n_pairs": None,
        "errored_pairs": None,
        "run_at": None,
    }


def _latest_run_for(config_key: str) -> dict | None:
    """
    Newest saved run for one config, or None if it has never been run.

    Filenames embed a UTC timestamp, but they're not lexically sortable
    across all formats, so sort by mtime — the file's own write time is
    what "latest run" actually means here.
    """
    pattern = os.path.join(EXPERIMENT_RESULTS_DIR, f"{config_key}_*.json")
    paths = glob.glob(pattern)
    if not paths:
        return None

    for path in sorted(paths, key=os.path.getmtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            # A truncated file from an interrupted run shouldn't blank out
            # the whole page — fall through to the next-newest one.
            continue
    return None


def _load_experiment_configs() -> list[dict]:
    """
    Real Config A/B/C numbers from results/*.json, falling back to
    'pending' per config that hasn't been run. Nothing is estimated: a
    config with no result file stays pending rather than being inferred
    from the others.
    """
    configs = []
    for key, label in _CONFIG_NAMES:
        blob = _latest_run_for(key)
        if blob is None:
            configs.append(_pending_config(key, label))
            continue

        classification = blob.get("classification") or {}
        efficiency = blob.get("efficiency") or {}
        latency = efficiency.get("latency_overall") or {}
        integrity = blob.get("integrity") or {}

        configs.append({
            "config": key,
            "label": label,
            "status": "complete",
            "accuracy": classification.get("accuracy"),
            "macro_f1": classification.get("macro_f1"),
            "llm_call_count": efficiency.get("llm_calls"),
            "avg_latency_s": latency.get("mean_s"),
            # False when the run used Groq. Surfaced so the page can't
            # quietly present cloud-LLM numbers as the paper's results —
            # see CLAUDE.md "LLM provider switch".
            "paper_grade": blob.get("paper_grade"),
            "n_pairs": blob.get("n_pairs"),
            "errored_pairs": integrity.get("errored_pairs"),
            "run_at": blob.get("finished_at"),
        })
    return configs


def get_research_metrics() -> dict:
    configs = _load_experiment_configs()

    if not os.path.isfile(RESULTS_JSON_PATH):
        return {
            "triage_eval_available": False,
            "generated_at": None,
            "dataset_split": None,
            "n_examples": None,
            "accuracy": None,
            "macro_f1": None,
            "ece": None,
            "calibration_bins": [],
            "frozen_threshold": 0.95,
            "threshold_sweep": [],
            "configs": configs,
        }

    with open(RESULTS_JSON_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    cal = data["calibration"]
    calibration_bins = [
        {"confidence": c, "accuracy": a, "count": n}
        for c, a, n in zip(cal["bin_confidences"], cal["bin_accuracies"], cal["bin_counts"])
        if n > 0
    ]

    return {
        "triage_eval_available": True,
        "generated_at": data.get("generated_at"),
        "dataset_split": data["dataset"]["split"],
        "n_examples": data["dataset"]["n_examples"],
        "accuracy": data["metrics"]["accuracy"],
        "macro_f1": data["metrics"]["macro_f1"],
        "ece": cal["ece"],
        "calibration_bins": calibration_bins,
        "frozen_threshold": data.get("frozen_threshold", 0.95),
        "threshold_sweep": data["threshold_sweep"],
        "configs": configs,
    }
