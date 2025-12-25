# spiral-core-series — Research Note

This repo publishes a runnable prototype + formal spec for **RECENT_A**:
a causally-closed frontier view over an append-only event history.

Primary references:
- Spec: `A-Mode Frontier(RECENT-A) — Clean Spec.md`
- Changelog notes: `spiral_core_series_SUMMARY_v039_to_v046.md`

Claim (informal):
RECENT_A is not a sliding window; it is a minimal causal closure generated from the last K events, augmented with reactive responses.
