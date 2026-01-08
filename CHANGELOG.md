# spiral_core_series. Summary Notes for v0.39 -> v0.46.

This document summarizes what changed across the spiral_core_series prototypes from v0.39 through v0.46. The core arc is: frontier visibility -> conflict observation -> conflict noise -> frontier modes -> parent strong binding + invariants.

All prototypes keep the same foundational invariant. Append only. No deletions. No edits. Only new events.

---

## 0. Goal.

Build a minimal event history core that can do three things.

- Record a stream of events in an append only history.
- Derive structural signals from the stream. Example. conflict_heat.
- Provide a visibility view. frontier. that surfaces the most relevant events without losing causal meaning.

---

## 1. Event model. History model.

### 1.1 Event fields.

- ts. int. millisecond timestamp. monotonic non decreasing via Clock.tick.
- id. str. random hash id.
- parent_ids. List[str]. causal links.
- meta. Dict[str, Any]. typed tags.
- payload. str. human readable line.

### 1.2 Kinds.

- input. primary events. meta.kind == "input". meta.topic is one of x y z.
- observe. derived events. meta.kind == "observe". meta.observe == "conflict_heat".
- noise. derived events. meta.kind == "noise". meta.noise_kind == "conflict(2)".

### 1.3 Append only invariant.

History.add appends the event and indexes it by id. No mutation. No deletion.

---

## 2. conflict_heat. From implicit to explicit.

### 2.1 conflict_heat metric.

Given the last WIN input events.

- topics = [topic of each input].
- heat = number of topic changes between adjacent topics.
- dom = most frequent topic in that window.
- domc = count of dom in the window.

Return value evolved.

- early versions. return heat and top tuple.
- v0.45+. return heat and top tuple and pair_ids.

### 2.2 pair_ids. The conflict pair.

In v0.45+. conflict_heat also returns pair_ids. This is the key conceptual upgrade.

- pair_ids binds the current conflict to a concrete pair of input events.
- default strategy. pick the last two input ids whose topic == dom within the window.
- fallback. if fewer than 2 exist. backfill from most recent inputs in the window with de duplication.
- order. old -> new.

This makes conflict explainable. It is no longer only a scalar heat. It becomes a traceable relation.

---

## 3. observe generation. Stability rules.

observe events represent the current conflict_heat state. They are appended only when the signature changes.

### 3.1 Signature gating.

- sig = f"win={WIN};total_heat={heat};top=topic:{heat}:{dom}".
- domc is excluded from sig to avoid noisy churn.
- if sig != last_obs_sig. append a new observe.

### 3.2 Parents binding. v0.46 semantics.

observe.parents is not a chain pointer. It is a semantic bind.

- observe.parents = pair_ids.
- payload includes. observe=conflict_heat; win=...; total_heat=...; top=topic:heat:dom:domc.

This means every observe can be traced back to the exact input pair it is about.

---

## 4. noise generation. Controlled escalation.

noise events represent a conflict escalation event. They are appended only when conflict exceeds a threshold and cooldown allows it.

### 4.1 Trigger.

- if heat >= 2.
- and now - last_conflict_ts >= COOLDOWN_MS.

### 4.2 Parents binding. v0.46 semantics.

noise.parents is strongly bound to the same conflict pair.

- noise.parents = pair_ids.
- payload includes. NOISE:<id>:conflict(2):top=...:<label>; topic=<t>.

This ensures noise is never orphaned. It is always attributable to a concrete conflict pair.

---

## 5. frontier. From single view to modes.

frontier is a view function that selects a subset of events that should be visible right now. It is not a mutation. It is a projection.

### 5.1 trace_score ranking.

Events are ranked by a time decay score.

- trace_score = exp(-age / half_life_ms).
- age is measured against the last event timestamp.

### 5.2 Roots.

Roots are chosen as.

- last N input events. last_inputs.
- last M observe events. last_observes.
- roots are ordered. observes then inputs. oldest -> newest.

### 5.3 Closure.

closure(seed_ids) returns an ancestor set within anc_depth using parent_ids edges.

### 5.4 global mode.

global mode aims to show a causal skeleton and its immediate neighbors.

- build skeleton = closure(root_ids).
- keep = skeleton.
- add any event that has a parent in skeleton. one hop forward.
- rank by trace_score. return topk.

### 5.5 recent_k mode.

recent mode aims to keep a local time window and preserve causal connectivity.

- tail_ids = ids of last recent_k events.
- seed = tail_ids union root_ids.
- keep = closure(seed).
- add one hop forward children for any kept id.
- rank by trace_score. return topk.

This avoids a common bug. recent window truncation hiding linked observe or noise. The forward one hop pass keeps linked derived events visible.

---

## 6. Printing. parents formatting.

To debug causality. the print layer was upgraded to show parents.

### 6.1 Minimal format.

When p > 0.

- print. parents=[id8,id8,...].
- id8 means first 8 hex characters.

Example.

- observe score=0.998 p=2 parents=[7fe7d9f2,7d75addb] | observe=conflict_heat; ...
- noise score=1.000 p=2 parents=[7fe7d9f2,7d75addb] [conflict(2)] | NOISE:...:conflict(2):...

This makes causality legible in the console output.

---

## 7. Strong binding rule. parents = conflict pair.

This is the main addition in v0.46.

### 7.1 Rule.

Define a conflict pair as the pair_ids computed by conflict_heat for the current window. Then.

- observe(conflict_heat).parents must equal that pair.
- noise(conflict(2)).parents must equal that pair.
- noise should not invent new parents.
- observe should not point to a rolling chain id.

### 7.2 Practical benefit.

- You can always trace an observe or noise back to the exact two input events that generated it.
- frontier does not need special casing to keep derived events meaningful.
- later. you can compute conflict clusters by union finding on these pairs.

---

## 8. Invariants. Automatic checks.

An invariant checker was added and treated as a first class contract.

### 8.1 Basic structural checks.

- observe(conflict_heat) must bind to input events only.
- noise(conflict(2)) must bind to input events only.

### 8.2 Strong binding checks.

If you also keep an observe id reference in noise or choose to encode it. enforce.

- noise.parents == observe.parents for the latest relevant observe.

In v0.46 the simplest invariant is already strong enough.

- For every noise(conflict(2)). parents must be a valid conflict pair of two input events.
- For every observe(conflict_heat)). parents must be a valid conflict pair of two input events.

If you later re introduce the pattern noise parents = [input, observe]. then add the cross check noise.input == observe.parent and preserve the same input pair concept via explicit encoding.

---

## 9. Version arc. What changed per step.

This is a condensed changelog.

- v0.39 a only. single frontier. observe and noise exist but parents are not semantically printed and not strongly bound.
- v0.40 frontier fix. frontier ranking and selection cleaned up so frontier is stable.
- v0.41 frontier modes. split into frontier_recent and frontier_global outputs. visibility became a mode system.
- v0.42 frontier modes fix. ensure both outputs are correct. keep observe only list. fix edge inclusion logic.
- v0.43 recent fix. repair recent mode so it does not drop linked derived events.
- v0.44 recent_k. introduce recent_k parameterization for recent mode. avoid hard coded tail length.
- v0.45 recent_k fix. patch the recent_k logic and stabilize selection.
- v0.46. add parents printing. change conflict_heat to return pair_ids. bind observe.parents and noise.parents to pair_ids. add invariant checker for parents = conflict pair.

---

## 10. Next steps. Optional.

These are not required for this completed development round. But they are natural continuations.

- Make conflict pair selection policy pluggable. dominant last two. entropy weighted. alternating edges. etc.
- Add a tiny schema version string into meta for forward compatibility.
- Add a deterministic replay mode by seeding random and using a deterministic clock.
- Add a compact export. jsonl. with id parent_ids meta payload. for Spiral Engine ingestion.

---

## 11. Done criteria for this round.

This round is complete when.

- parents are printed in all views.
- observe and noise are strongly bound to conflict pairs.
- invariants run at the end and pass.
- frontier_recent_k and frontier_global both remain stable and interpretable.

As of v0.46. these criteria are satisfied.
