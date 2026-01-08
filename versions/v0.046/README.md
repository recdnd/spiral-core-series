# Spiral Core v0.46 — Frontier (RECENT_A) + Strong Binding

v0.46 is a “make it interpretable” release:

1) **Parents are printed** in views (`parents=[xxxxxxxx,yyyyyyyy]`)  
2) **Observe/noise are strongly bound** to a concrete **conflict input pair**  
3) A runtime **invariant suite** enforces the binding rules  
4) `frontier(mode="recent")` is fixed to keep the right closure slice (no accidental truncation)

---

## Run

```bash
python spiral_core_v046_frontier-recent-k-fix.py
```

Expected output sections:

- `LAST_12` — newest events in append-only history
- `FRONTIER_RECENT_K_FIXED` — RECENT_A-like view (seed K + trace-closure + one-hop forward)
- `FRONTIER_GLOBAL` — global skeleton view from latest roots
- `OBSERVE_ONLY` — observe events sorted by trace score
- `Invariant: ...` — must pass

---

## Data model (at a glance)

Each `Event`:

- `ts`: monotonic timestamp (ms)
- `id`: short hash id
- `parent_ids`: explicit causal edges
- `meta`: `{ kind: input|observe|noise, ... }`
- `payload`: printable line

Append-only contract: **no deletes, no edits. only new events.**

---

## What changed in v0.46

### 1) Parents printing (debug visibility)

Views now include a compact parent list:

```
... observe ... p=2 parents=[7fe7d9f2,7d75addb] | observe=conflict_heat; ...
... noise   ... p=2 parents=[7fe7d9f2,7d75addb] [conflict(2)] | NOISE:...
```

- The list is truncated to 8 chars per id for readability.
- This makes “why is this event here?” answerable by inspection.

### 2) Strong binding: “parents = conflict pair”

The core rule is:

> Every `observe(conflict_heat)` and `noise(conflict(2))` must be attributable to the same **two input events**.

Implementation detail:

- `conflict_heat(...)` returns:
  - `heat`: scalar
  - `top`: a tuple describing the dominant topic in the window
  - `pair_ids`: **two input ids** picked as the “conflict pair”

Then event emitters use:

- `mk_observe(..., parents=pair_ids, ...)`
- `mk_noise(..., parents=pair_ids, ...)`

This removes ambiguity where observe/noise used to reference “current input + latest observe” (which breaks traceability).

### 3) Invariant: conflict-pair binding is enforced

At the end of the run, we check:

- Observe events:
  - `observe(conflict_heat)` must have exactly **2** parents
  - both parents must be `input`

- Noise events:
  - `noise(conflict(2))` must have exactly **2** parents
  - both parents must be `input`

If any of those fail, the run throws an `AssertionError` with a readable report.

> If your next iteration introduces other derived types, add them here early.
> Invariants are your “append-only safety rails”.

### 4) Frontier RECENT_K fix (no missing edges)

The `frontier(mode="recent")` strategy:

1. Seed = `{ last K events } ∪ { root ids }`
2. Closure upward via parent edges (bounded by `anc_depth`)
3. Add one-hop forward children of kept nodes (so linked observe/noise stays visible)
4. Rank by `trace_score` (orthogonal to membership)

This yields a compact but causally coherent “recent explainability view”.

---

## Parameters worth tuning

- `WIN` (default 14): window length for `conflict_heat`
- `recent_k` (default 10): how many tail events seed RECENT_A
- `anc_depth` (default 6): maximum ancestry depth in closure
- `COOLDOWN_MS` (default 2): throttle for emitting `noise(conflict(2))`

---

## Notes

- `trace_score` is *view-only*. It never changes the history or parents.
- `repair` is still emitted as a special `input` payload; you can promote it to `kind="repair"` later if you want.
- The conflict-pair selection policy is intentionally simple in this version; making it pluggable is a natural v0.47+ task.

---

## Related docs (repo root)

- [`../../docs/SPEC_RECENT_A.md`](../../docs/SPEC_RECENT_A.md) — formal definition of RECENT_A / trace-closure
- [`../../CHANGELOG.md`](../../CHANGELOG.md) — patch history notes (v0.39 → v0.46)
