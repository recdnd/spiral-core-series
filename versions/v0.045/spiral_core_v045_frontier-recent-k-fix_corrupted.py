# spiral_core_v045_frontier-recent-k-fix.py  (<200 lines)
import time, random, hashlib, math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set

def now_ms(): return int(time.time()*1000)
def h16(s): return hashlib.sha1(s.encode()).hexdigest()[:16]
def rnd_id(): return h16(str(random.random())+str(now_ms()))

class Clock:
    def __init__(self): self.t = now_ms()
    def tick(self, step=1):
        cur = now_ms()
        self.t = max(self.t + step, cur)
        return self.t

@dataclass
class Event:
    ts:int; id:str; parent_ids:List[str]
    meta:Dict[str,Any]=field(default_factory=dict)
    payload:str=""

@dataclass
class History:
    events:List[Event]=field(default_factory=list)
    by_id:Dict[str,Event]=field(default_factory=dict)
    def add(self,e): self.events.append(e); self.by_id[e.id]=e

def fmt_score(x): return f"{x:.3e}" if x < 1e-2 else f"{x:.3f}"
def last_id(h): return h.events[-1].id if h.events else None

def trace_score(e,h,half_life_ms=450):
    age = max(0, h.events[-1].ts - e.ts)
    return math.exp(-age/max(1,half_life_ms))

def mk_input(clk,h,topic,label):
    ts=clk.tick(); pid=last_id(h)
    return Event(ts,rnd_id(),[pid] if pid else [],{"kind":"input","topic":topic},f"{label}; topic={topic}")

def mk_repair(clk,h,topic):
    ts=clk.tick(); pid=last_id(h)
    return Event(ts,rnd_id(),[pid] if pid else [],{"kind":"input","topic":topic},f"repair: summarize; topic={topic}")

def mk_noise(clk,parents,payload):
    ts=clk.tick()
    return Event(ts,rnd_id(),parents,{"kind":"noise","noise_kind":"conflict(2)"},payload)

def mk_observe(clk,parents,payload):
    ts=clk.tick()
    return Event(ts,rnd_id(),parents,{"kind":"observe","observe":"conflict_heat"},payload)

def conflict_heat(h,win=14):
    inp=[e for e in h.events if e.meta.get("kind")=="input"]
    tail=inp[-win:]
    topics=[e.meta.get("topic","?") for e in tail]
    heat=sum(1 for i in range(1,len(topics)) if topics[i]!=topics[i-1])
    counts={}
    for t in topics: counts[t]=counts.get(t,0)+1
    dom=max(counts.items(), key=lambda kv: kv[1])[0] if counts else "?"
    return heat, ("topic",heat,dom,counts.get(dom,0))

def sig_no_dom(win,total_heat,top):
    key,heat,dom,_=top
    return f"win={win};total_heat={total_heat};top={key}:{heat}:{dom}"

def frontier(h, mode="global",
             last_inputs=4, last_observes=2,
             anc_depth=6, topk=20,
             recent_k=12):
    # roots = last N inputs + last M observes
    inputs=[]; observes=[]
    for e in reversed(h.events):
        k=e.meta.get("kind")
        if k=="input" and len(inputs)<last_inputs: inputs.append(e)
        elif k=="observe" and len(observes)<last_observes: observes.append(e)
        if len(inputs)>=last_inputs and len(observes)>=last_observes: break
    roots=list(reversed(observes))+list(reversed(inputs))
    if not roots: return []

    def closure(seed_ids:Set[str]) -> Set[str]:
        keep=set()
        stack=[(sid,0) for sid in seed_ids if sid]
        while stack:
            eid,d=stack.pop()
            if eid in keep or d>anc_depth: continue
            e=h.by_id.get(eid)
            if not e: continue
            keep.add(eid)
            for pid in e.parent_ids:
                if pid: stack.append((pid,d+1))
        return keep

    if mode=="recent":
        tail_ids={e.id for e in h.events[-recent_k:]}
        root_ids={r.id for r in roots}
        seed = tail_ids | root_ids
        keep_ids = closure(seed)
        # also keep children of keep_ids (one-hop forward) so linked noise/observe stays visible
        for e in h.events:
            if any(pid in keep_ids for pid in e.parent_ids):
                keep_ids.add(e.id)
        evs=[h.by_id[i] for i in keep_ids if i in h.by_id]
    else:
        # global: build skeleton from roots, then keep edges that touch skeleton
        skel=closure({r.id for r in roots})
        keep=set(skel)
        for e in h.events:
            if any(pid in skel for pid in e.parent_ids):
                keep.add(e.id)
        evs=[h.by_id[i] for i in keep if i in h.by_id]

    evs.sort(key=lambda e: trace_score(e,h), reverse=True)
    return evs[:topk]

def print_view(title, rows, h, n=20):
    print(f"\n== View: {title} ==")
    for e in rows[:n]:
        k=e.meta.get("kind"); p=len(e.parent_ids); sc=trace_score(e,h)
        tag=f" [{e.meta.get('noise_kind','noise')}]" if k=="noise" else ""
        print(f"{e.ts} {e.id} {k} score={fmt_score(sc)} p={p}{tag} | {e.payload[:92]}{'…' if len(e.payload)>92 else ''}")

def main():
    random.seed(7)
    clk=Clock(); h=History()
    WIN=14; COOLDOWN_MS=2; TOPICS=["x","y","z"]
    last_obs_sig=None; last_conflict_ts=-10**18

    t0=random.choice(TOPICS)
    h.add(Event(clk.tick(),rnd_id(),[],{"kind":"input","topic":t0},f"evt0:{random.randint(1_000_000,9_999_999)}; topic={t0}"))

    for i in range(1,28):
        t=random.choice(TOPICS); lab=f"evt{i}:{random.randint(1_000_000,9_999_999)}"
        e=mk_input(clk,h,t,lab); h.add(e)
        if i%9==0: h.add(mk_repair(clk,h,random.choice(TOPICS)))

        heat, top = conflict_heat(h,WIN)
        key,_heat,dom,domc=top
        sig=sig_no_dom(WIN,heat,top)

        if sig!=last_obs_sig:
            h.add(mk_observe(clk,[e.id],f"observe=conflict_heat; win={WIN}; total_heat={heat}; top={key}:{heat}:{dom}:{domc}"))
            last_obs_sig=sig

        if heat>=2 and (h.events[-1].ts-last_conflict_ts)>=COOLDOWN_MS:
            obs=next((x for x in reversed(h.events) if x.meta.get("kind")=="observe"), None)
            parents=[e.id]+([obs.id] if obs else [])
            h.add(mk_noise(clk,parents,f"NOISE:{rnd_id()}:conflict(2):top={key}:{heat}:{dom}:{domc}:{lab}; topic={t}"))
            last_conflict_ts=h.events[-1].ts

    print(f"\nHistory size: {len(h.events)} (append-only)")
    print_view("LAST_12", list(reversed(h.events))[:12], h, n=12)
    fr_recent = frontier(h, mode="recent", topk=20, recent_k=10)
    fr_global = frontier(h, mode="global", topk=20)
    print_view("FRONTIER_RECENT_K_FIXED top20 (ranked by trace_score)", fr_recent, h, n=20)
    print_view("FRONTIER_GLOBAL top20 (ranked by trace_score)", fr_global, h, n=20)

    obs=[e for e in h.events if e.meta.get("kind")=="observe"]
    obs.sort(key=lambda e: trace_score(e,h), reverse=True)
    print_view("OBSERVE_ONLY (ranked by trace_score)", obs, h, n=20)
    print("\nInvariant: no deletions, no edits. Only new events.")

if __name__=="__main__":
    main()
