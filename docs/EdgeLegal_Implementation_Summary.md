> **OUTDATED (marked 2026-09-29):** this summary dates from August 2026. Its "~40% complete" claim and its description of the app pipeline no longer match the code. See `CLAUDE.md` at the repo root for the current state.

# EdgeLegal — In-Depth Technical Implementation & Architectural Mapping Guide

**Document Classification:** Comprehensive Codebase Reference & Architecture Coverage Report  
**Target Milestone:** Configuration A (No-Triage RAG Baseline) + Data Ingestion & Evaluation Suite  
**Document Purpose:** Detailed conceptual, algorithmic, and architectural walkthrough of every implemented Python component in the EdgeLegal system, along with an explicit section-by-section mapping to the project's master documentation.

---

## 1. High-Level Executive Summary of Current Build

The EdgeLegal repository currently implements the **entire foundational RAG and baseline reasoning infrastructure** (designated as **Configuration A** in the project specifications). 

Rather than attempting to build the entire dual-tier system in one monolithic pass, the codebase establishes a verified, mathematically sound baseline. It handles the complete lifecycle of a contract: downloading and validating standard benchmark datasets, segmenting legal text into structure-aware clauses, vectorizing clauses with dense embeddings, indexing them in ChromaDB with dynamic noise filtering, and conducting multi-clause natural language inference (NLI) through a local LLM running in Ollama.

---

## 2. In-Depth Technical Walkthrough by Subsystem

```
                                  EDGELEGAL IMPLEMENTED PIPELINE
                                  
  [ContractNLI / Raw Text]
             │
             ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │ 1. INGESTION & PARSING (clause_parser.py)                                              │
  │    • Structural boundary detection (Regex for 1.1, (a), (iv), ALL-CAPS, Recitals)      │
  │    • Contextual heading preservation across page splits                                │
  └──────────────────────────────────┬─────────────────────────────────────────────────────┘
                                     │ Normalized Clause Objects
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │ 2. DENSE VECTOR EMBEDDING (embedder.py)                                                │
  │    • SentenceTransformer wrapping BAAI/bge-small-en (384 dimensions)                   │
  │    • Batch-vectorized L2-normalized float32 representations                            │
  └──────────────────────────────────┬─────────────────────────────────────────────────────┘
                                     │ Dense Vectors
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │ 3. VECTOR STORAGE & ADAPTIVE RETRIEVAL (chroma_client.py)                              │
  │    • ChromaDB Ephemeral / Persistent collection management                             │
  │    • Adaptive Gap Filtering: Rank-1 preservation + 15% relative distance cutoff        │
  └──────────────────────────────────┬─────────────────────────────────────────────────────┘
                                     │ Candidate Evidentiary Clauses
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │ 4. LOCAL GENERATIVE REASONING (prompts.py & ollama_client.py)                          │
  │    • Multi-clause prompt labeling (Clause A, Clause B, ...)                            │
  │    • Greedy decoding (temperature=0) for deterministic legal judgment                  │
  │    • 3-stage resilient JSON extraction (Fence stripping -> loads -> Regex fallback)    │
  └──────────────────────────────────┬─────────────────────────────────────────────────────┘
                                     │ Structured Prediction: {Label, Reasoning, Cited}
                                     ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │ 5. BENCHMARKING & DIAGNOSTIC SUITE (retrieval_accuracy_check.py & test_pipeline.py)     │
  │    • Zero-LLM gold-span retrieval validation across 123 test contracts                 │
  │    • 4-Phase end-to-end evaluation & failure root-cause analysis                       │
  └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2.1. Subsystem 1: Document Ingestion & Structure-Aware Parsing
**Primary File:** [`edgelegal/backend/app/parsing/clause_parser.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/parsing/clause_parser.py)

#### Algorithmic & Design Rationale:
* **The Failure of Naive Chunking:** Standard RAG systems split text by fixed character lengths (e.g., 500 characters) or token counts with sliding window overlaps. In legal contracts, naive chunking destroys logical cohesion—a clause stating *"Except as provided in Section 4, neither party shall..."* becomes useless if severed from Section 4 or broken across arbitrary sentence boundaries.
* **Structural Parsing State Machine:** `clause_parser.py` implements a structure-aware segmentation engine. It processes pages as `PageBlock` objects and splits text strictly along legal paragraph and numbering boundaries.
* **Heading & Section Hierarchy:** The module maintains internal state while traversing the contract:
  1. *Numbered Section Matcher:* Recognizes hierarchical legal enumerations such as `1.`, `1.1`, `1.1.1`, `(a)`, `(iv)`.
  2. *ALL-CAPS Heading Matcher:* Detects standard legal section titles (e.g., `CONFIDENTIALITY OBLIGATIONS`, `NON-SOLICITATION`, `GOVERNING LAW`).
  3. *Recital & Preamble Handlers:* Identifies preliminary recitals initiated by `WHEREAS` or `NOW, THEREFORE`.
* **Context Inheritance:** When sub-clauses (e.g., `(a)`, `(b)`) are parsed, they inherit the parent section heading in their metadata. When retrieved downstream, the LLM receives the clause with its full structural title, ensuring the legal scope is not lost.

---

### 2.2. Subsystem 2: Dense Semantic Embeddings
**Primary File:** [`edgelegal/backend/app/embeddings/embedder.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/embeddings/embedder.py)

#### Algorithmic & Design Rationale:
* **Model Selection:** The module encapsulates `BAAI/bge-small-en` using HuggingFace's `sentence-transformers` library. This model maps English sentences into a 384-dimensional dense vector space.
* **Why BGE-Small on Edge Hardware:** Unlike massive 1024-dimensional embedding models (such as `bge-large` or OpenAI `text-embedding-3-large`), `bge-small-en` offers a tiny memory footprint (~130 MB) and executes forward passes rapidly on standard laptop CPUs without requiring dedicated GPU acceleration.
* **Normalization & Memory Handling:** The wrapper automatically handles batching (default batch size of 32) and normalizes output vectors using the Euclidean ($L_2$) norm. Normalized vectors allow ChromaDB to compute cosine similarity using standard dot products, maximizing retrieval speed.

---

### 2.3. Subsystem 3: Vector Storage & Adaptive Gap Filtering
**Primary File:** [`edgelegal/backend/app/vectorstore/chroma_client.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/vectorstore/chroma_client.py)

#### Algorithmic & Design Rationale:
* **Client Architecture:** Supports both an in-memory `EphemeralClient` (for temporary, zero-retention analysis sessions) and a disk-persisted ChromaDB client.
* **The Noise Problem in Legal Retrieval:** In standard semantic search, querying for Top-$K$ (e.g., $K=5$) always forces the database to return 5 items, even if only 1 clause in the entire NDA is relevant. The other 4 weakly similar clauses act as distractor noise, confusing the LLM and causing false-positive contradictions.
* **The Adaptive Gap Filter Algorithm:** `chroma_client.py` solves this by introducing a dynamic cutoff mechanism:
  1. Retrieve candidate clauses ranked by ascending cosine distance ($d_0 \le d_1 \le d_2 \le \dots \le d_{k-1}$).
  2. The Rank-1 candidate ($d_0$) is **always preserved** as the primary candidate.
  3. For every subsequent candidate $i$, the algorithm computes the relative distance jump:
     $$\text{Relative Gap} = \frac{d_i - d_{i-1}}{d_{i-1}}$$
  4. If this relative jump exceeds the `GAP_THRESHOLD` (default **15%**), all candidates from index $i$ onward are immediately discarded.
* **Outcome:** If a contract has only one strongly matching confidentiality clause, the filter returns only that 1 clause. If the contract has 3 tightly clustered non-solicitation clauses with similar relevance, all 3 are passed. This prevents context pollution and reduces downstream inference latency.

---

### 2.4. Subsystem 4: Prompt Formulation & Multi-Clause Context
**Primary File:** [`edgelegal/backend/app/llm/prompts.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/llm/prompts.py)

#### Algorithmic & Design Rationale:
* **Unified Multi-Clause Evaluation:** When the Adaptive Gap Filter returns multiple candidates (e.g., Clause 3 and Clause 7 both touch upon termination), `prompts.py` packages them into a single, structured prompt labeled as `Clause A: ...` and `Clause B: ...`.
* **Single-Pass Inference:** Rather than calling the LLM multiple times per clause (which multiplies latency and cost), the model evaluates all surviving candidates in a single pass against the hypothesis.
* **Strict JSON Grammar Enforcement:** The prompt defines rigid behavioral rules forcing the model to output valid JSON conforming to:
  ```json
  {
    "label": "Entailment | Contradiction | NotMentioned",
    "reasoning": "Direct explanation citing specific clause phrases...",
    "cited_clauses": ["Clause A"]
  }
  ```
* **The Triage Pre-Label Hook:** The prompt function includes an optional parameter `triage_label: str = ""`. In Configuration A (current build), this is left empty. In future Configurations B and C, this parameter automatically injects a pre-classification hint (e.g., *"The triage classifier pre-classified this as: Contradiction. Confirm or override based on your reading."*), allowing small LLMs to operate with higher accuracy by verifying prior predictions rather than reasoning from a blank slate.

---

### 2.5. Subsystem 5: Resilient Local LLM Inference
**Primary File:** [`edgelegal/backend/app/llm/ollama_client.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/llm/ollama_client.py)

#### Algorithmic & Design Rationale:
* **Target Environment:** Interfaces directly with local Ollama daemons over HTTP (`localhost:11434`), defaulting to `llama3.1:8b`.
* **Greedy Decoding for Reproducibility:** Sets `temperature: 0` in all API payloads. For legal NLI classification, non-zero temperatures introduce stochastic variance (the exact same contract scoring 82% in one run and 58% in another). Greedy decoding guarantees deterministic, repeatable compliance audits.
* **CPU Latency Tolerance & Transient Retries:** Multi-clause inference on CPU can take 180–240 seconds. The client sets a 300-second timeout and incorporates automatic single-retry logic upon socket or OS timeouts to survive background CPU load spikes.
* **3-Stage Resilient JSON Parser (`_parse_llm_response`):** Smaller 8B models frequently wrap JSON in conversational text or markdown fences. The parser handles this via a multi-tier fallback:
  1. *Stage 1:* Regex extraction of markdown code blocks (````json ... ````).
  2. *Stage 2:* Direct `json.loads()` on the sanitized string.
  3. *Stage 3:* Unanchored regex bracket matching (`\{.*\}`) to extract embedded JSON objects if surrounded by conversational preamble.
  4. *Stage 4 (Fallback):* If all parsing fails, it safely constructs an `LLMResult` with `label="NotMentioned"` and preserves the raw output in the reasoning field for debugging, preventing pipeline crashes.

---

### 2.6. Subsystem 6: Dataset Management & Schema Validation
**Primary File:** [`edgelegal/backend/app/data_setup.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/data_setup.py)

#### Algorithmic & Design Rationale:
* **Automated Provenance:** Downloads the official Stanford NLP ContractNLI dataset distribution directly from Stanford's servers and extracts it into `backend/data/contractnli/`.
* **Zero-Dependency Execution:** Written entirely with the Python standard library (`urllib.request`, `zipfile`, `json`).
* **Integrity & Split Verification:** Validates that the downloaded splits match published ground-truth sizes:
  * `train.json`: Exactly 423 contracts.
  * `dev.json`: Exactly 61 contracts.
  * `test.json`: Exactly 123 contracts.
  * Hypotheses: Exactly 17 standardized NDA rules across all splits.

---

### 2.7. Subsystem 7: Retrieval Accuracy Verification (Zero-LLM Benchmark)
**Primary File:** [`edgelegal/backend/app/retrieval_accuracy_check.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/retrieval_accuracy_check.py)

#### Algorithmic & Design Rationale:
* **Scientific Motivation:** In RAG systems, if an LLM outputs an incorrect label, it is often impossible to tell whether the LLM failed at reasoning or whether the retriever failed to find the right clause.
* **Retrieval-Only Evaluation:** This benchmark maps the gold character spans (`doc["spans"]`) from all 123 test contracts in `test.json` to parsed `Clause` objects, runs embedding retrieval and adaptive gap filtering, and verifies whether the gold clause survived the filter—**with zero LLM calls**.
* **Three-Way Outcome Categorization:**
  * `INCLUDED`: At least one gold-evidence clause survived gap filtering (Retrieval Success).
  * `MISSING`: Gold clauses were identified in the document, but the vector search/filter failed to retrieve them (True Retrieval Failure).
  * `UNMATCHED`: The parser failed to encapsulate the exact gold span into a discrete clause (Parsing Boundary Error).

---

### 2.8. Subsystem 8: End-to-End Evaluation Suite (Configuration A)
**Primary File:** [`edgelegal/backend/app/test_pipeline.py`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/backend/app/test_pipeline.py)

#### Algorithmic & Design Rationale:
A 960-line test and diagnostic harness divided into four sequential evaluation phases:
* **Phase 1 (Clause Quality Audit):** Ingests 6 diverse contracts from the training set, segments them, and flags anomalies (clauses $<20$ characters or $>2000$ characters).
* **Phase 2 (Single-Document Smoke Test):** Indexes the UNHCR NDA (`doc_id=34`), runs all 17 hypotheses through ChromaDB and Ollama, and prints a per-hypothesis accuracy score against ground-truth labels.
* **Phase 3 (Multi-Document Held-Out Test Evaluation):** Evaluates 6 test contracts against all 17 hypotheses, calculating overall accuracy and computing an error-type breakdown:
  * *Missed Detections:* Predicted `NotMentioned` when gold was `Entailment` or `Contradiction`.
  * *False Positives:* Predicted `Entailment`/`Contradiction` when gold was `NotMentioned`.
  * *Label Confusion:* Swapped `Entailment` and `Contradiction`.
* **Phase 4 (Root-Cause Diagnostic Deep-Dive):** Isolates the worst-performing contract (e.g., `doc_id=408`, which scored 29.4%) and prints full un-truncated diagnostic traces for every mismatch (exact hypothesis, all retrieved clauses, LLM reasoning, and gold labels).

---

## 3. Explicit Documentation Coverage Matrix

This section explicitly maps every implemented file to its corresponding sections in the master design documents:
* **Master Guide:** [`EdgeLegal_Project_Guide.md`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/EdgeLegal_Project_Guide.md)
* **Technical Architecture:** [`edgelegal/docs/technical_architecture.md`](file:///c:/Users/katta/OneDrive/Desktop/major%20project/EdgeLegal_CodeBase/edgelegal/docs/technical_architecture.md)

---

### 3.1. Detailed Coverage Mapping Table

| Implemented File | Document Reference | Document Section Covered | Architectural Role & Implementation Scope |
|---|---|---|---|
| **`data_setup.py`** | `Project Guide`<br>`Tech Arch` | Section 5.2 (Step 1)<br>Section 6 | **Data Setup & Split Verification:** Automates the ingestion of ContractNLI's 607 contracts into train/val/test splits. |
| **`clause_parser.py`** | `Project Guide`<br>`Tech Arch` | Section 4 & 5.1<br>Section 3 (S1) & 4.1 | **Structure-Aware Clause Parser:** Converts raw contract text into segmented, heading-anchored `Clause` objects. |
| **`embedder.py`** | `Project Guide`<br>`Tech Arch` | Section 4 & 5.1<br>Section 3 (S2) & 4.2 | **Dense Retrieval Layer:** Implements 384-d vector embeddings using `BAAI/bge-small-en`. |
| **`chroma_client.py`** | `Project Guide`<br>`Tech Arch` | Section 4 & 5.1<br>Section 4.2 | **Vectorstore & Adaptive Gap Filter:** ChromaDB collection management and dynamic 15% distance cutoff filtering. |
| **`prompts.py`** | `Project Guide`<br>`Tech Arch` | Section 5.1 & 5.2 (Step 8)<br>Section 4.5 | **Prompt Engineering:** Strict multi-clause JSON prompts with built-in hooks for triage pre-labels. |
| **`ollama_client.py`** | `Project Guide`<br>`Tech Arch` | Section 4 & 5.1<br>Section 4.5 | **Local LLM Engine:** Robust HTTP client for local Ollama inference with greedy decoding and timeout recovery. |
| **`retrieval_accuracy_check.py`** | `Project Guide`<br>`Tech Arch` | Section 6.2 & 8<br>Section 4.2 & 6.1 | **Retrieval Evaluation:** Evaluates retrieval precision against gold spans across 123 test documents without LLM costs. |
| **`test_pipeline.py`** | `Project Guide`<br>`Tech Arch` | Section 6.1 (Config A)<br>Section 6.2 (Config A) | **Baseline Benchmark (Config A):** End-to-end evaluation harness for the un-routed full LLM control group. |

---

### 3.2. Quantitative Roadmap Coverage Analysis

```
Total Project Documentation Scope:
═══════════════════════════════════════════════════════════════════════════════════════════════
[████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] ~40% Complete
═══════════════════════════════════════════════════════════════════════════════════════════════
  ▲                                   ▲
  │                                   │
  ├── 100% of Configuration A         └── 0% of Configuration B & C (Pending: Triage & Agent)
  ├── 100% of Parsing & Embeddings
  └── 100% of ChromaDB & Retrieval
```

#### What is 100% Complete according to Docs:
1. **The Control Group (Configuration A):** Section 6.1 of the Project Guide requires evaluating a pure RAG pipeline where every clause is sent directly to the local LLM. This is completely built, tested, and benchmarked.
2. **Document Ingestion & Retrieval Pipeline:** Sections 4.1 and 4.2 of `technical_architecture.md` (PyMuPDF blocks, clause segmentation, BGE-small embeddings, ChromaDB, Adaptive Gap Filter) are fully implemented.
3. **Local LLM Interface:** Section 4.5 of `technical_architecture.md` (Ollama integration, JSON structured output protocol) is fully implemented.

#### What Remains to be Built:
1. **Tier 1 Triage Classifier (`app/triage_model/`):** Section 4.3 of `technical_architecture.md` & Step 2 of `Project Guide` (Fine-tuning DeBERTa-v3 on ContractNLI, temperature scaling, ECE calibration).
2. **LangGraph Orchestrator (`app/agent/`):** Section 4.4 of `technical_architecture.md` & Step 7 of `Project Guide` (State graph enforcing routing decision rule $\tau_{\text{frozen}}$).
3. **Configurations B & C Evaluation:** Section 6.1 of `Project Guide` (Running test benchmarks on Pretrained vs. Fine-Tuned triage routing and calculating McNemar significance tests).
4. **FastAPI Service & Frontend (`app/main.py` & `frontend/`):** Step 9 of `Project Guide` (Interactive dashboard and PDF bounding box viewer).
