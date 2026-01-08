# Spiral Core Series — Technical Whitepaper

**Version**: v0.46  
**Date**: 2024  
**Status**: Prototype Series (v0.02 → v0.46)

---

## Executive Summary

`spiral-core-series` is a minimal, append-only event history core that solves a fundamental problem in event stream processing: **how to maintain visibility of "what matters" without losing causal meaning**.

This whitepaper documents the complete evolution from v0.02 to v0.46, the core design principles, and the formal guarantees that make RECENT_A fundamentally different from naive sliding windows.

---

## 1. Problem Statement

Event streams accumulate rapidly. Traditional approaches face two critical limitations:

1. **Sliding windows** drop causal context when truncating by time.
2. **Score-based ranking** loses explainability when events are selected by importance alone.

**Core question**: How do we keep a compact, interpretable view of recent activity while preserving the causal relationships that make events meaningful?

---

## 2. Design Principles

### 2.1 Append-Only Invariant

**Rule**: Append-only. No edits. No deletions.

- Events are only appended to history.
- No mutation, no deletion, no retroactive changes.
- This ensures auditability and prevents causal inconsistencies.

### 2.2 Explicit Causal Edges

**Rule**: Causal edges are explicit via `parent_ids`.

- Every event declares its causal parents explicitly.
- The history forms a DAG (directed acyclic graph).
- This makes causality traceable and verifiable.

### 2.3 Strong Binding Rule

**Rule**: Every derived event must be attributable to a concrete **conflict pair** (two input events).

- `observe(conflict_heat)` must have `parent_ids` equal to the conflict pair.
- `noise(conflict(2))` must have `parent_ids` equal to the conflict pair.
- This ensures every derived event is traceable to concrete inputs. No floating explanations.

**Enforcement**: Runtime invariants check this at the end of each run (v0.46+).

---

## 3. Evolution: v0.02 → v0.46

### 3.1 Early Versions (v0.02 - v0.38)

**Focus**: Establish append-only log and basic event emission.

- v0.02: Initial prototype with basic event model.
- v0.03-v0.38: Iterative improvements to event structure, history management, and basic signal derivation.

**Key achievements**:
- Stable append-only history model.
- Basic event kinds: `input`, `observe`, `noise`, `repair`.
- Monotonic timestamp and hash-based IDs.

### 3.2 Frontier Visibility (v0.39 - v0.44)

**Focus**: Build frontier visibility and add modes.

- v0.39: Single frontier view introduced.
- v0.40: Frontier ranking and selection stabilized.
- v0.41: Split into `frontier_recent` and `frontier_global` modes.
- v0.42: Fixed edge inclusion logic for both modes.
- v0.43: Fixed recent mode to avoid dropping linked derived events.
- v0.44: Introduced `recent_k` parameterization.

**Key achievements**:
- Two-mode frontier system (recent vs global).
- Trace-closure algorithm for causal completeness.
- One-hop forward expansion to keep linked events visible.

### 3.3 Strong Binding (v0.45 - v0.46)

**Focus**: Explicit conflict attribution and invariant enforcement.

- v0.45: `conflict_heat` now returns `pair_ids` (conflict pair).
- v0.46: Parents printing + strong binding + invariant checks.

**Key achievements**:
- Every `observe` and `noise` is bound to a concrete conflict pair.
- Parents are printed in all views for causality visibility.
- Runtime invariants enforce the strong binding rule.

---

## 4. RECENT_A: Trace-Closure Frontier

### 4.1 Definition

**RECENT_A is not a sliding window.**

RECENT_A is defined as:

> **The minimal causally closed subgraph generated from the last K events, augmented with reactive system responses.**

### 4.2 Algorithm

1. **Seed**: Last K events (time-based).
2. **Upward closure**: Include ancestors (bounded by depth `anc_depth`).
3. **Downward closure**: Include reactive explainers (observe/noise/repair) that reference kept nodes.
4. **Ranking**: Sort by `trace_score` (orthogonal to membership).

### 4.3 Formal Properties

**P1. Causal completeness**: For every event in RECENT_A, all its parents (within depth cutoff) are also in RECENT_A.

**P2. Recent explainability**: Every event in RECENT_A is connected to the seed via causal paths.

**P3. Score orthogonality**: Membership is determined by causal/semantic closure, not by maximizing trace score.

### 4.4 Non-Equivalence with Sliding Window

**Theorem**: For any fixed K ≥ 1, there exists a history H such that RECENT_A(K) ≠ SW_K(H).

**Proof sketch**: Sliding window is purely time-based (only truncates). RECENT_A is causal-based (can pull older ancestors back in, and pull in bound reactive events). Therefore they cannot be equivalent in general.

**Engineering counterexample**: See [`A-Mode-Frontier-RECENT-A-Clean-Spec.md`](A-Mode-Frontier-RECENT-A-Clean-Spec.md) for a detailed example with K=2.

---

## 5. Strong Binding Rule: Detailed Specification

### 5.1 Conflict Pair Selection

When `conflict_heat(h, win)` is computed:

1. Extract the last `win` input events.
2. Compute `heat` (number of topic changes).
3. Identify `dom` (dominant topic).
4. **Select conflict pair**: Pick the last two input IDs whose topic equals `dom` within the window.
5. **Fallback**: If fewer than 2 exist, backfill from most recent inputs in the window (with deduplication).
6. **Order**: Old → new.

### 5.2 Binding Semantics

**For `observe(conflict_heat)`**:
- `observe.parent_ids = pair_ids`
- Payload includes: `observe=conflict_heat; win=...; total_heat=...; top=topic:heat:dom:domc`

**For `noise(conflict(2))`**:
- `noise.parent_ids = pair_ids`
- Payload includes: `NOISE:<id>:conflict(2):top=...:<label>; topic=<t>`

### 5.3 Invariant Checks

At the end of each run, the following are verified:

1. Every `observe(conflict_heat)` has exactly 2 parents, both of kind `input`.
2. Every `noise(conflict(2))` has exactly 2 parents, both of kind `input`.
3. These parents form a valid conflict pair (computed by `conflict_heat`).

If any check fails, an `AssertionError` is raised with a readable report.

### 5.4 Benefits

- **Traceability**: Every derived event can be traced back to exact input events.
- **Interpretability**: Frontier views remain meaningful without special casing.
- **Clusterability**: Conflict clusters can be computed via union-find on these pairs.

---

## 6. Event Model

### 6.1 Event Structure

Each event is a tuple:

```
Event = (id, ts, parent_ids, meta, payload)
```

Where:
- `id`: Short hash ID (16 hex chars).
- `ts`: Monotonic timestamp (milliseconds).
- `parent_ids`: List of parent event IDs (causal edges).
- `meta`: Typed tags (`kind`, `topic`, `observe`, `noise_kind`, etc.).
- `payload`: Human-readable line.

### 6.2 Event Kinds

- **`input`**: Primary events with `meta.topic` (x, y, z).
- **`observe`**: Derived state (`meta.observe == "conflict_heat"`).
- **`noise`**: Derived escalation (`meta.noise_kind == "conflict(2)"`).
- **`repair`**: Currently implemented as a special `input` payload.

### 6.3 History Model

History is a strictly append-only sequence:

```
H = ⟨e₀ ≺ e₁ ≺ ⋯ ≺ eₙ⟩
```

With invariant: `i < j ⇒ t_{e_i} ≤ t_{e_j}`. No deletions, no edits.

---

## 7. Frontier Views

### 7.1 Modes

**Global mode** (`frontier(mode="global")`):
- Build skeleton from roots (last N inputs + last M observes).
- Closure upward via parent edges (bounded by `anc_depth`).
- Add one-hop forward children of skeleton nodes.
- Rank by `trace_score`, return top K.

**Recent mode** (`frontier(mode="recent")`):
- Seed = `{last recent_k events} ∪ {root_ids}`.
- Closure upward via parent edges (bounded by `anc_depth`).
- Add one-hop forward children of kept nodes.
- Rank by `trace_score`, return top K.

### 7.2 Trace Score

Trace score is a time-decay function:

```
trace_score(e, h) = exp(-age / half_life_ms)
```

Where `age = h.events[-1].ts - e.ts`.

**Important**: Trace score is view-only. It never affects event generation or causal edges.

---

## 8. Implementation Notes

### 8.1 Parents Printing

In v0.46+, all views include parent IDs:

```
observe score=0.998 p=2 parents=[7fe7d9f2,7d75addb] | observe=conflict_heat; ...
noise   score=1.000 p=2 parents=[7fe7d9f2,7d75addb] [conflict(2)] | NOISE:...
```

- IDs are truncated to 8 hex chars for readability.
- This makes "why is this event here?" answerable by inspection.

### 8.2 Parameters

- `WIN` (default 14): Window length for `conflict_heat`.
- `recent_k` (default 10): How many tail events seed RECENT_A.
- `anc_depth` (default 6): Maximum ancestry depth in closure.
- `COOLDOWN_MS` (default 2): Throttle for emitting `noise(conflict(2))`.

---

## 9. Future Directions

### 9.1 Planned (v0.47+)

- Conflict pair selection policy pluggability (dominant last two, entropy weighted, alternating edges, etc.).
- Deterministic replay mode (seed random, deterministic clock).
- Compact export (JSONL) with `id`, `parent_ids`, `meta`, `payload` for Spiral Engine ingestion.

### 9.2 Optional Enhancements

- Schema version string in `meta` for forward compatibility.
- Additional derived event types beyond `observe` and `noise`.
- Conflict cluster analysis via union-find on conflict pairs.

---

## 10. References

- **Formal Spec**: [`A-Mode-Frontier-RECENT-A-Clean-Spec.md`](A-Mode-Frontier-RECENT-A-Clean-Spec.md) — Complete mathematical definition of RECENT_A.
- **Changelog**: [`spiral_core_series_SUMMARY_v039_to_v046.md`](spiral_core_series_SUMMARY_v039_to_v046.md) — Detailed version arc (v0.39 → v0.46).
- **Latest Version**: [`../versions/v0.046/README.md`](../versions/v0.046/README.md) — v0.46 implementation details.

---

## 11. Conclusion

The spiral-core-series demonstrates that **causal closure** is a fundamental primitive for event stream visibility. By maintaining minimal causally closed subgraphs and enforcing strong binding rules, we achieve:

- **Interpretability**: Every event is traceable to concrete inputs.
- **Completeness**: Causal context is preserved even in compact views.
- **Correctness**: Runtime invariants enforce semantic guarantees.

RECENT_A is not a sliding window. It is a **trace-closure** that makes recent activity meaningful by preserving causality.

---

**Built by Rec. Part of the Spiral / SpiralVM research-to-tool chain.**

