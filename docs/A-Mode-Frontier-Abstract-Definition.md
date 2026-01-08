# A-Mode Frontier (Trace-Closure) — Abstract Definition

**Spiral Core v0.46**

This document provides an abstract, intuitive definition of the A-Mode Frontier. For the formal mathematical specification, see [`A-Mode-Frontier-RECENT-A-Clean-Spec.md`](A-Mode-Frontier-RECENT-A-Clean-Spec.md).

---

## 1. Basic Universe (Universe)

### 1.1 Event (Event)

An event is an **immutable record**:

```
e = {
  id: Hash,
  ts: Timestamp,
  kind ∈ {input, observe, noise, repair},
  parents ⊆ EventID,
  payload: Any,
  trace_score ∈ ℝ⁺
}
```

### 1.2 History (History)

```
H = [e₀, e₁, e₂, ...]
```

Satisfies the unique invariant:

**Append-Only Invariant**

∀t, history can only be appended. No deletion, modification, or reordering.

---

## 2. Causal Structure (Causal Structure)

### 2.1 Parent-Child Relationship

If `p ∈ e.parents`, then:

```
p → e  (p is the causal source of e)
```

Define a directed acyclic graph (DAG):

```
G = (H, →)
```

---

## 3. Trace Score (Traceability Weight)

### 3.1 Definition

`trace_score(e)` represents:

> The relative importance of event `e` for "understanding what is happening in the system" within the current history.

**Constraints**:

- Does not affect history order
- Does not participate in event generation or deletion
- Used only for view sorting

---

## 4. Abstract Definition of Frontier

### 4.1 Global Frontier

```
FRONTIER_GLOBAL = TopN(H, key = trace_score)
```

**Semantics**:

The set of "most important" events in the full history (does not guarantee continuity or causal completeness).

---

## 5. Frontier Recent — A Mode (Core Innovation)

### 5.1 Intuitive Definition (One Sentence)

> A small segment of recent history that has occurred recently and can be completely explained causally.

### 5.2 Seed Set (Seed)

```
Seed_K = LastK(H)
```

That is:

- The K most recent events in time
- No filtering, no score consideration

### 5.3 Trace-Closure (Causal Closure)

Define a closure operator `C(S)`:

**Upward Closure (Causes)**

If:

```
e ∈ S  and  p ∈ e.parents
```

Then:

```
p ∈ C(S)
```

Recursively, until:

- No new parent nodes, or
- Maximum parent depth D is reached

**Downward Closure (Explanatory Reactions)**

If:

```
p ∈ S  and  e.kind ∈ {observe, noise, repair}
and  p ∈ e.parents
```

Then:

```
e ∈ C(S)
```

**Constraint**:

❌ Sub-nodes of ordinary `input` events are not automatically included

This prevents temporal explosion.

### 5.4 Formal Definition of RECENT_A

```
RECENT_A = sort_desc(
  C(Seed_K),
  key = (trace_score, ts)
)
```

---

## 6. Semantic Guarantees of A Mode (Guarantees)

### G1. Explainability

Every event in RECENT_A:

- Either occurred recently, or
- Is a necessary causal prerequisite for explaining recent events, or
- Is a system reaction to these events

### G2. Local Completeness

RECENT_A is a **causally closed subgraph**, not a temporal slice.

### G3. Decoupled from Importance

"Recent" ≠ "Important"

`trace_score` only sorts; it does not determine membership.

---

## 7. Explicit Anti-Definitions (Pitfalls Before v0.44)

RECENT_A is **not**:

❌ Top-K by `trace_score`

❌ Temporal truncation of Global Frontier

❌ Pure time window

❌ Collection of observe/noise without causal sources

---

## 8. Why A is a "New Model"

From an abstract perspective, what we do is:

> Transform a **temporal view** into a **causal-explanatory view**.

This is the intersection of three system paradigms:

| Domain | Traditional | Spiral v0.46 |
|--------|------------|--------------|
| Logging | Time-based rolling | Causal closure |
| Agent Memory | Top-K relevance | Recent explainable slice |
| AI Debug | State snapshot | Event trace subgraph |

---

## 9. Core Sentence for Whitepaper (Direct Use)

> Spiral defines "recent context" not as a temporal window, but as the minimal causally closed subgraph necessary to explain the system's latest behavior.

---

## 10. Relationship to Formal Spec

This abstract definition complements the formal mathematical specification in [`A-Mode-Frontier-RECENT-A-Clean-Spec.md`](A-Mode-Frontier-RECENT-A-Clean-Spec.md):

- **This document**: Intuitive understanding, conceptual framework, design rationale.
- **Formal spec**: Mathematical precision, proofs, implementation constraints.

Together, they provide both the "why" and the "how" of RECENT_A.

---

**See also**:
- [`TECHNICAL_WHITEPAPER.md`](TECHNICAL_WHITEPAPER.md) — Complete technical overview.
- [`spiral_core_series_SUMMARY_v039_to_v046.md`](spiral_core_series_SUMMARY_v039_to_v046.md) — Implementation evolution.

