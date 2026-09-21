# The POW UK Causal Graph

Not a watchlist. A graph. Every node is a UK-listed security sensing a physical constraint.

## The Supply Chain

```
                  POWER
                    │
          NG ─ SSE ─ DRX
                    │
                    ▼
             POWERED LAND
                  BBOX
                    │
                    ▼
            COMPUTE DEPLOYMENT
                   CCC
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
     ELECTRONICS          SEMICONDUCTORS
 XPP VLX TTG DSCV       IQE
          │                    │
          └─────────┬──────────┘
                    ▼
                  COMPUTE
               RPI / CNC
                    ▲
                    │
          PHYSICAL MATERIALS
      PRE TUN ALL HE1 RHL SML
```

## What Each Node Senses

### Grid / Power
- **NG.** — grid capacity, transmission constraints, connection queue
- **SSE** — grid + generation balance, renewable integration
- **DRX** — dispatchable electricity, biomass/storage economics
- **CNA** — energy system balance, gas/storage

### Powered Land
- **BBOX** — data-centre land + power connection availability (250MW secured, 1GW pipeline)
- **SGRO** — industrial/logistics real estate with power read-through

### Compute Deployment
- **CCC** — enterprise compute deployment velocity (FTSE 100, "hyper scaled")

### Electronics
- **XPP** — power conversion supply/demand
- **VLX** — power + data interconnect availability
- **TTG** — electronic component supply
- **DSCV** — specialist component bottleneck detection

### Semiconductors
- **IQE** — compound semiconductor wafer supply (AIM, thin market = better sensor)

### Compute
- **RPI** — edge compute demand signal (FTSE 250)
- **CNC** — embedded compute demand (AIM/SETSqx, ~£226m)

### Physical Materials
- **PRE** — rare earth supply (Chinese policy → NdPr pricing → western scarcity)
- **TUN** — tungsten supply (Hemerdon restart, £71m NWF investment)
- **ALL** — lithium supply
- **SML** — strategic mineral exposure
- **HE1** — helium supply (semiconductor/scientific/cooling)
- **RHL** — helium supply (Tanzania Rukwa Basin)

## The Seesaw Mappings

### Tungsten (TUN) — Most Pow-Relevant

```
Chinese export policy
↓
tungsten spot / benchmark price
↓
western supply scarcity
↓
TUN valuation
↓
TUN book depth (L2)
↓
capital raising
↓
Hemerdon restart
↓
future tungsten supply
```

Question: Does the financial market reprice physical scarcity before or after the underlying constraint data?

### Helium (HE1 / Rhl) — Two Experiments

```
helium physical market
↓
supply announcements
↓
HE1 / RHL book (L2)
↓
capital flows
↓
exploration investment
↓
future helium supply
```

Two separate helium companies = replication within a single domain.

### Rare Earths (PRE)

```
Chinese rare-earth policy
↓
NdPr / magnet pricing
↓
western supply scarcity
↓
PRE valuation
↓
PRE L2 state
↓
capital raising
↓
project development
```

### AI Infrastructure Chain

```
mineral availability (PRE, TUN, ALL, HE1, RHL, SML)
       ↓
components (IQE, TTG, DSCV)
       ↓
power electronics (XPP)
       ↓
compute hardware (RPI, CNC, SOLI)
       ↓
datacentre deployment (CCC)
       ↓
powered land (BBOX)
       ↓
grid connection (NG., SSE)
       ↓
electricity generation (DRX, CNA)
       ↓
compute economics (CCC, RPI)
```

Every node has a UK-listed security. The L2 feed is a sensor on every node of this graph.
