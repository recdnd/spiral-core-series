# Spiral Minimal Simulation v0.2 (Non-narrative, Non-persona)  <200 lines
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple
import hashlib, json, random, time

def _hash(obj: dict) -> str:
    b = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:16]

def _ts() -> int:
    return int(time.time() * 1000)

@dataclass(frozen=True)
class Event:
    id: str
    parent_ids: List[str]
    ts: int
    payload: str
    meta: Dict[str, str] = field(default_factory=dict)

class History:
    def __init__(self) -> None:
        self.events: List[Event] = []
        self.by_id: Dict[str, Event] = {}

    def append(self, parent_ids: List[str], payload: str, meta: Optional[Dict[str,str]]=None) -> Event:
        meta = meta or {}
        raw = {"parent_ids": parent_ids, "ts": _ts(), "payload": payload, "meta": meta}
        eid = _hash(raw)
        ev = Event(id=eid, parent_ids=list(parent_ids), ts=raw["ts"], payload=payload, meta=meta)
        self.events.append(ev); self.by_id[eid] = ev
        return ev

class View:
    def __init__(self, name: str, predicate: Callable[[Event, History], bool]) -> None:
        self.name, self.predicate = name, predicate

    def visible(self, h: History) -> List[Event]:
        return [e for e in h.events if self.predicate(e, h)]

def chain_depth(e: Event, h: History, seen: Set[str]) -> int:
    if e.id in seen: return 999
    seen.add(e.id)
    if not e.parent_ids: return 1
    ds = []
    for pid in e.parent_ids:
        pe = h.by_id.get(pid)
        ds.append(999 if pe is None else 1 + chain_depth(pe, h, seen.copy()))
    return max(ds) if ds else 1

def trace_score(e: Event, h: History, alpha: float=0.55) -> float:
    # continuous score: missing parents / deep chains reduce score smoothly
    miss = sum(1 for pid in e.parent_ids if pid not in h.by_id)
    d = chain_depth(e, h, set())
    # score in (0,1], penalize missing parents strongly
    base = pow(2.71828, -alpha * max(0, d-1))
    return base * (0.15 ** miss)

def parse_kv(payload: str) -> Dict[str,str]:
    # minimal: accept "k=v; a=b" anywhere in payload
    out: Dict[str,str] = {}
    parts = [p.strip() for p in payload.split(";")]
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v: out[k] = v
    return out

class NoiseEngine:
    def __init__(self, seed: int=11, n_thr: int=30, d_thr: int=9, score_thr: float=0.06,
                 win: int=16, conflict_thr: int=4) -> None:
        random.seed(seed)
        self.n_thr, self.d_thr, self.score_thr = n_thr, d_thr, score_thr
        self.win, self.conflict_thr = win, conflict_thr

    def conflict_score(self, h: History) -> int:
        # in recent window, if a key has >1 distinct values -> +1 conflict per extra value
        recent = h.events[-self.win:]
        kvs: Dict[str, Set[str]] = {}
        for e in recent:
            if e.meta.get("kind") != "input": continue
            for k, v in parse_kv(e.payload).items():
                kvs.setdefault(k, set()).add(v)
        return sum(max(0, len(vals)-1) for vals in kvs.values())

    def should_noise(self, h: History) -> Tuple[bool, str]:
        if len(h.events) >= self.n_thr: return True, "count"
        if h.events:
            d = max(chain_depth(e, h, set()) for e in h.events[-min(24, len(h.events)):])
            if d >= self.d_thr: return True, "depth"
            smin = min(trace_score(e, h) for e in h.events[-min(24, len(h.events)):])
            if smin <= self.score_thr: return True, "trace_score"
        c = self.conflict_score(h)
        if c >= self.conflict_thr: return True, f"conflict({c})"
        return False, ""

    def emit_noise(self, h: History, reason: str) -> Event:
        k = random.randint(2, min(6, max(2, len(h.events))))
        parents = random.sample([e.id for e in h.events], k=k)
        mix = "|".join(h.by_id[p].payload for p in parents if p in h.by_id)
        lossy = hashlib.sha256((reason + "::" + mix).encode("utf-8")).hexdigest()[:24]
        payload = f"NOISE:{lossy}:{reason}:{mix[:18]}…"
        return h.append(parents, payload, meta={"kind":"noise","reason":reason})

def accept(h: History, payload: str, parents: Optional[List[str]]=None) -> Event:
    parents = parents or ([h.events[-1].id] if h.events else [])
    return h.append(parents, payload, meta={"kind":"input"})

def frontier_set(h: History, last_inputs: int=3, max_anc_depth: int=4) -> Set[str]:
    # causal frontier: last N input events + ancestors up to L depth
    inputs = [e for e in reversed(h.events) if e.meta.get("kind") == "input"][:last_inputs]
    keep: Set[str] = set()
    def walk(eid: str, depth: int) -> None:
        if depth > max_anc_depth or eid in keep: return
        keep.add(eid)
        e = h.by_id.get(eid)
        if not e: return
        for pid in e.parent_ids: walk(pid, depth+1)
    for e in inputs: walk(e.id, 0)
    return keep

def demo() -> None:
    h = History()
    noise = NoiseEngine(seed=13, n_thr=28, d_thr=9, score_thr=0.05, win=14, conflict_thr=3)

    view_last = View("LAST_10", lambda e, H: e in H.events[-10:])
    # show traceable-ish non-noise (score threshold)
    view_trace = View("TRACE_SCORE>0.10", lambda e, H: e.meta.get("kind")!="noise" and trace_score(e,H) > 0.10)

    # Generate inputs with occasional conflicts: topic=x/y flips inside window
    topics = ["x","y","z"]
    for i in range(20):
        t = random.choice(topics if i % 5 else ["x","y"])  # periodic conflict injection
        payload = f"evt{i}:{random.randint(10**6,10**7-1)}; topic={t}"
        accept(h, payload)
        ok, reason = noise.should_noise(h)
        if ok:
            for _ in range(random.randint(1, 2)):
                noise.emit_noise(h, reason)

    accept(h, "repair: summarize; topic=x")  # repair is also an input, can add conflict
    ok, reason = noise.should_noise(h)
    if ok: noise.emit_noise(h, reason)

    # Frontier view is computed set-based (depends on recent inputs)
    keep = frontier_set(h, last_inputs=3, max_anc_depth=4)
    view_frontier = View("FRONTIER", lambda e, H: e.id in keep)

    print(f"\nHistory size: {len(h.events)} (append-only)")
    for vw in [view_last, view_frontier, view_trace]:
        print(f"\n== View: {vw.name} ==")
        for e in vw.visible(h):
            sc = trace_score(e, h)
            kind = e.meta.get("kind")
            reason = e.meta.get("reason","")
            print(e.ts, e.id, kind, f"score={sc:.3f}", f"p={len(e.parent_ids)}", (reason and f"[{reason}]"), "|", e.payload)

    print("\nInvariant: no deletions, no edits. Only new events.\n")

if __name__ == "__main__":
    demo()
