from pydantic import BaseModel, Field
from typing import List, Optional

class UploadResponse(BaseModel):
    doc_id: str
    message: str

class AnalyzeRequest(BaseModel):
    doc_id: str
    hypothesis: str

class ReportCitation(BaseModel):
    id: str
    text: str
    page: int
    bbox: Optional[List[float]] = None

class TriageDetail(BaseModel):
    label: Optional[str] = Field(default=None, description="The triage classifier's own predicted label.")
    confidence: Optional[float] = Field(
        default=None, description="The triage classifier's own confidence in [0, 1], pre-routing."
    )
    threshold: float = Field(..., description="The frozen confidence threshold used to route this request.")
    decision: str = Field(..., description="'accept' (resolved by the classifier) or 'escalate' (sent to the LLM).")

class ReportResult(BaseModel):
    label: str = Field(..., description="Must be Entailment, Contradiction, or NotMentioned")
    reasoning: str
    cited_clauses: List[ReportCitation]
    source: Optional[str] = Field(
        default=None,
        description="Which engine produced the label: 'classifier' or 'llm'. "
                    "None for callers (e.g. the live demo's rag_engine.py) "
                    "that don't run through the triage-routing agent.",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Triage classifier's confidence in [0, 1], when source='classifier'. "
                    "None on the LLM path or when source is unset.",
    )
    triage: Optional[TriageDetail] = Field(
        default=None,
        description="The routing agent's own step, for the 'how this was decided' panel. "
                    "Present whenever the request went through the agent, regardless of "
                    "which branch (accept/escalate) it took; None when no agent ran "
                    "(e.g. document had no extractable clauses).",
    )

class HistoryItem(BaseModel):
    id: int
    document_id: str
    filename: str
    hypothesis: str
    label: str
    confidence: Optional[float] = None
    source: Optional[str] = None
    created_at: str

class HistoryPage(BaseModel):
    items: List[HistoryItem]
    total: int
    limit: int
    offset: int

class HistoryDocument(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    page_count: Optional[int] = None
    analysis_count: int

class TopHypothesis(BaseModel):
    hypothesis: str
    contradiction_count: int

class CalibrationBin(BaseModel):
    confidence: float = Field(..., description="Mean predicted confidence of examples in this bin.")
    accuracy: float = Field(..., description="Actual accuracy of examples in this bin.")
    count: int

class ThresholdSweepPoint(BaseModel):
    tau: float
    coverage: float = Field(..., description="Fraction of dev examples at or above this threshold.")
    macro_f1: float
    accuracy: float
    n_above: int

class ConfigResult(BaseModel):
    config: str = Field(..., description="Machine-readable config id, e.g. 'A_no_triage'.")
    label: str
    status: str = Field(..., description="'complete' or 'pending' — pending until experiment_runner.py is run.")
    accuracy: Optional[float] = None
    macro_f1: Optional[float] = None
    llm_call_count: Optional[int] = None
    avg_latency_s: Optional[float] = None
    paper_grade: Optional[bool] = Field(
        default=None,
        description="False when the run used a cloud LLM (Groq) rather than local Ollama. "
                    "Surfaced so cloud-sourced numbers are never silently presented as the "
                    "paper's results — see CLAUDE.md 'LLM provider switch'. None when pending.",
    )
    n_pairs: Optional[int] = Field(
        default=None, description="(document, hypothesis) pairs evaluated in this run."
    )
    errored_pairs: Optional[int] = Field(
        default=None,
        description="Pairs that failed (e.g. rate limit) and were excluded from the metrics "
                    "above rather than counted as wrong.",
    )
    run_at: Optional[str] = Field(default=None, description="UTC ISO-8601 time the run finished.")

class ResearchMetrics(BaseModel):
    triage_eval_available: bool = Field(
        ..., description="False until backend/app/triage_model/verify_checkpoint.py has been run."
    )
    generated_at: Optional[str] = None
    dataset_split: Optional[str] = None
    n_examples: Optional[int] = None
    accuracy: Optional[float] = None
    macro_f1: Optional[float] = None
    ece: Optional[float] = Field(default=None, description="Expected Calibration Error on the dev split.")
    calibration_bins: List[CalibrationBin] = []
    frozen_threshold: float = 0.95
    threshold_sweep: List[ThresholdSweepPoint] = []
    configs: List[ConfigResult] = Field(
        default_factory=list, description="Config A/B/C comparison — real once run, otherwise 'pending'."
    )

class Analytics(BaseModel):
    documents_analyzed: int
    total_analyses: int
    total_contradictions: int
    contradiction_rate: float = Field(..., description="Fraction in [0, 1], not a percentage.")
    top_hypotheses: List[TopHypothesis]
    avg_classifier_confidence: Optional[float] = Field(
        default=None, description="None when no classifier-sourced analyses exist yet."
    )
    classifier_count: int
    llm_count: int
