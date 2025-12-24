# Spiral Minimal Simulation (Non-narrative, Non-persona)
# Requirements: Python 3.10+
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set
import hashlib, json, random, time

def _hash(obj: dict) -> str:
    b = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:16]

def _mono_ts() -> int:
    # monotonic-ish ordering for demo; replace with real monotonic clock if needed
    return int(time.time() * 1000)

@dataclass(frozen=True)
class Event:
    id: str
    parent_ids: List[str]
    ts: int
    payload: str              # opaque blob (system does not interpret)
    meta: Dict[str, str] = field(default_factory=dict)

class History:
    def __init__(self) -> None:
        self.events: List[Event] = []
        self.by_id: Dict[str, Event] = {}

    def append(self, parent_ids: List[str], payload: str, meta: Optional[Dict[str,str]]=None) -> Event:
        meta = meta or {}
        raw = {"parent_ids": parent_ids, "ts": _mono_ts(), "payload": payload, "meta": meta}
        eid = _hash(raw)
        ev = Event(id=eid, parent_ids=list(parent_ids), ts=raw["ts"], payload=payload, meta=meta)
        self.events.append(ev)
        self.by_id[eid] = ev
        return ev

class View:
    # A view is ONLY a filter. It cannot edit history.
    def __init__(self, name: str, predicate: Callable[[Event, History], bool]) -> None:
        self.name = name
        self.predicate = predicate

    def visible(self, h: History) -> List[Event]:
        return [e for e in h.events if self.predicate(e, h)]

def traceable(e: Event, h: History) -> bool:
    # "traceable" means all parents exist and chain depth is bounded (demo rule)
    for pid in e.parent_ids:
        if pid not in h.by_id: 
            return False
    # bounded depth check: if any chain exceeds 6, mark as hard-to-trace
    def depth(x: Event, seen: Set[str]) -> int:
        if x.id in seen: 
            return 999
        seen.add(x.id)
        if not x.parent_ids:
            return 1
        return 1 + max(depth(h.by_id[p], seen.copy()) for p in x.parent_ids if p in h.by_id)
    return depth(e, set()) <= 6

class NoiseEngine:
    def __init__(self, N: int=50, D: int=8, P: float=0.25, seed: int=7) -> None:
        self.N, self.D, self.P = N, D, P
        random.seed(seed)

    def _chain_depth(self, e: Event, h: History, seen: Set[str]) -> int:
        if e.id in seen: 
            return 999
        seen.add(e.id)
        if not e.parent_ids:
            return 1
        depths = []
        for pid in e.parent_ids:
            pe = h.by_id.get(pid)
            if pe is None:
                depths.append(999)
            else:
                depths.append(1 + self._chain_depth(pe, h, seen.copy()))
        return max(depths) if depths else 1

    def should_noise(self, h: History) -> bool:
        if len(h.events) >= self.N:
            return True
        if h.events:
            max_d = max(self._chain_depth(e, h, set()) for e in h.events[-min(len(h.events), 20):])
            if max_d >= self.D:
                return True
        # "opaque ratio" heuristic: payloads that look random-ish (no spaces) count as opaque
        if h.events:
            opaque = sum(1 for e in h.events[-min(len(h.events), 40):] if (" " not in e.payload and len(e.payload) > 12))
            if opaque / min(len(h.events), 40) >= self.P:
                return True
        return False

    def emit_noise(self, h: History) -> Event:
        # pick multiple parents; lossy transform: hash-mix their payloads
        k = random.randint(2, min(6, max(2, len(h.events))))
        parents = random.sample([e.id for e in h.events], k=k)
        mix = "|".join(h.by_id[p].payload for p in parents if p in h.by_id)
        # lossy: keep only partial hash + truncated fragments
        lossy = hashlib.sha256(mix.encode("utf-8")).hexdigest()[:24]
        payload = f"NOISE:{lossy}:{mix[:18]}…"
        return h.append(parent_ids=parents, payload=payload, meta={"kind":"noise"})

def accept(h: History, payload: str, parents: Optional[List[str]]=None) -> Event:
    parents = parents or ([h.events[-1].id] if h.events else [])
    return h.append(parent_ids=parents, payload=payload, meta={"kind":"input"})

def demo() -> None:
    h = History()
    noise = NoiseEngine(N=30, D=7, P=0.30, seed=11)

    # Views: last 8 events, and traceable-only
    view_last = View("LAST_8", lambda e, H: e in H.events[-8:])
    view_trace = View("TRACEABLE_ONLY", lambda e, H: traceable(e, H) and e.meta.get("kind") != "noise")

    # Step 1: write inputs
    for i in range(18):
        accept(h, payload=f"evt{i}:{random.randint(10**6, 10**7-1)}")

        # Step 2: auto-noise when thresholds hit
        if noise.should_noise(h):
            for _ in range(random.randint(1, 3)):
                noise.emit_noise(h)

    # Step 3: "repair attempt" (only adds new events, cannot undo)
    accept(h, payload="repair: attempt to summarize recent noise")
    if noise.should_noise(h):
        noise.emit_noise(h)

    # Print
    print(f"\nHistory size: {len(h.events)} (append-only)")
    print("\n== View: LAST_8 ==")
    for e in view_last.visible(h):
        print(e.ts, e.id, e.meta.get("kind"), "parents", len(e.parent_ids), "|", e.payload)

    print("\n== View: TRACEABLE_ONLY ==")
    for e in view_trace.visible(h)[-12:]:
        print(e.ts, e.id, "parents", len(e.parent_ids), "|", e.payload)

    # Invariant check
    print("\nInvariant: no deletions, no edits. Only new events.")
    print("Try 'undo' mentally: impossible; only more events can be added.\n")

if __name__ == "__main__":
    demo()
