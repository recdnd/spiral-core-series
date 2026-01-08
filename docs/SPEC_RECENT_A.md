## A-Mode Frontier (RECENT_A) — Clean Spec

**Context**:
- Concept / intuition: [`ABSTRACT.md`](ABSTRACT.md)
- Engineering narrative: [`WHITEPAPER.md`](WHITEPAPER.md)

---

### 1) Data model

**Events.**  
Let the event universe be E={e0,e1,… }\mathcal{E}=\{e_0,e_1,\dots\}E={e0​,e1​,…}. Each event is

e=(ide,  te,  ke,  Pe,  se)e = (\mathrm{id}_e,\; t_e,\; k_e,\; P_e,\; s_e)e=(ide​,te​,ke​,Pe​,se​)

- ide∈H\mathrm{id}_e \in \mathcal{H}ide​∈H: hash/id space
    
- te∈Rt_e \in \mathbb{R}te​∈R: timestamp
    
- ke∈{input,observe,noise,repair}k_e \in \{\text{input},\text{observe},\text{noise},\text{repair}\}ke​∈{input,observe,noise,repair}
    
- Pe⊆HP_e \subseteq \mathcal{H}Pe​⊆H: parent id list/set
    
- se∈R+s_e \in \mathbb{R}^+se​∈R+: trace score (ranking only)
    

**Append-only history.**  
History is a strictly append-only sequence:

H=⟨e0≺e1≺⋯≺en⟩\mathcal{H} = \langle e_0 \prec e_1 \prec \cdots \prec e_n\rangleH=⟨e0​≺e1​≺⋯≺en​⟩

with invariant i<j⇒tei≤teji<j \Rightarrow t_{e_i}\le t_{e_j}i<j⇒tei​​≤tej​​. No deletions, no edits.

---

### 2) Causal DAG

Define directed graph G=(E,→)G=(\mathcal{E},\to)G=(E,→) where

p→e  ⟺  idp∈Pep \to e \iff \mathrm{id}_p \in P_ep→e⟺idp​∈Pe​

Assume GGG is a DAG (parents always point to same-or-earlier events).

---

### 3) Trace score (ranking only)

trace_score:E→R+\mathrm{trace\_score}:\mathcal{E}\to\mathbb{R}^+trace_score:E→R+

Constraints:

- does **not** affect event generation
    
- does **not** affect causal edges
    
- used **only** for sorting in views
    

---

### 4) Seed (time seed)

For a chosen K≥1K\ge 1K≥1, define the last-KKK events:

SeedK(H)={en−K+1,…,en}\mathrm{Seed}_K(\mathcal{H}) = \{e_{n-K+1},\dots,e_n\}SeedK​(H)={en−K+1​,…,en​}

---

## 5) Closure operator (Trace-Closure)

We build the minimal “explanation-closed” set around SeedK\mathrm{Seed}_KSeedK​. There are two expansions:

### 5.1 Upward closure: Ancestry (causal backtrace)

For any set S⊆ES\subseteq\mathcal{E}S⊆E, include ancestors (within depth cutoff DDD):

If e∈Se\in Se∈S and p→ep\to ep→e, then ppp must be included. Recursively apply until:

- no new parents, or
    
- depth exceeds DDD
    

(Depth cutoff DDD is your `anc_depth`.)

### 5.2 Downward closure: Reactive explanation (system responses)

Include reactive “explainers” that are _bound_ to nodes already included:

If p∈Sp\in Sp∈S, and there exists eee such that p→ep\to ep→e and

ke∈{observe,noise,repair}k_e \in \{\text{observe},\text{noise},\text{repair}\}ke​∈{observe,noise,repair}

then include eee.

(Engineering reading: if an observe/noise/repair points to something we keep, keep that response too, so the graph remains interpretable.)

### 5.3 Fixed point (minimal closed set)

Let C(⋅)C(\cdot)C(⋅) denote “apply 5.1 and 5.2 once”. Define:

C∗(S)=min⁡{T∣S⊆T ∧ C(T)=T}C^*(S)=\min\{T\mid S\subseteq T\ \wedge\ C(T)=T\}C∗(S)=min{T∣S⊆T ∧ C(T)=T}

---

## 6) A-Mode Frontier (RECENT_A / “recent causal frontier”)

### 6.1 Set definition

RECENTA(K)=C∗(SeedK(H))\mathrm{RECENT}_A(K)=C^*(\mathrm{Seed}_K(\mathcal{H}))RECENTA​(K)=C∗(SeedK​(H))

This is: **the minimal causally+reactively closed subgraph generated from the last KKK events**.

### 6.2 Output ordering (view only)

Return as a ranked view:

sort↓(RECENTA,  (se,  te))\mathrm{sort}_\downarrow(\mathrm{RECENT}_A,\; (s_e,\; t_e))sort↓​(RECENTA​,(se​,te​))

---

## 7) Formal guarantees

### P1. Causal completeness (ancestry closed)

For every e∈RECENTAe\in \mathrm{RECENT}_Ae∈RECENTA​, all its parents (within depth cutoff) are also in RECENTA\mathrm{RECENT}_ARECENTA​.

### P2. Recent explainability (connected to seed)

For every e∈RECENTAe\in \mathrm{RECENT}_Ae∈RECENTA​, there exists r∈SeedKr\in \mathrm{Seed}_Kr∈SeedK​ such that there is a causal path e⇝re\leadsto re⇝r or r⇝er\leadsto er⇝e.

### P3. Score orthogonality

Membership in RECENTA\mathrm{RECENT}_ARECENTA​ is determined by causal/semantic closure, **not** by maximizing ses_ese​.

---

## 8) One-line paper sentence (English)

> Let RECENTA(K)\mathrm{RECENT}_A(K)RECENTA​(K) be the minimal causally closed subgraph induced by the last KKK events, augmented with reactive system responses (observe/noise/repair) that directly reference nodes in the subgraph.

---

# Non-equivalence: RECENT_A vs Sliding Window

### Definitions

**Sliding window:**

SWK(H)={en−K+1,…,en}\mathrm{SW}_K(\mathcal{H})=\{e_{n-K+1},\dots,e_n\}SWK​(H)={en−K+1​,…,en​}

**RECENT_A:**

RECENTA(K)=C∗(SWK(H))\mathrm{RECENT}_A(K)=C^*(\mathrm{SW}_K(\mathcal{H}))RECENTA​(K)=C∗(SWK​(H))

### Claim

For any fixed K≥1K\ge 1K≥1, there exists a history H\mathcal{H}H such that

RECENTA(K)≠SWK(H)\mathrm{RECENT}_A(K) \ne \mathrm{SW}_K(\mathcal{H})RECENTA​(K)=SWK​(H)

### Minimal intuition

Sliding window is **purely time-based** (only truncates).  
RECENT_A is **causal-based** (can pull older ancestors back in, and pull in bound reactive events). Therefore they cannot be equivalent in general.

---

## Engineering counterexample (matches your log semantics)

Take K=2K=2K=2. Construct these events (timestamps increasing):

1. AAA: input
    
2. BBB: input
    
3. OOO: observe with **parents bound to the conflict input pair** (your v0.46 rule)
    
    PO={A,B}P_O=\{A,B\}PO​={A,B}
4. RRR: repair referencing the observe
    
    PR={O}P_R=\{O\}PR​={O}
5. NNN: noise referencing the observe (or conflict pair)
    
    PN={O,… }P_N=\{O,\dots\}PN​={O,…}

Now:

- Sliding window:
    
    SW2={R,N}\mathrm{SW}_2=\{R,N\}SW2​={R,N}
- RECENT_A starts from {R,N}\{R,N\}{R,N}, pulls in parents:
    
    - R→O⇒O∈RECENTAR\to O\Rightarrow O\in \mathrm{RECENT}_AR→O⇒O∈RECENTA​
        
    - N→O⇒O∈RECENTAN\to O\Rightarrow O\in \mathrm{RECENT}_AN→O⇒O∈RECENTA​
        
    - O→{A,B}⇒A,B∈RECENTAO\to \{A,B\}\Rightarrow A,B\in \mathrm{RECENT}_AO→{A,B}⇒A,B∈RECENTA​
        

So:

RECENTA(K)⊇{R,N,O,A,B}≠{R,N}=SW2\mathrm{RECENT}_A(K)\supseteq\{R,N,O,A,B\}\ne \{R,N\}=\mathrm{SW}_2RECENTA​(K)⊇{R,N,O,A,B}={R,N}=SW2​

**Key reason**: the observe/noise binding introduces edges that jump outside the time window; closure must pull those ancestors back.