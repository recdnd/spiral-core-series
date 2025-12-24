# spiral_core v0.36-a-only (Non-narrative, Non-persona) <200 lines
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple
import hashlib, json, random, time
from collections import Counter

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

def conflict_heat(h: History, win: int) -> Tuple[int, List[Tuple[str,int,str,int]]]:
    recent_inputs = [e for e in h.events[-win:] if e.meta.get("kind") == "input"]
    key_vals: Dict[str, Set[str]] = {}
    key_counts: Dict[str, Counter] = {}
    for e in recent_inputs:
        kv = parse_kv(e.payload)
        for k, v in kv.items():
            key_vals.setdefault(k, set()).add(v)
            key_counts.setdefault(k, Counter())[v] += 1
    rows: List[Tuple[str,int,str,int]] = []
    total = 0
    for k, vals in key_vals.items():
        heat = max(0, len(vals)-1)
        total += heat
        dom_v, dom_c = ("", 0)
        if k in key_counts and key_counts[k]:
            dom_v, dom_c = key_counts[k].most_common(1)[0]
        rows.append((k, heat, dom_v, dom_c))
    rows.sort(key=lambda x: (-x[1], x[0]))
    return total, rows

class ObserveGate:
    # Write observe only when STRUCTURAL signature changes + cooldown (by input steps).
    def __init__(self, cooldown_inputs: int=2) -> None:
        self.last_sig: Optional[str] = None
        self.cooldown = max(0, cooldown_inputs)
        self.inputs_since_emit = 10**9  # large

    def on_input(self) -> None:
        self.inputs_since_emit += 1

    def _struct_sig(self, win: int, total: int, struct_top: str) -> str:
        return f"conflict_heat|win={win}|total={total}|struct_top={struct_top}"

    def maybe_observe(self, h: History, win: int, topn: int=3) -> Optional[Event]:
        total, rows = conflict_heat(h, win)
        if total <= 0:
            self.last_sig = None
            return None
        # payload top keeps count; signature top drops count
        payload_parts, sig_parts = [], []
        for (k, heat, dom_v, dom_c) in rows[:topn]:
            if heat <= 0: break
            payload_parts.append(f"{k}:{heat}:{dom_v}:{dom_c}")  # keep count
            sig_parts.append(f"{k}:{heat}:{dom_v}")            # no count in signature
        top_payload = ",".join(payload_parts)
        top_struct = ",".join(sig_parts)
        sig = self._struct_sig(win, total, top_struct)

        if self.inputs_since_emit < self.cooldown:
            return None
        if sig == self.last_sig:
            return None

        self.last_sig = sig
        self.inputs_since_emit = 0
        payload = f"observe=conflict_heat; win={win}; total_heat={total}; top={top_payload}"
        parents = [h.events[-1].id] if h.events else []
        return h.append(parents, payload, meta={"kind":"observe","observe":"conflict_heat"})

class NoiseEngineAOnly:
    def __init__(self, seed: int=33, win: int=14, conflict_thr: int=2,
                 d_thr: int=14, n_thr: int=120, backref_prob: float=0.15) -> None:
        random.seed(seed)
        self.win, self.conflict_thr = win, conflict_thr
        self.d_thr, self.n_thr = d_thr, n_thr
        self.backref_prob = backref_prob

    def conflict_score(self, h: History) -> int:
        total, _ = conflict_heat(h, self.win)
        return total

    def conflicting_inputs(self, h: History) -> List[Event]:
        recent_inputs = [e for e in h.events[-self.win:] if e.meta.get("kind") == "input"]
        total, rows = conflict_heat(h, self.win)
        if total <= 0: return []
        conflict_keys = {k for (k, heat, _, _) in rows if heat >= 1}
        out: List[Event] = []
        for e in recent_inputs:
            kv = parse_kv(e.payload)
            if any(k in conflict_keys for k in kv.keys()):
                out.append(e)
        return out

    def should_noise(self, h: History) -> Tuple[bool, str]:
        c = self.conflict_score(h)
        if c >= self.conflict_thr: return True, f"conflict({c})"
        if c == 0 and h.events:
            d = max(chain_depth(e, h, set()) for e in h.events[-min(24, len(h.events)):])
            if d >= self.d_thr: return True, "depth"
        if len(h.events) >= self.n_thr: return True, "count"
        return False, ""

    def emit_noise(self, h: History, reason: str) -> Event:
        all_inputs = [e for e in h.events if e.meta.get("kind") == "input"]
        pool = self.conflicting_inputs(h) if reason.startswith("conflict") else []
        if len(pool) < 2: pool = all_inputs
        if len(pool) < 2:
            parents = [h.events[-1].id] if h.events else []
        else:
            k = random.randint(2, min(6, len(pool)))
            parents = [e.id for e in random.sample(pool, k=k)]
        mix = "|".join(h.by_id[p].payload for p in parents if p in h.by_id)
        lossy = hashlib.sha256((reason + "::" + mix).encode("utf-8")).hexdigest()[:24]
        payload = f"NOISE:{lossy}:{reason}:{mix[:18]}…"
        return h.append(parents, payload, meta={"kind":"noise","reason":reason})

    def choose_input_parents(self, h: History) -> List[str]:
        if not h.events: return []
        if random.random() > self.backref_prob:
            return [h.events[-1].id]
        inputs = [e for e in h.events if e.meta.get("kind") == "input"]
        if len(inputs) < 3: return [h.events[-1].id]
        older = inputs[:-1]
        pick = random.choice(older[max(0, len(older)-12):])
        return [pick.id]

def accept(h: History, eng: NoiseEngineAOnly, payload: str) -> Event:
    parents = eng.choose_input_parents(h)
    return h.append(parents, payload, meta={"kind":"input"})

def frontier_select(h: History, last_inputs: int=3, anc_depth: int=4, topk: int=20) -> List[Event]:
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

    keep_ids: Set[str] = set(keep_in)
    for e in h.events:
        k = e.meta.get("kind")
        if k in ("noise","observe") and any(pid in keep_in for pid in e.parent_ids):
            keep_ids.add(e.id)

    evs = [h.by_id[i] for i in keep_ids if i in h.by_id]
    evs.sort(key=lambda e: trace_score(e, h), reverse=True)
    return evs[:topk]

def demo() -> None:
    h = History()
    eng = NoiseEngineAOnly(seed=35, win=14, conflict_thr=2, d_thr=14, n_thr=120, backref_prob=0.15)
    obs = ObserveGate(cooldown_inputs=2)

    topics = ["x","y","z"]
    for i in range(28):
        t = random.choice(["x","y"]) if i % 4 in (0,1) else random.choice(topics)
        accept(h, eng, f"evt{i}:{random.randint(10**6,10**7-1)}; topic={t}")
        obs.on_input()
        obs.maybe_observe(h, eng.win, topn=3)
        ok, reason = eng.should_noise(h)
        if ok: eng.emit_noise(h, reason)

    accept(h, eng, "repair: summarize; topic=x")
    obs.on_input()
    obs.maybe_observe(h, eng.win, topn=3)
    ok, reason = eng.should_noise(h)
    if ok: eng.emit_noise(h, reason)

    frontier = frontier_select(h, last_inputs=3, anc_depth=4, topk=20)
    view_last = View("LAST_12", lambda e,H: e in H.events[-12:])
    view_observe = View("OBSERVE_ONLY", lambda e,H: e.meta.get("kind") == "observe")

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
    show(view_observe.name, view_observe.visible(h)[-10:])

    print("\nInvariant: no deletions, no edits. Only new events.\n")

if __name__ == "__main__":
    demo()
