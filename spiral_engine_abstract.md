# One-liner (Purpose)

A minimal, append-only event history core that maintains visibility of "what matters" in event streams without losing causal meaning, via RECENT_A trace-closure frontier over event DAGs.

# Audience (Who it's for)

Researchers, system architects, and developers exploring causal event log architectures. Also serves as reference implementation and formal spec for Spiral's event history model.

# Scope (In / Out)

**In**: Append-only event log, causal DAG structure, RECENT_A trace-closure algorithm, conflict-pair binding rules, frontier view projections, runtime invariants.

**Out**: No production deployment, no persistence layer, no network protocols, no user interface. Pure algorithmic prototype series.

**Not included**: Database backends, API servers, client libraries, visualization tools.

# Status

prototype | v0.46 (latest) | Active development

Next: Conflict pair selection policy pluggability, deterministic replay, compact export (JSONL). All prototypes preserved as append-only series (v0.02 → v0.46).

# Entry Points

**URLs**:
- GitHub Pages: https://core.rec.ooo
- GitHub Repo: https://github.com/recdnd/spiral-core-series

**Key docs**:
- README.md (root)
- docs/ABSTRACT.md (concept/intuition)
- docs/SPEC_RECENT_A.md (formal spec)
- docs/WHITEPAPER.md (engineering narrative)
- CHANGELOG.md (version arc v0.39 → v0.46)

**Commands**:
- `make run` (runs latest prototype v0.46)
- `python versions/v0.046/spiral_core_v046_frontier-recent-k-fix.py` (direct execution)

# Core Concepts / Keywords

append-only, event history, causal DAG, trace-closure, RECENT_A, frontier view, conflict-pair binding, parent_ids, trace_score, observe, noise, repair, invariant, strong binding, minimal causally closed subgraph, sliding window alternative

# Interfaces

**None** (prototype series)

No API, CLI, or file formats exposed. Pure Python prototypes demonstrating algorithmic concepts. Output is console-printed event views and invariant checks.

# Relation to Spiral Universe

Research prototype and formal specification for Spiral's event history core. Defines RECENT_A trace-closure as the foundation for "recent context" in event streams. Serves as reference implementation and mathematical spec. Part of Spiral / SpiralVM research-to-tool chain. Published at core.rec.ooo as technical documentation.

