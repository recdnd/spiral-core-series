## A-Mode Frontier (RECENT_A) — Clean Spec

**Context**:
- Concept / intuition: [`ABSTRACT.md`](ABSTRACT.md)
- Engineering narrative: [`WHITEPAPER.md`](WHITEPAPER.md)

---

### 1) Data model

**Event universe.**
Let the event universe be:

```text
E = { e0, e1, e2, ... }
```

**Events.**
Each event is an immutable record:

```text
e = (id_e, t_e, k_e, P_e, s_e)
```

Where:

- `id_e`: event id (hash)
- `t_e`: timestamp (monotonic, ms)
- `k_e`: kind ∈ {input, observe, noise, repair}
- `P_e`: parent id list/set (causal parents)
- `s_e`: trace score (ranking only; does not affect membership)

**Append-only history.**
History is a strictly append-only sequence:

```text
H = ⟨ e0 ≺ e1 ≺ ... ≺ en ⟩
```

Invariant:

```text
i < j => t(e_i) <= t(e_j)
```

No deletions. No edits. Only appends.

---

### 2) Causal DAG

Define a directed graph `G = (E, ->)` where:

```text
p -> e   iff   id(p) ∈ P_e
```

Assumption: G is a DAG (parents always point to same-or-earlier events).

---

### 3) Trace score (ranking only)

```text
trace_score: E -> R+
```

Constraints:
- does **not** affect event generation
- does **not** affect causal edges
- used **only** for sorting in views

---

### 4) Seed (time seed)

For a chosen `K >= 1`, define the last K events:

```text
Seed_K(H) = { e_{n-K+1}, ..., e_n }
```

---

## 5) Closure operator (Trace-Closure)

We build the minimal "explanation-closed" set around `Seed_K`. There are two expansions:

### 5.1 Upward closure: Ancestry (causal backtrace)

For any set `S ⊆ E`, include ancestors (within depth cutoff D):

If `e ∈ S` and `p -> e`, then `p` must be included. Recursively apply until:

- no new parents, or
- depth exceeds D

(Depth cutoff D is your `anc_depth`.)

### 5.2 Downward closure: Reactive explanation (system responses)

Include reactive "explainers" that are _bound_ to nodes already included:

If `p ∈ S`, and there exists `e` such that `p -> e` and

```text
k_e ∈ {observe, noise, repair}
```

then include `e`.

(Engineering reading: if an observe/noise/repair points to something we keep, keep that response too, so the graph remains interpretable.)

### 5.3 Fixed point (minimal closed set)

Let `C(·)` denote "apply 5.1 and 5.2 once". Define:

```text
C*(S) = min { T | S ⊆ T ∧ C(T) = T }
```

---

## 6) A-Mode Frontier (RECENT_A / "recent causal frontier")

### 6.1 Set definition

Seed (time seed):

```text
Seed_K(H) = { e_{n-K+1}, ..., e_n }
```

RECENT_A is the minimal causally + reactively closed subgraph generated from Seed_K(H):

```text
RECENT_A(K) = C*( Seed_K(H) )
```

This is: **the minimal causally+reactively closed subgraph generated from the last K events**.

### 6.2 Output ordering (view only)

Return as a ranked view:

```text
sort_desc(RECENT_A, (s_e, t_e))
```

---

## 7) Formal guarantees

### P1. Causal completeness (ancestry closed)

For every `e ∈ RECENT_A`, all its parents (within depth cutoff) are also in `RECENT_A`.

### P2. Recent explainability (connected to seed)

For every `e ∈ RECENT_A`, there exists `r ∈ Seed_K` such that there is a causal path `e ⇝ r` or `r ⇝ e`.

### P3. Score orthogonality

Membership in `RECENT_A` is determined by causal/semantic closure, **not** by maximizing `s_e`.

---

## 8) One-line paper sentence (English)

> Let RECENT_A(K) be the minimal causally closed subgraph induced by the last K events, augmented with reactive system responses (observe/noise/repair) that directly reference nodes in the subgraph.

---

# Non-equivalence: RECENT_A vs Sliding Window

### Definitions

**Sliding window:**

```text
SW_K(H) = { e_{n-K+1}, ..., e_n }
```

**RECENT_A:**

```text
RECENT_A(K) = C*( SW_K(H) )
```

### Claim

For any fixed `K >= 1`, there exists a history `H` such that

```text
RECENT_A(K) ≠ SW_K(H)
```

### Minimal intuition

Sliding window is **purely time-based** (only truncates).  
RECENT_A is **causal-based** (can pull older ancestors back in, and pull in bound reactive events). Therefore they cannot be equivalent in general.

---

## Engineering counterexample (matches your log semantics)

Take `K = 2`. Construct these events (timestamps increasing):

1. AAA: input
2. BBB: input
3. OOO: observe with **parents bound to the conflict input pair** (your v0.46 rule)
   - `P_O = {A, B}`
4. RRR: repair referencing the observe
   - `P_R = {O}`
5. NNN: noise referencing the observe (or conflict pair)
   - `P_N = {O, ...}`

Now:

- **Sliding window:**
  - `SW_2 = {R, N}`
- **RECENT_A** starts from `{R, N}`, pulls in parents:
  - `R -> O` ⇒ `O ∈ RECENT_A`
  - `N -> O` ⇒ `O ∈ RECENT_A`
  - `O -> {A, B}` ⇒ `A, B ∈ RECENT_A`

So:

```text
RECENT_A(K) ⊇ {R, N, O, A, B} ≠ {R, N} = SW_2
```

**Key reason**: the observe/noise binding introduces edges that jump outside the time window; closure must pull those ancestors back.
