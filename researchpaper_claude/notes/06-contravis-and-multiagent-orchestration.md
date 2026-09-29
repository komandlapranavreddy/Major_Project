# Two more contradiction/contract-review papers, both worth knowing about

## ContraVis
**Author/year:** Unspecified authors (cs.HC), ~September 2026.
**Idea:** Models a legal contract as a typed paragraph graph (explicit cross-references +
semantic relationships) that both conditions an LLM's reasoning AND drives an interactive
visualization for a human lawyer reviewing flagged contradictions. Found that
graph-conditioned LLM reasoning catches more injected contradictions than standalone LLM
analysis as contracts get longer.
- arXiv: https://arxiv.org/abs/2609.27014

**What you need from it:** Not a competitor — it's a human-in-the-loop visualization/HCI
tool, not a detection method (no classifier+LLM routing, no calibration, no benchmark-
style evaluation). Cite it only if you build the cross-reference retrieval agent feature
later (its typed-paragraph-graph idea is directly relevant to that).

## Multi-Agent Orchestration of Local LLMs for Contract Review under Resource Constraints
**Author/year:** Yang An, Zhicheng Wu, Z. Yang, Shaolei Zhou, Ya-Qin Yin, Xueyong Wang,
Pinle Qin (2025). Proceedings of the 2025 5th International Conference on Big Data,
Artificial Intelligence and Risk Management (ICBAR 2025), Dongguan, China.
- DOI: https://doi.org/10.1145/3800227.3800266

**Could not get the idea — the publisher deliberately withheld even the abstract.**
I checked both ACM's own page (403) and the Semantic Scholar API (which explicitly
returned: "the following paper fields have been elided by the publisher: abstract").
So this isn't a fetch failure I can work around — ACM has not made this abstract public
through any channel I can reach. All I have is title + authors + venue + DOI.

**What you need from it:** The title alone is the closest match to EdgeLegal's exact
premise found anywhere in this search — "local LLMs," "resource constraints," "contract
review," "multi-agent," all four at once. Because I can't tell you what's actually inside
it, this is the one paper on this list you or your advisor should personally track down
(institutional library / ACM DL subscription / interlibrary loan) before finalizing
related work — I'd treat it as unresolved risk, not a confirmed non-issue.

Side note: ICBAR is a broad-scope, moderately-selective ACM conference series — a useful
data point that this kind of work (local-LLM-constrained legal contract systems) gets
published at exactly the tier of Scopus-indexed venue you're likely aiming for.
