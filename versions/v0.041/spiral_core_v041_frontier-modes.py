# spiral_core_v041_frontier-modes.py  (<200 lines)
import time, random, hashlib, math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple

def now_ms() -> int: return int(time.time() * 1000)
def h16(s: str) -> str: return hashlib.sha1(s.encode()).hexdigest()[:16]
def rnd_id() -> str: return h16(str(random.random()) + str(now_ms()))
def clamp(x,a,b): return max(a,min(b,x))

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
        self.events.append(e)
        self.by_id[e.id] = e

def trace_score(e: Event, h: History, half_life_ms: int = 450) -> float:
    # recency-based trace_score (stable, simple)
    age = max(0, h.events[-1].ts - e.ts) if h.events else 0
    return math.exp(-age / max(1, half_life_ms))

def fmt_score(x: float) -> str:
    return f"{x:.3e}" if x < 1e-2 else f"{x:.3f}"

def last_id(h: History) -> Optional[str]:
    return h.events[-1].id if h.events else None

def mk_input(h: History, topic: str, label: str) -> Event:
    ts = now_ms()
    pid = last_id(h)
    eid = rnd_id()
    payload = f"{label}; topic={topic}"
    return Event(ts=ts, id=eid, parent_ids=[pid] if pid else [], meta={"kind":"input","topic":topic}, payload=payload)

def mk_repair(h: History, topic: str) -> Event:
    ts = now_ms()
    pid = last_id(h)
    eid = rnd_id()
    return Event(ts=ts, id=eid, parent_ids=[pid] if pid else [], meta={"kind":"input","topic":topic}, payload="repair: summarize; topic="+topic)

def mk_noise(h: History, kind: str, parents: List[str], payload: str) -> Event:
    ts = now_ms()
    eid = rnd_id()
    return Event(ts=ts, id=eid, parent_ids=parents, meta={"kind":"noise","noise_kind":kind}, payload=payload)

def mk_observe(h: History, parents: List[str], obs: str, payload: str) -> Event:
    ts = now_ms()
    eid = rnd_id()
    return Event(ts=ts, id=eid, parent_ids=parents, meta={"kind":"observe","observe":obs}, payload=payload)

def conflict_heat(h: History, win: int = 14) -> Tuple[int, Tuple[str,int,str,int]]:
    # heat = count(topic switches in last win inputs)
    inp = [e for e in h.events if e.meta.get("kind")=="input"]
    tail = inp[-win:]
    topics = [e.meta.get("topic","?") for e in tail]
    heat = 0
    for i in range(1, len(topics)):
        if topics[i] != topics[i-1]: heat += 1
    # top key: topic:heat:dominant:count
    counts: Dict[str,int] = {}
    for t in topics: counts[t] = counts.get(t,0)+1
    dominant = max(counts.items(), key=lambda kv: kv[1])[0] if counts else "?"
    dom_count = counts.get(dominant,0)
    top = ("topic", heat, dominant, dom_count)
    return heat, top

def sig_no_dom(win: int, total_heat: int, top: Tuple[str,int,str,int]) -> str:
    # signature excludes dominant_count
    key, heat, dom, _domc = top
    return f"win={win};total_heat={total_heat};top={key}:{heat}:{dom}"

def frontier(h: History, mode: str = "global",
             last_inputs: int = 4, last_observes: int = 2,
             anc_depth: int = 6, topk: int = 20, recent_ms: int = 800) -> List[Event]:
    # roots: ensure observe cannot be starved
    inputs: List[Event] = []
    observes: List[Event] = []
    for e in reversed(h.events):
        k = e.meta.get("kind")
        if k == "input" and len(inputs) < last_inputs: inputs.append(e)
        elif k == "observe" and len(observes) < last_observes: observes.append(e)
        if len(inputs) >= last_inputs and len(observes) >= last_observes: break
    roots = list(reversed(observes)) + list(reversed(inputs))
    if not roots: return []

    min_root_ts = min(r.ts for r in roots)
    cutoff = min_root_ts - recent_ms

    skeleton: Set[str] = set()
    def walk(eid: str, depth: int) -> None:
        if depth > anc_depth or eid in skeleton: return
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
        evs = [e for e in evs if e.ts >= cutoff]
    evs.sort(key=lambda e: trace_score(e, h), reverse=True)
    return evs[:topk]

def print_view(title: str, rows: List[Event], h: History, n: int = 20) -> None:
    print(f"\n== View: {title} ==")
    for e in rows[:n]:
        k = e.meta.get("kind")
        p = len(e.parent_ids)
        sc = trace_score(e, h)
        tag = ""
        if k == "noise": tag = f" [{e.meta.get('noise_kind','noise')}]"
        if k == "observe": tag = ""
        print(f"{e.ts} {e.id} {k} score={fmt_score(sc)} p={p}{tag} | {e.payload[:92]}{'…' if len(e.payload)>92 else ''}")

def main():
    random.seed(7)
    h = History()

    # knobs
    WIN = 14
    COOLDOWN_CONFLICT = 2
    TOPICS = ["x","y","z"]

    last_obs_sig = None
    last_conflict_ts = 0

    # genesis
    h.add(Event(ts=now_ms(), id=rnd_id(), parent_ids=[], meta={"kind":"input","topic":random.choice(TOPICS)}, payload="evt0:"+str(random.randint(1_000_000,9_999_999))+"; topic="+random.choice(TOPICS)))
    # run
    for i in range(1, 28):
        t = random.choice(TOPICS)
        lab = f"evt{i}:{random.randint(1_000_000,9_999_999)}"
        e = mk_input(h, t, lab)
        h.add(e)

        # maybe repair
        if i % 9 == 0:
            h.add(mk_repair(h, random.choice(TOPICS)))

        # observe conflict_heat only on signature change (sig excludes dominant_count; payload keeps count)
        heat, top = conflict_heat(h, WIN)
        sig = sig_no_dom(WIN, heat, top)
        key, _heat, dom, domc = top
        if sig != last_obs_sig:
            # parents bind to the latest input that caused change
            obs_parents = [e.id]
            payload = f"observe=conflict_heat; win={WIN}; total_heat={heat}; top={key}:{heat}:{dom}:{domc}"
            h.add(mk_observe(h, obs_parents, "conflict_heat", payload))
            last_obs_sig = sig

        # conflict-trigger noise with cooldown=2 (tied to latest observe + input)
        if heat >= 2:
            if (h.events[-1].ts - last_conflict_ts) >= COOLDOWN_CONFLICT:
                # bind to latest input + latest observe (if exists)
                obs = next((x for x in reversed(h.events) if x.meta.get("kind")=="observe"), None)
                parents = [e.id] + ([obs.id] if obs else [])
                payload = f"NOISE:{rnd_id()}:conflict(2):top={key}:{heat}:{dom}:{domc}:{lab}; topic={t}"
                h.add(mk_noise(h, "conflict(2)", parents, payload))
                last_conflict_ts = h.events[-1].ts

    # print
    print(f"\nHistory size: {len(h.events)} (append-only)")
    print_view("LAST_12", list(reversed(h.events))[:12], h, n=12)

    fr_recent = frontier(h, mode="recent", topk=20, recent_ms=800)
    fr_global = frontier(h, mode="global", topk=20)

    print_view("FRONTIER_RECENT top20 (ranked by trace_score)", fr_recent, h, n=20)
    print_view("FRONTIER_GLOBAL top20 (ranked by trace_score)", fr_global, h, n=20)

    obs_only = [e for e in h.events if e.meta.get("kind")=="observe"]
    obs_only.sort(key=lambda e: trace_score(e,h), reverse=True)
    print_view("OBSERVE_ONLY (ranked by trace_score)", obs_only, h, n=20)

    print("\nInvariant: no deletions, no edits. Only new events.")

if __name__ == "__main__":
    main()
