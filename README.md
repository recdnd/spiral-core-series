# spiral-core-series

A minimal, append-only event history core for Spiral. Focused on traceable causality, conflict signals, and frontier visibility.

> **Status**: Prototype series (v0.02 → v0.46).  
> **Latest**: v0.46 — Parents printing + strong binding + invariants.

---

## What This Is

`spiral-core-series` is a compact set of Python prototypes that explore a single problem:

**How do we keep "what matters" visible in an event stream, without losing causal meaning?**

Core capabilities:

- Append-only event log.
- Derived signals (e.g. `conflict_heat`).
- View projection (`frontier`) that surfaces relevant nodes while preserving causality.
- Strong binding rule: derived events must be attributable to a concrete input pair ("conflict pair").

---

## Quickstart

**Requirements:** Python 3.10+

```bash
git clone https://github.com/recdnd/spiral-core-series.git
cd spiral-core-series
python3 versions/spiral_core_v046_frontier-recent-k-fix.py
Expected output (shape):

History size: ... (append-only)

== View: LAST_12 ==

== View: FRONTIER_RECENT_K_FIXED ... ==

Invariant: no deletions, no edits. Only new events.
```

---

## Cite / Attribution

If you build on **RECENT_A (trace-closure frontier)** or the **conflict-pair binding** rule, attribution is appreciated:

- Concept + prototype: **recdnd/spiral-core-series**
- Spec: `docs/A-Mode Frontier(RECENT-A) — Clean Spec.md`

---

## Why It Exists

Event streams accumulate fast. Naive sliding windows drop causal context. Simple ranking loses explainability.

This series builds a **trace-closure** approach: instead of truncating by time or score, we maintain minimal causally closed subgraphs that remain interpretable.

---

## Core Invariants

**Append-only. No edits. No deletions.**

- Events are only appended to history.
- No mutation, no deletion, no retroactive changes.

**Causal edges are explicit via parent_ids.**

- Every event declares its causal parents explicitly.
- The history forms a DAG (directed acyclic graph).

**Derived events binding.**

- Every `observe(conflict_heat)` and `noise(conflict(2))` must be attributable to a concrete **conflict pair** (two input events).
- This is enforced by runtime invariants (see v0.46).

---

## RECENT_A Overview (Trace-Closure)

**RECENT_A is not a sliding window.**

Instead of a plain sliding window, RECENT_A is defined as:

> **The minimal causally closed subgraph generated from the last K events, augmented with reactive system responses.**

Components:

- **Seed**: Last K events (time-based).
- **Upward closure**: Include ancestors (bounded by depth).
- **Downward closure**: Include reactive explainers (observe/noise/repair) that reference kept nodes.
- **Ranking is orthogonal**: `trace_score` sorts the view, it does not decide membership.

**Formal spec**: See [`docs/A-Mode-Frontier-RECENT-A-Clean-Spec.md`](docs/A-Mode-Frontier-RECENT-A-Clean-Spec.md).

---

## Repo Structure

```
spiral-core-series/
├── README.md                    # This file
├── .gitignore
├── spiral_core.py              # Minimal core (optional reference)
├── docs/
│   ├── A-Mode-Frontier-RECENT-A-Clean-Spec.md
│   └── spiral_core_series_SUMMARY_v039_to_v046.md
└── versions/
    ├── v0.02/
    │   └── spiral_core_v02.py
    ├── v0.03/
    │   └── spiral_core_v03_a-only.py
    ...
    └── v0.046/
        ├── README.md
        └── spiral_core_v046_frontier-recent-k-fix.py  # Latest reference
```

**Version naming**: Each version lives in `versions/vX.XX/` with its prototype file(s). Append-only series: no deletions, no merges.

---

## Quickstart

**Requirements:** Python 3.10+ (and `make`)

```bash
git clone https://github.com/recdnd/spiral-core-series.git
cd spiral-core-series
make run
```

**Expected output**:

- `LAST_12` — newest events in append-only history.
- `FRONTIER_RECENT_K_FIXED` — RECENT_A-like view (recent seed + closure + one-hop forward).
- `FRONTIER_GLOBAL` — global skeleton view from latest roots.
- `OBSERVE_ONLY` — observe events sorted by trace score.
- `Invariant: ...` — must pass (strong binding checks).

Parents are printed as `parents=[deadbeef,feedcafe]` (first 8 chars) for causality visibility.

---

## Event Model (Minimal)

Each event has:

- `ts`: monotonic ms timestamp.
- `id`: short hash id.
- `parent_ids`: causal edges (explicit).
- `meta`: typed tags (`kind`, `topic`, etc.).
- `payload`: a human-readable line.

**Kinds used in the series**:

- `input`: primary events with `meta.topic`.
- `observe`: derived state, currently `observe=conflict_heat`.
- `noise`: derived escalation, currently `noise_kind=conflict(2)`.
- `repair`: implemented as a special `input` payload in current prototypes.

---

## Output Glossary

**Views**:

- `LAST_N`: Simple tail view (last N events by timestamp).
- `FRONTIER_RECENT_K_FIXED`: RECENT_A trace-closure view.
- `FRONTIER_GLOBAL`: Global skeleton view (roots + closure + one-hop forward).

**Event types**:

- `input`: Primary events with topics (x, y, z).
- `observe`: Derived conflict heat state (`observe=conflict_heat`).
- `noise`: Conflict escalation (`noise_kind=conflict(2)`).
- `repair`: Repair attempts (currently as `input` payload).

**Fields**:

- `parents=[id8,id8]`: Causal parent ids (truncated to 8 hex chars for readability).
- `score=0.998`: Trace score (time decay, view-only ranking).
- `p=2`: Parent count.

**Conflict pair**: Two input event ids that generated a conflict. Strongly bound to `observe` and `noise` events in v0.46+.

---

## Strong Binding Rule

**Definition**: Every derived event (`observe(conflict_heat)` or `noise(conflict(2))`) must have `parent_ids` equal to the **conflict pair** (two input events) that generated it.

**Why**: This ensures every derived event is traceable to concrete inputs. No floating explanations. Frontier views remain interpretable.

**Enforcement**: Runtime invariants check this at the end of each run (v0.46+). See [`versions/v0.046/README.md`](versions/v0.046/README.md) for details.

---

## Roadmap

- **v0.46** (current): Parents printing + strong binding + invariants. ✅
- **v0.47+** (future): Conflict pair selection policy pluggability, deterministic replay, compact export (JSONL).

For detailed changelog across v0.39 → v0.46, see [`docs/spiral_core_series_SUMMARY_v039_to_v046.md`](docs/spiral_core_series_SUMMARY_v039_to_v046.md).

---

## Documentation

- **Technical Whitepaper**: [`docs/TECHNICAL_WHITEPAPER.md`](docs/TECHNICAL_WHITEPAPER.md) — Complete technical overview (v0.02 → v0.46), design principles, and strong binding rule.
- **Abstract Definition**: [`docs/A-Mode-Frontier-Abstract-Definition.md`](docs/A-Mode-Frontier-Abstract-Definition.md) — Intuitive definition and conceptual framework of RECENT_A.
- **Formal spec**: [`docs/A-Mode-Frontier-RECENT-A-Clean-Spec.md`](docs/A-Mode-Frontier-RECENT-A-Clean-Spec.md) — RECENT_A trace-closure mathematical definition.
- **Changelog**: [`docs/spiral_core_series_SUMMARY_v039_to_v046.md`](docs/spiral_core_series_SUMMARY_v039_to_v046.md) — Version arc notes (v0.39 → v0.46).
- **v0.46 README**: [`versions/v0.046/README.md`](versions/v0.046/README.md) — Latest version details.

---

## License

Apache-2.0

---

## Credits

Built by Rec. Part of the Spiral / SpiralVM research-to-tool chain.
