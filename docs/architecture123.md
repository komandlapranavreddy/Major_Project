# EdgeLegal — Architecture & Function Outline

Confidence-routed legal contradiction detection. One job per component — the
NLI classifier predicts, the agent routes, the LLM reasons, nothing else
blurs those lines.

## 1. Data Flow

```
Contract PDF
   → PDF Extractor (PyMuPDF)
   → Clause Parser (structure-aware segmentation)
   → [Embedder → ChromaDB]  +  [Triage Classifier → label + confidence]
   → LangGraph Agent (confidence >= threshold?)
        YES → accept classifier label, no LLM call
        NO  → escalate to Local LLM (Ollama) → confirm/override + explanation
   → Report Generator → Final Contradiction Report
```

## 2. Components

| Component | Does | Does NOT do |
|---|---|---|
| PDF Extractor | Text + page/coordinate metadata | Classification/reasoning |
| Clause Parser | Segment into retrievable clause units | Predict labels |
| Embedder | Vectorize clauses for retrieval | Predict entailment |
| ChromaDB | Store/retrieve embeddings + metadata | Model inference |
| Triage Classifier (DeBERTa/LegalBERT) | Fast label + confidence | Explain why |
| LangGraph Agent | Orchestrate, apply threshold, decide escalation | Predict, explain |
| Local LLM (Ollama) | Deep reasoning, explanation, override | Handle every case |
| Report Generator | Assemble final report | Any prediction logic |

## 3. Backend Function Outline

### `parsing/pdf_extractor.py`
- `extract_pages(pdf_path: str) -> list[PageBlock]`
  Runs PyMuPDF over the file; returns one `PageBlock` per page: `{text, page_num, bbox}`. No parsing of clause boundaries here.

### `parsing/clause_parser.py`
- `segment_clauses(pages: list[PageBlock]) -> list[Clause]`
  Splits page text into clause-level units using heading/numbering patterns. Each `Clause`: `{id, text, page_num, section_heading}`.
- `detect_section_heading(line: str) -> str | None`
  Helper — regex/heuristic check for numbered/titled section headers.

### `embeddings/embedder.py`
- `class Embedder`
  - `load(model_name: str = "BAAI/bge-small-en")`
  - `embed(texts: list[str]) -> np.ndarray` — batched encode, returns vectors for ChromaDB.

### `vectorstore/chroma_client.py`
- `init_collection(name: str) -> Collection`
- `add_clauses(collection, clauses: list[Clause], embeddings: np.ndarray) -> None`
- `query(collection, query_text: str, k: int = 5, *, with_scores: bool = False, embedder=None, query_embedding=None) -> list`
  — `with_scores=False` (default): returns `list[Clause]`; `with_scores=True`: returns `list[(Clause, float)]` pairs (cosine distance).
- `gap_filter(candidates: list[(Clause, float)], gap_threshold: float = GAP_THRESHOLD) -> list[(Clause, float)]`
  — Adaptive cutoff: always keeps Rank-1; drops subsequent candidates when a relative gap > `GAP_THRESHOLD` (default 15%) appears.

### `triage_model/model.py`
- `class TriageModel`
  - `load(checkpoint_path: str)` — loads fine-tuned DeBERTa/LegalBERT weights.
  - `forward(premise: str, hypothesis: str) -> torch.Tensor` — raw logits over {Entailment, Contradiction, NotMentioned}.

### `triage_model/train.py`
- `main(config: TrainConfig) -> None` — entrypoint (epochs=3–5, lr=2e-5).
- `train_epoch(model, dataloader, optimizer) -> float` — one pass, returns avg loss.
- `run_early_stopping(model, val_loader, patience: int) -> Checkpoint` — stops on validation **F1**, not accuracy (class imbalance).

### `triage_model/evaluate.py`
- `evaluate(model, test_split) -> MetricsDict` — accuracy/precision/recall/F1 per class.
- `compute_calibration(confidences: list[float], correct: list[bool]) -> ECEResult` — reliability diagram + Expected Calibration Error. Required, not optional.
- `select_threshold(val_confidences, val_labels, candidates: list[float]) -> float` — sweeps 0.60–0.95 on **validation only**, freezes best accuracy-preserving threshold.

### `triage_model/infer.py`
- `predict(clause: str, hypothesis: str) -> tuple[str, float]` — single-pair inference used at runtime; returns `(label, confidence)`.

### `agent/graph.py`
- `build_graph() -> StateGraph` — wires the LangGraph nodes/edges below into the routing pipeline.

### `agent/nodes.py`
- `retrieve_node(state) -> state` — pulls relevant clauses from ChromaDB for the active hypothesis.
- `triage_node(state) -> state` — calls `infer.predict`, attaches `(label, confidence)` to state.
- `confidence_check_node(state) -> state` — compares confidence to frozen threshold, sets `route = "accept" | "escalate"`.
- `call_llm_node(state) -> state` — only reached on escalation; calls the LLM client, merges its output into state.

### `llm/ollama_client.py`
- `class OllamaClient`
  - `generate(prompt: str, model: str = "llama3.1:8b") -> str` — raw call to local Ollama server.
  - `query_llm(clauses: list[str], hypothesis: str, triage_label: str) -> LLMResult` — builds multi-clause prompt, makes a single `generate()` call, parses structured JSON output `{label, reasoning, cited_clauses}`.

### `llm/prompts.py`
- `build_reasoning_prompt(clauses: list[str], hypothesis: str, triage_label: str) -> str` — template presenting all gap-filtered clauses (labeled A, B, …) and requesting a single final label in JSON.

### `report/report_generator.py`
- `generate_report(results: list[ClauseResult]) -> Report` — assembles label, confidence, source (classifier/LLM), evidence clause(s), explanation.
- `export_report(report: Report, fmt: str = "json") -> str` — writes report to disk, returns path.

### `app/main.py` (FastAPI)
- `POST /upload` — accepts contract PDF, triggers extraction + parsing + embedding.
- `POST /analyze` — runs the LangGraph pipeline against a given hypothesis set, returns report.
- `GET /report/{id}` — fetches a previously generated report.
- `GET /health` — liveness check.

## 4. Experiment Runner (Section 6 configs)

- `run_experiment(config: Literal["A_no_triage", "B_pretrained_triage", "C_finetuned_triage"]) -> ResultsDict`
  Runs the full pipeline in one of three modes on the same test split:
  - **A** — every pair forced to `call_llm_node` (triage bypassed).
  - **B** — triage uses an unmodified pretrained ContractNLI checkpoint.
  - **C** — triage uses the fine-tuned model from `triage_model/train.py`.
- `compute_significance(results_a, results_b) -> McNemarResult` — paired significance test between configs.

## 5. Frontend (React) — Feature Outline

- **Upload** — drag/drop or file picker → `POST /upload`, shows extraction progress.
- **Hypothesis/Chat panel** — select or type a hypothesis to check clauses against.
- **Report view** — per-clause label, confidence, source (classifier vs LLM), explanation.
- **PDF viewer** — renders the contract with clause highlights linked to report entries (page + bbox from `PageBlock`).

## 6. Frozen Constraints (do not violate mid-build)

- Threshold is selected on validation only, frozen before any test-split run.
- BiLSTM, GNN clause modeling, multi-document/multi-language, federated/active learning, RL-based thresholds — all out of scope, Future Work only.
- Every function above stays inside its component's single responsibility per Section 2's table.
