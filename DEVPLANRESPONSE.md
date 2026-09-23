# DevPlan Response — Full Rendition

> Auto-generated audit of all POW repos. What exists, what works, what's missing, and what matters.

---

## The System at a Glance

```
Layer 1 — Observatories (data gardens)
  powpowpow  ─── 7/7 sources active ──── PoW chain compute, venue L2, WS ticks
  repair     ─── 6/7 sources active ──── Open Repair, eBay UK, DVLA, land registry
  powuk      ─── 0/8 sources active ──── NESO, PV Live, planning, ONS labour
  powstock   ─── 7/18 sources active ─── Yahoo prices, RNS, FCA, Companies House
  powproducts── 0/8 sources active ──── RobotShop, PCI IDs, ROBOTIS, MuJoCo
  powrobots  ─── 0/15 sources active ─── HMRC, UKRI, RBTX, Mouser, Farnell
  powphysical── 0/3 sources active ──── LCSC, M5Stack, Waveshare (fixtures only)

Layer 1 command centre
  powops     ─── Monitors all 7 gardens, 46 sources, dashboard at admin.pow.systems

Layer 2 — Deterministic kernel
  powk       ─── Constraint interchange format, snapshot building, counterfactuals
```

**Reality check:** 13/46 sources are actually collecting data. The other 33 are wired but blocked (missing keys, timeouts, API changes, Cloudflare).

---

## Per-Repo Status

### powpowpow — THE ONLY HEALTHY GARDEN

**What it collects:** PoW chain compute (QUBIC, XMR, KAS, AKT, NOCK), venue L2 order books, WebSocket tick archives.

**Status:** 7/7 sources green. 807K raw files on disk. All collectors running. This is the proof of concept that the architecture works.

**What's broken:** 6 systemd services failing (daily-state, qubic-computors, qubic-epoch, seed-rebuild, tardis-reload, tardis-remainder). Core collection works but derived state computation is down.

**Value to devplan:** This garden proves the heartbeat-based monitoring pattern works. powops reads `warehouse/chain_state_heartbeat.json` and confirms data is flowing. Replicate this pattern everywhere.

---

### repair — MOSTLY HEALTHY

**What it collects:** Open Repair (305K+ records), eBay UK parts pricing, DVLA vehicle data, land registry, planning applications, EU EPREL, France repairability index.

**Status:** 6/7 green, 1 stale (ebay_uk). 4 raw files. collector_db checks working.

**Value to devplan:** Second proof that collector_db monitoring works. The `collection_runs` table schema is different from powstock's `ingest_run` — powops handles both via fallback logic in `garden.py:215-238`.

---

### powuk — CODE EXISTS, NO DATA FLOWING

**What it collects:** NESO demand/generation (hourly), PV Live solar output, planning apps, ONS labour market, APAR training providers, Ofqual qualifications, Contracts Finder procurement.

**Status:** 0/8 sources. No health artifacts on disk. The garden directory exists at `/root/powuk` but has only 2 commits and 612KB.

**What's there:** A physical constraint graph definition (2 commits: "UK physical constraint graph" and "narrow Companies House + APAR + capability_provider entity"). No collectors implemented.

**Value to devplan:** This is the most important garden for the "physical scarcity repricing" thesis — it would provide the constraint data that powstock's signals react to. Currently empty. Needs full collector implementation.

---

### powstock — PARTIALLY WORKING, DATA-STARVED

**What it collects:** UK equity prices (25 tickers), RNS announcements, Companies House profiles, FCA PDMR insider deals, FCA short interest, takeover panel, TR-1 notifications, commodity prices.

**Status:** 7/18 active, 1 stale, 1 needs key, 10 not installed.

**The real problem:** The architecture is solid but the data is thin:
- `price_daily`: 24 rows (1 day only, NOT historical)
- `insider_deals`: 4 rows (all wrong ticker — GTE, not our 25 universe stocks)
- `short_interest`: 421 positions (only CNA matched to universe)
- `rns_announcements`: 891 rows (working, 18 tickers)
- `company_profiles`: 25 rows (working, all 25 universe companies)

**The thesis blocker:** Without insider data for the 25 universe tickers, 4 of 10 signals compute None. Without historical prices, momentum signals are empty. The "seesaw" question cannot be tested.

**Value to devplan:** The ArtifactStore + IngestRun lifecycle is the real engineering win. Content-addressed raw storage with provenance tracking is genuinely useful. But the project needs a Tracefour API key (free) and price backfill to produce actual signal.

---

### powproducts — SCAFFOLDING ONLY

**What it would collect:** RobotShop UK components, PCI device IDs, OSHWA certifications, ROBOTIS Dynamixel specs, robot descriptions (URDF/XACRO), MuJoCo models, Blender assets, MicroBT mining hardware.

**Status:** 0/8 active (7 not_installed, 1 unknown). DB exists but empty.

**Value to devplan:** This garden feeds the "canonical product identity" layer — what components exist, what's compatible, what's available. Essential for the commercial thesis (UK robotics parts intelligence) but no collectors implemented.

---

### powrobots — MOST COMPLEX, NOTHING WORKING

**What it would collect:** HMRC traders/trade flows, UKRI research grants, RBTX marketplace, OPSS safety recalls, BARA member directory, BGS minerals, Contracts Finder, ONS PPI, apprenticeships, Companies House registrations, Mouser/Farnell/LCSC component pricing, eBay UK robotics.

**Status:** 0/15 active. 10 unknown, 5 need API keys (Companies House, Mouser, Farnell, LCSC, eBay).

**Value to devplan:** This is the supply chain intelligence layer. When working, it answers: "Who is importing/exporting robotics components? What does it cost? Where are the bottlenecks?" Most complex garden, most API dependencies.

---

### powphysical — FIXTURES ONLY

**What it would collect:** LCSC component search, M5Stack modules, Waveshare modules.

**Status:** 0/3 active. All fixture-only adapters, no real data collection.

**Value to devplan:** Supplier adapter layer for BOM resolution. Lowest priority.

---

### powops — WORKING COMMAND CENTRE

**What it does:** Monitors all 7 gardens, 46 sources. Dashboard at admin.pow.systems. MCP server for Pi agent. CLI tools. Alert/incident system. History with chain hashing. GitHub repo status.

**Status:** Core engine works. 69 tests passing. The two healthy gardens (powpowpow, repair) are properly monitored. powstock integration just completed (18 sources wired).

**What's missing:**
- Webhook alerts (infrastructure done, no URLs configured)
- Coverage view (health != completeness)
- Backup status view
- Source detail drill-down
- Garden-owned manifests (currently central sources.yaml will drift)
- 5 of 7 gardens have no data to monitor

**Value to devplan:** This is the operational nervous system. When all gardens are collecting, powops is how you know if the data is flowing. The MCP toolset (16 read-only tools) is how the Pi agent queries operational state.

---

### powk — DETERMINISTIC KERNEL

**What it does:** Reconstructs dated dependency states, runs versioned models against them. Five canonical types: NODE, EDGE, OBSERVATION, EVIDENCE, DERIVATION.

**Status:** 3 commits. Code complete for v0.2 spec. Adapters exist for powpowpow and repair. No real data flowing through it yet.

**Value to devplan:** This is the Layer 2 engine. When powstock has real data, powk can build snapshots and run constraint pressure models. The key invariant: "Same snapshot + same model bytes = same derivation." Deterministic, reproducible, auditable.

---

## What the DevPlan Is Missing

### 1. The Data Gap Is the Real Problem

The DEVPLAN lists 21 items as "DONE" but the DB has:
- 24 price rows (1 day, not historical)
- 4 insider deals (all wrong ticker)
- 0 financial fundamentals (no XBRL parser)
- 0 entity resolution (dead code)

**The architecture is done. The data is not.** The devplan should acknowledge this and prioritize data flow over new features.

### 2. Missing Source: Tracefour API

Free API key needed. Provides structured UK PDMR data. Would fix the insider deals problem (currently scraping Investegate global feed, getting non-universe stocks). This is the single highest-impact unblock.

### 3. Missing Source: Price Backfill

`backfill_prices.py` exists but hasn't run. Need to populate historical prices for the 25 universe tickers. Without this, momentum signals (50d, 200d, MA crossover, drawdown) are all None.

### 4. Missing: Financial Fundamentals

No XBRL parser exists. `financials.py` needs `stream-read-xbrl` (not installed). Without revenue, cash, debt, employees — the daily state builder produces mostly-NULL states.

### 5. Missing: Entity Resolution

The entity resolver (`entity_resolver.py`) is dead code — never imported, has httpx import bug at line 191. Without it, you can't link people across companies (the "who knew, who moved capital" question).

### 6. Missing: Experiments

The `experiments/` directory is empty. The seesaw thesis has not been tested. No hypothesis has been formulated, no data collected, no results recorded.

### 7. Missing: powops Integration for All Gardens

Only powstock is wired into powops with collector_db checks. The other 5 gardens either use different check types or aren't connected. The devplan should specify which gardens feed which Layer 2 systems.

### 8. Missing: Layer 1 Daemon

`layer1/collect.py` is listed as PENDING in the devplan. Without a daemon, collection only happens when someone manually runs `run_all()`. Needs cron or systemd timer.

---

## Threads Worth Pulling

### Thread 1: The 13 Active Sources

These are actually working and producing data:

| Garden | Source | Records | Last Run |
|--------|--------|---------|----------|
| powpowpow | chain_state | live | continuous |
| powpowpow | venue_l2 | live | continuous |
| powpowpow | venue_ws | live | continuous |
| powpowpow | qubic_collector | live | continuous |
| powpowpow | prl_collector | live | continuous |
| powpowpow | xmr_collector | live | continuous |
| powpowpow | clore_collector | live | continuous |
| repair | open_repair | 305K+ | daily |
| repair | dvla | live | daily |
| repair | land_registry | live | daily |
| repair | planning_data | live | daily |
| repair | eprel | live | daily |
| repair | france_repairability | live | daily |

Plus powstock's 7 active sources (yahoo, rns, ch, pdmr, ansp, takeover, tr1, commodities).

### Thread 2: The 33 Blocked Sources

These need action:

**Need API keys (5):**
- finnhub → FINNHUB_API_KEY
- companies_house → POWSTOCK_COMPANIES_HOUSE_API_KEY
- companies_house_filings → POWSTOCK_COMPANIES_HOUSE_API_KEY
- mouser → MOUSER_API_KEY
- farnell → FARNELL_API_KEY
- lcsc → LCSC_API_KEY
- ebay_uk → EBAY_APP_ID

**Need network/timeout fixes (8):**
- uk_parliament, congress_trades → timeout on scrape
- european_insiders → API returns HTML
- dmo_gilts → Cloudflare captcha
- fca_nsm → Cloudflare 403
- ch_company_snapshot, ch_accounts_bulk, companies_house_psc → download timeout

**Need implementation (20):**
- powproducts: 8 sources (RobotShop, PCI IDs, OSHWA, ROBOTIS, robot descriptions, MuJoCo, Blender, MicroBT)
- powrobots: 15 sources (HMRC, UKRI, RBTX, OPSS, BARA, BGS, contracts, ONS PPI, apprenticeships, companies_house, mouser, farnell, lcsc, ebay)
- powphysical: 3 sources (LCSC, M5Stack, Waveshare)

### Thread 3: The Signal Chain

powstock has 10 signals that depend on data that mostly doesn't exist yet:

| Signal | Depends On | Data Status |
|--------|-----------|-------------|
| insider_pressure | insider_deals | 4 rows, wrong ticker |
| short_interest_level | short_interest | 421 rows, weak matching |
| short_squeeze_risk | short_interest | same |
| filing_event_signal | company_profiles | 25 rows, working |
| alignment_score | insider + short | partial |
| anomaly_score | insider vs short | partial |
| composite_score | all above | partial |
| price_momentum_50d | price_daily | 1 day only |
| price_momentum_200d | price_daily | 1 day only |
| moving_average_crossover | price_daily | 1 day only |
| drawdown_from_peak | price_daily | 1 day only |

**Only 2 of 10 signals can produce meaningful output today** (filing_event_signal and short_interest_level). The rest need insider data for universe tickers and historical prices.

### Thread 4: The powops Monitoring Chain

```
Garden Collector
  │
  ├─ writes raw bytes → ArtifactStore (content-addressed)
  ├─ writes ingest_run → collector_run view → powops reads
  ├─ writes heartbeat.json → powops reads
  └─ writes normalized facts → signal computation
       │
       └─ powops checks: "Is data flowing?"
            │
            ├─ ok → green light
            ├─ stale → data older than threshold
            ├─ error → collection failed
            ├─ no_key → missing API credential
            └─ not_installed → collector not wired
```

### Thread 5: The Commercial Thesis

From vision docs, the commercial opportunity is:
1. **UK robotics parts intelligence** — canonical product identity, compatibility, pricing
2. **Repair outcomes data** — what breaks, what gets fixed, what parts are needed
3. **Supply chain visibility** — who imports what, from where, at what cost
4. **Physical scarcity signals** — constraint data before it shows up in financials

powstock provides thread 4. repair provides thread 2. powproducts + powrobots would provide threads 1 and 3. None of the commercial gardens are collecting yet.

---

## Priority Actions (What the DevPlan Should Say)

### Immediate (this week)
1. Get Tracefour API key → fix insider data for universe tickers
2. Run price backfill → populate historical prices
3. Fix 10 blocked powstock collectors → get more sources green in powops

### Short-term (this month)
4. Implement powuk collectors → NESO demand/generation is free and hourly
5. Wire powpowpow derived state services → fix the 6 failing systemd units
6. Add powops webhook alerts → know when things break

### Medium-term (next quarter)
7. Implement powproducts collectors → RobotShop, PCI IDs, ROBOTIS
8. Implement powrobots collectors → HMRC, UKRI, component pricing
9. Build iXBRL parser → financial fundamentals for daily state
10. Wire entity resolver → link people across companies

### Long-term (this year)
11. Run first seesaw experiment → test the thesis
12. Build commercial products → UK robotics parts intelligence
13. Deploy powops to production → admin.pow.systems with real monitoring
14. Garden-owned manifests → each garden declares its own sources
