# spiral_core_v043_frontier-recent-fix.py  (<200 lines)
import time, random, hashlib, math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple

def now_ms() -> int: return int(time.time() * 1000)
def h16(s: str) -> str: return hashlib.sha1(s.encode()).hexdigest()[:16]
def rnd_id() -> str: return h16(str(random.random()) + str(now_ms()))
def fmt_score(x: float) -> str: return f"{x:.3e}" if x < 1e-2 else f"{x:.3f}"

class Clock:
    def __init__(self): self.t = now_ms()
    def tick(self, step: int = 1) -> int:
        cur = now_ms()
        self.t = max(self.t + step, cur)
        return self.t

@dataclass
class Event:
    ts: int
    id: str
    parent_ids: List[str]
    meta: Dict[str, Any] = field(default_factory=dict)
    payload: str = ""

@dataclass
class History:
    events: List[Event] = field(default_factory=list)
    by_id: Dict[str, Event] = field(default_factory=dict)
    def add(self, e: Event) -> None:
        self.events.append(e); self.by_id[e.id] = e

def trace_score(e: Event, h: History, half_life_ms: int = 450) -> float:
    if not h.events: return 0.0
    age = max(0, h.events[-1].ts - e.ts)
    return math.exp(-age / max(1, half_life_ms))

def last_id(h: History) -> Optional[str]:
    return h.events[-1].id if h.events else None

def mk_input(clk: Clock, h: History, topic: str, label: str) -> Event:
    ts = clk.tick(); pid = last_id(h)
    return Event(ts, rnd_id(), [pid] if pid else [], {"kind":"input","topic":topic}, f"{label}; topic={topic}")

def mk_repair(clk: Clock, h: History, topic: str) -> Event:
    ts = clk.tick(); pid = last_id(h)
    return Event(ts, rnd_id(), [pid] if pid else [], {"kind":"input","topic":topic}, "repair: summarize; topic="+topic)

def mk_noise(clk: Clock, parents: List[str], payload: str) -> Event:
    ts = clk.tick()
    return Event(ts, rnd_id(), parents, {"kind":"noise","noise_kind":"conflict(2)"}, payload)

def mk_observe(clk: Clock, parents: List[str], payload: str) -> Event:
    ts = clk.tick()
    return Event(ts, rnd_id(), parents, {"kind":"observe","observe":"conflict_heat"}, payload)

def conflict_heat(h: History, win: int = 14) -> Tuple[int, Tuple[str,int,str,int]]:
    inp = [e for e in h.events if e.meta.get("kind")=="input"]
    tail = inp[-win:]
    topics = [e.meta.get("topic","?") for e in tail]
    heat = sum(1 for i in range(1,len(topics)) if topics[i]!=topics[i-1])
    counts: Dict[str,int] = {}
    for t in topics: counts[t] = counts.get(t,0)+1
    dom = max(counts.items(), key=lambda kv: kv[1])[0] if counts else "?"
    domc = counts.get(dom,0)
    return heat, ("topic", heat, dom, domc)

def sig_no_dom(win: int, total_heat: int, top: Tuple[str,int,str,int]) -> str:
    key, heat, dom, _ = top
    return f"win={win};total_heat={total_heat};top={key}:{heat}:{dom}"

def frontier(h: History, mode: str = "global",
             last_inputs: int = 4, last_observes: int = 2,
             anc_depth: int = 6, topk: int = 20,
             recent_ms: int = 10) -> List[Event]:
    # roots = last N inputs + last M observes
    inputs: List[Event] = []; observes: List[Event] = []
    for e in reversed(h.events):
        k = e.meta.get("kind")
        if k=="input" and len(inputs)<last_inputs: inputs.append(e)
        elif k=="observe" and len(observes)<last_observes: observes.append(e)
        if len(inputs)>=last_inputs and len(observes)>=last_observes: break
    roots = list(reversed(observes)) + list(reversed(inputs))
    if not roots: return []

    # ✅ FIX: recent cutoff is relative to LAST event, not min_root_ts
    last_ts = h.events[-1].ts
    cutoff = last_ts - recent_ms

    skeleton: Set[str] = set()
    def walk(eid: str, depth: int) -> None:
        if depth>anc_depth or eid in skeleton: return
        e = h.by_id.get(eid)
        if not e: return
        if e.meta.get("kind") in ("input","observe"): skeleton.add(eid)
        for pid in e.parent_ids: walk(pid, depth+1)
    for r in roots: walk(r.id, 0)

    keep: Set[str] = set(skeleton)
    for e in h.events:
        if any(pid in skeleton for pid in e.parent_ids): keep.add(e.id)

    evs = [h.by_id[i] for i in keep if i in h.by_id]

    if mode == "recent":
        # keep roots even if older, but prune others by cutoff
        root_ids = {r.id for r in roots}
        evs = [e for e in evs if (e.id in root_ids) or (e.ts >= cutoff)]

    evs.sort(key=lambda e: trace_score(e, h), reverse=True)
    return evs[:topk]

def print_view(title: str, rows: List[Event], h: History, n: int = 20) -> None:
    print(f"\n== View: {title} ==")
    for e in rows[:n]:
        k = e.meta.get("kind"); p = len(e.parent_ids); sc = trace_score(e,h)
        tag = f" [{e.meta.get('noise_kind','noise')}]" if k=="noise" else ""
        print(f"{e.ts} {e.id} {k} score={fmt_score(sc)} p={p}{tag} | {e.payload[:92]}{'…' if len(e.payload)>92 else ''}")

def main():
    random.seed(7)
    clk = Clock(); h = History()
    WIN = 14
    COOLDOWN_MS = 2
    TOPICS = ["x","y","z"]
    last_obs_sig = None
    last_conflict_ts = -10**18

    # genesis
    t0 = random.choice(TOPICS)
    h.add(Event(clk.tick(), rnd_id(), [], {"kind":"input","topic":t0},
                f"evt0:{random.randint(1_000_000,9_999_999)}; topic={t0}"))

    for i in range(1, 28):
        t = random.choice(TOPICS)
        lab = f"evt{i}:{random.randint(1_000_000,9_999_999)}"
        e = mk_input(clk, h, t, lab); h.add(e)
        if i % 9 == 0: h.add(mk_repair(clk, h, random.choice(TOPICS)))

        heat, top = conflict_heat(h, WIN)
        key, _heat, dom, domc = top
        sig = sig_no_dom(WIN, heat, top)

        if sig != last_obs_sig:
            h.add(mk_observe(clk, [e.id],
                             f"observe=conflict_heat; win={WIN}; total_heat={heat}; top={key}:{heat}:{dom}:{domc}"))
            last_obs_sig = sig

        if heat >= 2 and (h.events[-1].ts - last_conflict_ts) >= COOLDOWN_MS:
            obs = next((x for x in reversed(h.events) if x.meta.get("kind")=="observe"), None)
            parents = [e.id] + ([obs.id] if obs else [])
            h.add(mk_noise(clk, parents,
                           f"NOISE:{rnd_id()}:conflict(2):top={key}:{heat}:{dom}:{domc}:{lab}; topic={t}"))
            last_conflict_ts = h.events[-1].ts

    print(f"\nHistory size: {len(h.events)} (append-only)")
    print_view("LAST_12", list(reversed(h.events))[:12], h, n=12)

    fr_recent = frontier(h, mode="recent", topk=20, recent_ms=10)
    fr_global = frontier(h, mode="global", topk=20)

    print_view("FRONTIER_RECENT top20 (ranked by trace_score)", fr_recent, h, n=20)
    print_view("FRONTIER_GLOBAL top20 (ranked by trace_score)", fr_global, h, n=20)

    obs_only = [e for e in h.events if e.meta.get("kind")=="observe"]
    obs_only.sort(key=lambda e: trace_score(e,h), reverse=True)
    print_view("OBSERVE_ONLY (ranked by trace_score)", obs_only, h, n=20)

    print("\nInvariant: no deletions, no edits. Only new events.")

if __name__ == "__main__":
    main()
