# spiral_core v0.40-frontier-fix (Non-narrative, A-only) <200 lines
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import hashlib, json, random, time
from collections import Counter

def _ts() -> int: return int(time.time() * 1000)
def _hash(obj: dict) -> str:
    b = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:16]

@dataclass(frozen=True)
class Event:
    id: str
    parent_ids: List[str]
    ts: int
    payload: str
    meta: Dict[str, str]

class History:
    def __init__(self) -> None:
        self.events: List[Event] = []
        self.by_id: Dict[str, Event] = {}
    def append(self, parent_ids: List[str], payload: str, meta: Dict[str,str]) -> Event:
        raw = {"parent_ids": parent_ids, "ts": _ts(), "payload": payload, "meta": meta}
        eid = _hash(raw)
        ev = Event(eid, list(parent_ids), raw["ts"], payload, meta)
        self.events.append(ev); self.by_id[eid] = ev
        return ev

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
    recent = [e for e in h.events[-win:] if e.meta.get("kind") == "input"]
    key_vals: Dict[str, Set[str]] = {}
    key_counts: Dict[str, Counter] = {}
    for e in recent:
        for k, v in parse_kv(e.payload).items():
            key_vals.setdefault(k, set()).add(v)
            key_counts.setdefault(k, Counter())[v] += 1
    rows: List[Tuple[str,int,str,int]] = []
    total = 0
    for k, vals in key_vals.items():
        heat = max(0, len(vals)-1); total += heat
        dom_v, dom_c = ("", 0)
        if k in key_counts and key_counts[k]:
            dom_v, dom_c = key_counts[k].most_common(1)[0]
        rows.append((k, heat, dom_v, dom_c))
    rows.sort(key=lambda x: (-x[1], x[0]))
    return total, rows

def conflict_signature(total: int, rows: List[Tuple[str,int,str,int]], topn: int=3) -> Tuple[str,str,List[Tuple[str,int,str,int]]]:
    payload_parts, sig_parts, kept = [], [], []
    for (k, heat, dom_v, dom_c) in rows[:topn]:
        if heat <= 0: break
        kept.append((k, heat, dom_v, dom_c))
        payload_parts.append(f"{k}:{heat}:{dom_v}:{dom_c}")   # payload keeps dom_count
        sig_parts.append(f"{k}:{heat}:{dom_v}")              # signature omits dom_count
    top_payload = ",".join(payload_parts)
    sig = f"total={total}|top={','.join(sig_parts)}"
    return top_payload, sig, kept

class ObserveGate:
    def __init__(self, cooldown_inputs: int=2, win: int=14) -> None:
        self.cool = max(0, cooldown_inputs)
        self.win = win
        self.last_sig: Optional[str] = None
        self.since = 10**9
    def on_input(self) -> None: self.since += 1

    def _parents(self, h: History, top_struct: List[Tuple[str,int,str,int]], min_p: int=2, max_p: int=6) -> List[str]:
        recent = [e for e in h.events[-self.win:] if e.meta.get("kind") == "input"]
        want: List[str] = []
        for e in reversed(recent):
            kv = parse_kv(e.payload)
            hit = any(heat > 0 and kv.get(k) == dom_v for (k, heat, dom_v, _) in top_struct)
            if hit:
                want.append(e.id)
                if len(want) >= max_p: break
        if len(want) >= min_p: return list(reversed(want))
        for e in reversed(recent):
            if e.id not in want:
                want.append(e.id)
                if len(want) >= min_p: break
        return list(reversed(want)) if want else ([h.events[-1].id] if h.events else [])

    def maybe(self, h: History, topn: int=3) -> Optional[Event]:
        total, rows = conflict_heat(h, self.win)
        if total <= 0:
            self.last_sig = None
            return None
        top_payload, sig, top_struct = conflict_signature(total, rows, topn=topn)
        full_sig = f"conflict_heat|win={self.win}|{sig}"
        if self.since < self.cool: return None
        if full_sig == self.last_sig: return None
        self.last_sig = full_sig; self.since = 0
        parents = self._parents(h, top_struct, min_p=2, max_p=6)
        payload = f"observe=conflict_heat; win={self.win}; total_heat={total}; top={top_payload}"
        return h.append(parents, payload, {"kind":"observe","observe":"conflict_heat"})

class NoiseAOnly:
    def __init__(self, seed: int=40, win: int=14, conflict_thr: int=2, cooldown_inputs: int=2, backref_prob: float=0.15) -> None:
        random.seed(seed)
        self.win, self.thr = win, conflict_thr
        self.cool = max(0, cooldown_inputs)
        self.backref_prob = backref_prob
        self.since = 10**9
        self.last_sig: Optional[str] = None
        self.last_observe_parents: Optional[List[str]] = None
    def on_input(self) -> None: self.since += 1
    def on_observe(self, obs: Event) -> None:
        if obs.meta.get("observe") == "conflict_heat":
            self.last_observe_parents = list(obs.parent_ids)

    def choose_input_parents(self, h: History) -> List[str]:
        if not h.events: return []
        if random.random() > self.backref_prob:
            return [h.events[-1].id]
        inputs = [e for e in h.events if e.meta.get("kind") == "input"]
        if len(inputs) < 3: return [h.events[-1].id]
        older = inputs[:-1]
        pick = random.choice(older[max(0, len(older)-12):])
        return [pick.id]

    def should_conflict_noise(self, h: History) -> Tuple[bool, str, str]:
        total, rows = conflict_heat(h, self.win)
        top_payload, sig, _ = conflict_signature(total, rows, topn=3)
        if total < self.thr:
            self.last_sig = None
            return False, "", ""
        if self.since < self.cool: return False, "", ""
        if sig == self.last_sig: return False, "", ""
        self.last_sig = sig
        return True, f"conflict({total})", top_payload

    def emit_conflict_noise(self, h: History, reason: str, top_payload: str) -> Event:
        parents = list(self.last_observe_parents) if self.last_observe_parents else []
        if len(parents) < 2:
            parents = [h.events[-1].id] if h.events else []
        mix = "|".join(h.by_id[p].payload for p in parents if p in h.by_id)
        lossy = hashlib.sha256((reason + "::" + mix).encode("utf-8")).hexdigest()[:24]
        payload = f"NOISE:{lossy}:{reason}:top={top_payload}:{mix[:12]}…"
        self.since = 0
        return h.append(parents, payload, {"kind":"noise","reason":reason})

# roots 强制包含 “最近的 observe（最多 2 个）” + “最近的 input（最多 4 个）.
def frontier(h: History, last_inputs: int=4, last_observes: int=2, anc_depth: int=6, topk: int=20) -> List[Event]:
    # collect recent roots separately (so observe can't be starved by frequent inputs)
    inputs: List[Event] = []
    observes: List[Event] = []
    for e in reversed(h.events):
        k = e.meta.get("kind")
        if k == "input" and len(inputs) < last_inputs:
            inputs.append(e)
        elif k == "observe" and len(observes) < last_observes:
            observes.append(e)
        if len(inputs) >= last_inputs and len(observes) >= last_observes:
            break

    roots = list(reversed(observes)) + list(reversed(inputs))  # keep ordering stable-ish

    skeleton: Set[str] = set()
    def walk(eid: str, depth: int) -> None:
        if depth > anc_depth or eid in skeleton: return
        e = h.by_id.get(eid)
        if not e: return
        if e.meta.get("kind") in ("input", "observe"):
            skeleton.add(eid)
        for pid in e.parent_ids:
            walk(pid, depth+1)

    for r in roots:
        walk(r.id, 0)

    keep: Set[str] = set(skeleton)
    # attach all events that touch skeleton (noise included)
    for e in h.events:
        if any(pid in skeleton for pid in e.parent_ids):
            keep.add(e.id)

    evs = [h.by_id[i] for i in keep if i in h.by_id]
    evs.sort(key=lambda e: trace_score(e, h), reverse=True)
    return evs[:topk]


def demo() -> None:
    h = History()
    obs = ObserveGate(cooldown_inputs=2, win=14)
    eng = NoiseAOnly(seed=40, win=14, conflict_thr=2, cooldown_inputs=2, backref_prob=0.15)
    topics = ["x","y","z"]

    for i in range(26):
        t = random.choice(["x","y"]) if i % 4 in (0,1) else random.choice(topics)
        h.append(eng.choose_input_parents(h), f"evt{i}:{random.randint(10**6,10**7-1)}; topic={t}", {"kind":"input"})
        eng.on_input(); obs.on_input()
        o = obs.maybe(h, topn=3)
        if o: eng.on_observe(o)
        ok, reason, top_payload = eng.should_conflict_noise(h)
        if ok: eng.emit_conflict_noise(h, reason, top_payload)

    h.append(eng.choose_input_parents(h), "repair: summarize; topic=x", {"kind":"input"})
    eng.on_input(); obs.on_input()
    o = obs.maybe(h, topn=3)
    if o: eng.on_observe(o)
    ok, reason, top_payload = eng.should_conflict_noise(h)
    if ok: eng.emit_conflict_noise(h, reason, top_payload)

    def show(title: str, evs: List[Event]) -> None:
        print(f"\n== View: {title} ==")
        for e in evs:
            sc = trace_score(e, h)
            tag = f"[{e.meta.get('reason','')}]" if e.meta.get("reason") else ""
            print(e.ts, e.id, e.meta.get("kind"), f"score={sc:.3e}", f"p={len(e.parent_ids)}", tag, "|", e.payload)

    print(f"\nHistory size: {len(h.events)} (append-only)")
    show("LAST_12", h.events[-12:])
    show("FRONTIER top20 (ranked by trace_score)", frontier(h, last_inputs=4, last_observes=2, anc_depth=6, topk=20))
    show("OBSERVE_ONLY", [e for e in h.events if e.meta.get("kind") == "observe"][-10:])
    print("\nInvariant: no deletions, no edits. Only new events.\n")

if __name__ == "__main__":
    demo()
