# spiral_core v0.31-a-only (Non-narrative, Non-persona) <200 lines
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
    miss = sum(1 for pid in e.parent_ids if pid not in h.by_id)
    d = chain_depth(e, h, set())
    base = pow(2.71828, -alpha * max(0, d-1))
    return base * (0.15 ** miss)

def parse_kv(payload: str) -> Dict[str,str]:
    out: Dict[str,str] = {}
    for p in [x.strip() for x in payload.split(";")]:
        if "=" in p:
            k, v = p.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v: out[k] = v
    return out

class NoiseEngineAOnly:
    # A-only conflict: same key has multiple distinct values in sliding window
    def __init__(self, seed: int=17, win: int=14, conflict_thr: int=2,
                 d_thr: int=14, n_thr: int=90) -> None:
        random.seed(seed)
        self.win, self.conflict_thr = win, conflict_thr
        self.d_thr, self.n_thr = d_thr, n_thr

    def conflict_score(self, h: History) -> int:
        recent = h.events[-self.win:]
        kvs: Dict[str, Set[str]] = {}
        for e in recent:
            if e.meta.get("kind") != "input": continue
            for k, v in parse_kv(e.payload).items():
                kvs.setdefault(k, set()).add(v)
        return sum(max(0, len(vals)-1) for vals in kvs.values())

    def should_noise(self, h: History) -> Tuple[bool, str]:
        # Priority: conflict -> depth -> count   (trace_score is OBSERVATION ONLY)
        c = self.conflict_score(h)
        if c >= self.conflict_thr: return True, f"conflict({c})"
        if h.events:
            d = max(chain_depth(e, h, set()) for e in h.events[-min(24, len(h.events)):])
            if d >= self.d_thr: return True, "depth"
        if len(h.events) >= self.n_thr: return True, "count"
        return False, ""

    def emit_noise(self, h: History, reason: str) -> Event:
        # noise parents only from INPUT events => avoids noise breeding
        inputs = [e for e in h.events if e.meta.get("kind") == "input"]
        if len(inputs) < 2:
            parents = [h.events[-1].id] if h.events else []
        else:
            k = random.randint(2, min(6, len(inputs)))
            parents = [e.id for e in random.sample(inputs, k=k)]
        mix = "|".join(h.by_id[p].payload for p in parents if p in h.by_id)
        lossy = hashlib.sha256((reason + "::" + mix).encode("utf-8")).hexdigest()[:24]
        payload = f"NOISE:{lossy}:{reason}:{mix[:18]}…"
        return h.append(parents, payload, meta={"kind":"noise","reason":reason})

def accept(h: History, payload: str, parents: Optional[List[str]]=None) -> Event:
    parents = parents or ([h.events[-1].id] if h.events else [])
    return h.append(parents, payload, meta={"kind":"input"})

def frontier_select(h: History, last_inputs: int=3, anc_depth: int=4, topk: int=20) -> List[Event]:
    # Build frontier inputs: last N inputs + their input-ancestors up to depth
    inputs = [e for e in reversed(h.events) if e.meta.get("kind") == "input"][:last_inputs]
    keep_in: Set[str] = set()

    def walk_in(eid: str, depth: int) -> None:
        if depth > anc_depth or eid in keep_in: return
        e = h.by_id.get(eid)
        if not e: return
        if e.meta.get("kind") == "input":
            keep_in.add(eid)
        for pid in e.parent_ids:
            walk_in(pid, depth+1)

    for e in inputs: walk_in(e.id, 0)

    # Local contamination: noises that directly reference any kept input
    keep_ids: Set[str] = set(keep_in)
    for e in h.events:
        if e.meta.get("kind") != "noise": continue
        if any(pid in keep_in for pid in e.parent_ids):
            keep_ids.add(e.id)

    # Rank by trace_score (workset prioritizes more "legible" items)
    evs = [h.by_id[i] for i in keep_ids if i in h.by_id]
    evs.sort(key=lambda e: trace_score(e, h), reverse=True)
    return evs[:topk]

def demo() -> None:
    h = History()
    noise = NoiseEngineAOnly(seed=19, win=14, conflict_thr=2, d_thr=14, n_thr=90)

    topics = ["x","y","z"]
    for i in range(24):
        t = random.choice(["x","y"]) if i % 4 in (0,1) else random.choice(topics)
        accept(h, f"evt{i}:{random.randint(10**6,10**7-1)}; topic={t}")
        ok, reason = noise.should_noise(h)
        if ok:
            noise.emit_noise(h, reason)

    accept(h, "repair: summarize; topic=x")
    ok, reason = noise.should_noise(h)
    if ok: noise.emit_noise(h, reason)

    view_last = View("LAST_12", lambda e,H: e in H.events[-12:])
    view_trace = View("TRACE_SCORE>1e-1 (non-noise)", lambda e,H: e.meta.get("kind")!="noise" and trace_score(e,H) > 1e-1)
    frontier = frontier_select(h, last_inputs=3, anc_depth=4, topk=20)

    print(f"\nHistory size: {len(h.events)} (append-only)")

    def show(title: str, events: List[Event]) -> None:
        print(f"\n== View: {title} ==")
        for e in events:
            sc = trace_score(e, h)
            kind = e.meta.get("kind")
            reason = e.meta.get("reason","")
            tag = f"[{reason}]" if reason else ""
            print(e.ts, e.id, kind, f"score={sc:.3e}", f"p={len(e.parent_ids)}", tag, "|", e.payload)

    show(view_last.name, view_last.visible(h))
    show("FRONTIER top20 (ranked by trace_score)", frontier)
    show(view_trace.name, view_trace.visible(h))

    print("\nInvariant: no deletions, no edits. Only new events.\n")

if __name__ == "__main__":
    demo()
