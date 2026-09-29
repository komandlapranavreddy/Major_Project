export interface ReportCitation {
  id: string;
  text: string;
  page: number;
  bbox?: number[];
}

export interface ReportResult {
  label: 'Entailment' | 'Contradiction' | 'NotMentioned';
  reasoning: string;
  cited_clauses: ReportCitation[];
  /** Which engine produced this label. Undefined for pipelines that don't route through the triage agent. */
  source?: 'classifier' | 'llm';
  /** Triage classifier's confidence in [0, 1], present when source === 'classifier'. */
  confidence?: number;
  /** The routing agent's own step, for the "how this was decided" panel. Absent when no agent ran. */
  triage?: TriageDetail;
}

export interface CalibrationBin {
  confidence: number;
  accuracy: number;
  count: number;
}

export interface ThresholdSweepPoint {
  tau: number;
  coverage: number;
  macro_f1: number;
  accuracy: number;
  n_above: number;
}

export interface ConfigResult {
  config: string;
  label: string;
  status: 'complete' | 'pending';
  accuracy: number | null;
  macro_f1: number | null;
  llm_call_count: number | null;
  avg_latency_s: number | null;
  /** False when the run used cloud Groq rather than local Ollama — these are not paper-grade numbers. */
  paper_grade: boolean | null;
  /** (document, hypothesis) pairs evaluated in this run. */
  n_pairs: number | null;
  /** Pairs that failed and were excluded from the metrics, not counted as wrong. */
  errored_pairs: number | null;
  /** UTC ISO-8601 time the run finished. */
  run_at: string | null;
}

export interface ResearchMetrics {
  triage_eval_available: boolean;
  generated_at: string | null;
  dataset_split: string | null;
  n_examples: number | null;
  accuracy: number | null;
  macro_f1: number | null;
  ece: number | null;
  calibration_bins: CalibrationBin[];
  frozen_threshold: number;
  threshold_sweep: ThresholdSweepPoint[];
  configs: ConfigResult[];
}

export interface TriageDetail {
  /** The triage classifier's own predicted label. */
  label: string | null;
  /** The triage classifier's own confidence in [0, 1], pre-routing (present even when escalated). */
  confidence: number | null;
  /** The frozen confidence threshold used to route this request. */
  threshold: number;
  /** 'accept' (resolved by the classifier) or 'escalate' (sent to the LLM). */
  decision: 'accept' | 'escalate';
}

export interface HistoryItem {
  id: number;
  document_id: string;
  filename: string;
  hypothesis: string;
  label: ReportResult['label'];
  confidence: number | null;
  source: 'classifier' | 'llm' | null;
  created_at: string;
}

export interface HistoryPage {
  items: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface HistoryDocument {
  id: string;
  filename: string;
  uploaded_at: string;
  page_count: number | null;
  analysis_count: number;
}

export interface TopHypothesis {
  hypothesis: string;
  contradiction_count: number;
}

export interface Analytics {
  documents_analyzed: number;
  total_analyses: number;
  total_contradictions: number;
  /** Fraction in [0, 1], not a percentage. */
  contradiction_rate: number;
  top_hypotheses: TopHypothesis[];
  /** null when no classifier-sourced analyses exist yet. */
  avg_classifier_confidence: number | null;
  classifier_count: number;
  llm_count: number;
}
