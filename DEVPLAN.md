# POWStocks Development Plan

## The Thesis

> UK physical-economy capital-allocation observatory

Not a stock screener. A continuously-growing, provenance-preserving historical model of how physical constraints get repriced through UK-listed and private equities.

> Who is allocating capital into, out of, and around the physical bottlenecks of the UK economy — and how is that changing before it becomes obvious in reported financials?

## The Entity Graph

```
Companies House ───────────────┐
                               │
FCA / NSM / RNS ───────────────┤
                               │
Takeover Panel ────────────────┤
                               │
Company annual reports ────────┤
                               │
Planning / energy / procurement├──► ENTITY GRAPH
                               │
POWUK physical data ───────────┤
                               │
Commodity / energy prices ─────┤
                               │
Market prices / L2 ────────────┘
                                      │
                                      ▼
                         CAPITAL ALLOCATION GRAPH
                                      │
                  ┌───────────────────┼────────────────┐
                  ▼                   ▼                ▼
               INSIDERS          OWNERSHIP          COMPANY
                buying            changes            actions
                  │                   │                │
                  └───────────────────┼────────────────┘
                                      ▼
                          POW BOTTLENECK EXPOSURE
                                      │
                                      ▼
                         HISTORICAL DAILY STATE
```

## Collection Tiers

### TIER 1 — PLANT IMMEDIATELY
- Companies House company snapshot
- Companies House daily PSC
- Companies House accounts
- Companies House REST/stream
- FCA NSM/RNS
- FCA TR-1 related disclosures
- Takeover Panel disclosures
- Tracefour PDMR API
- Finnhub insider transactions

### TIER 2
- Bulk officer history (Product 216)
- Bulk charge history (Product 199/201)
- Bulk liquidations (Product 197)
- Companies House document extraction (iXBRL)
- Issuer IR/RNS mirrors

### TIER 3
- Market prices (Yahoo/Stooq)
- IBKR L1/L2
- Commodity prices
- Power prices
- Shipping/import data

### TIER 4 — JOIN EXISTING POW GARDENS
- Planning (from powuk)
- Procurement (from powuk)
- Jobs (from powuk)
- Apprenticeships (from powuk)
- Grid (from powuk)
- Energy (from powuk)
- Repair (from powuk)
- Materials (from powuk)
- Company formation (from powuk)

## POW Exposure Tags

```
POWER
├─ grid
├─ transformers
├─ switchgear
├─ generators
├─ substations
├─ transmission
├─ distribution
└─ power electronics

ENERGY
├─ gas
├─ nuclear
├─ solar
├─ battery
├─ diesel
└─ energy services

COMPUTE
├─ datacentres
├─ cooling
├─ networking
├─ servers
├─ semiconductors
└─ electrical infrastructure

MATERIALS
├─ copper
├─ aluminium
├─ steel
├─ cement
├─ aggregates
├─ rare earths
└─ specialty chemicals

MINING
├─ exploration
├─ extraction
├─ equipment
├─ processing
└─ mining services

PHYSICAL TECH
├─ robotics
├─ electronics
├─ industrial automation
├─ repair
├─ machine tools
└─ sensors

LABOUR
├─ electricians
├─ HVAC
├─ welders
├─ engineering
└─ construction
```

## Core Datasets

### insider_transactions
```
issuer_id, ticker, lei, isin, person_id, person_name, role,
relationship, transaction_type, transaction_class, price, quantity,
gross_value, currency, transaction_date, announcement_date,
venue, source_url, source_hash
```

Transaction classes:
- OPEN_MARKET_PURCHASE (conviction)
- OPEN_MARKET_SALE
- OPTION_EXERCISE
- RSU_VESTING
- SHARE_AWARD
- DIVIDEND_REINVESTMENT
- TAX_SALE
- SCRIP
- TRANSFER

### psc_events
```
company_number, person_id, entity_name, ownership_type,
ownership_band_before, ownership_band_after, control_before,
control_after, first_seen, last_seen, event_date, source_hash
```

### corporate_events
```
company_number, filing_type, event_type, description,
effective_date, filing_date, source_url, source_hash
```

Filing types → events:
- SH01 → share_issuance
- PSC01 → new_controller
- PSC07 → controller_ceased
- AP01 → director_appointed
- TM01 → director_departed
- MR01 → new_charge
- CS01 → ownership_snapshot
- AA → accounts_filed

### major_shareholder_movements (TR-1)
```
issuer, shareholder, ultimate_controller,
previous_voting_rights_pct, new_voting_rights_pct,
shares, financial_instruments, threshold_crossed,
date_crossed, date_notified
```

### takeover_panel_disclosures
```
offer_id, target, bidder, shareholder, action,
securities, price, date, form_type
```

## Derived Measurements

### pow_company_state_daily
```
date, entity_id, company_number, ticker, isin, lei
pow_domains[], bottlenecks[], geographies[]
top_holders, psc_state, institutional_concentration
ownership_delta_7d, ownership_delta_30d
insider_buy_value_7d, insider_buy_value_90d
conviction_buy_count, net_conviction_value
director_join_count, director_leave_count
share_issuance, new_charges, charge_value
revenue, inventory, cash, debt, employees
constraint_score, demand_score
price, market_cap, volume, spread
capital_response_score, insider_alignment_score
```

### POW Capital Response Index
```
CR_i,t = w1*I + w2*O + w3*E + w4*D + w5*C + w6*H

I = insider capital
O = ownership accumulation
E = equity issuance/investment
D = debt/charges
C = capex/fixed-asset response
H = hiring/director/company formation

Opportunity Gap = Constraint Growth - Capital Response
```

## GitHub References

- `Global-Witness/uk-companies-house-parsers-public` — CH .dat parsers
- `openownership/register-ingester-psc` — PSC bulk ingester
- `aicayzer/companies-house-mcp` — CH MCP server
- `RegistrumUK/companies-house-api-python-starter` — CH API starter
- `dacheah/uk-accounts-pipeline` — iXBRL → financials

## Key Insight

The moat is not the data. The moat is:
1. Continuous collection (daily PSC snapshots, every PDMR, every filing)
2. Entity resolution (linking people across companies)
3. Proprietary transformations (conviction scoring, capital response)
4. Retained historical state (Things time turns into a moat)

What did the physical economy look like?
What constraint was emerging?
Who knew?
Who moved capital?
Where did they move it?
How long before capacity responded?
What happened to the relevant securities?

---

## Implementation Status

### ✅ DONE
- [x] Cloned all 5 reference repos to `reference/`
- [x] Built bulk CH parsers (appointments + disqualifications) from Global-Witness pattern
- [x] Updated entity resolver with person_number, DOB, corporate_indicator fields
- [x] Built Finnhub UK insider transactions collector
- [x] Built Tracefour PDMR collector (UK structured data)
- [x] Built Companies House PSC snapshot collector
- [x] Built filing events classifier (SH01→issuance, AP01→director, etc)
- [x] Built insider conviction scorer (score 0-1, level LOW→VERY_HIGH)
- [x] Built entity resolver (person→companies graph)
- [x] Implemented self-registering tool pattern from companies-house-mcp
- [x] Implemented server-guided Retry-After from RegistrumUK starter
- [x] Added etag-based dedup concept from OpenOwnership ingester
- [x] Built Yahoo Finance price collector (24/25 tickers)
- [x] Built FCA short interest collector (421 positions)
- [x] Built Investegate RNS announcement collector
- [x] Built Companies House REST API collector

### 🔄 IN PROGRESS
- [ ] iXBRL parser from uk-accounts-pipeline (reference cloned, not yet implemented)
- [ ] pow_company_state_daily schema
- [ ] Wire up powuk physical constraint data
- [ ] Takeover Panel disclosures collector
- [ ] FCA TR-1 major shareholder notifications

### ⏳ PENDING
- [ ] Request CH bulk products (216, 199, 201, 197)
- [ ] Build director network analysis
- [ ] Build capital response index
- [ ] Build opportunity gap measurement

### Reference Repos (cloned)
```
reference/
├── uk-companies-house-parsers-public/  # CH .dat fixed-width parsers
├── register-ingester-psc/              # PSC bulk ingester (Ruby)
├── companies-house-mcp/                # CH MCP server (TypeScript)
├── companies-house-api-python-starter/ # CH API patterns (Python)
└── uk-accounts-pipeline/               # iXBRL → financials (Python)
```
