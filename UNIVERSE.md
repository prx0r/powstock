# The POW UK Universe

25 securities. Every node in the physical compute supply chain has a UK-listed security you can observe.

## Grid / Power

| Ticker | Company | Market Cap | Why |
|--------|---------|-----------|-----|
| NG. | National Grid | Large | Transmission/grid constraint proxy |
| SSE | SSE | Large | Grid networks + generation |
| DRX | Drax | Mid | Generation, dispatchable power, storage exposure |
| CNA | Centrica | Mid | UK energy system, generation/storage/gas |

## Compute Infrastructure

| Ticker | Company | Market Cap | Why |
|--------|---------|-----------|-----|
| CCC | Computacenter | FTSE 100 | Enterprise servers, datacentre/AI infrastructure deployment |
| CORD | Cordiant Digital Infrastructure | Small | Digital infrastructure assets |
| BBOX | Tritax Big Box | Mid | "Power first" strategy — 250MW data-centre opportunities, 1GW pipeline |
| SGRO | SEGRO | Large | Industrial/logistics real estate with power/data-centre read-through |

## Compute Hardware

| Ticker | Company | Market Cap | Why |
|--------|---------|-----------|-----|
| RPI | Raspberry Pi | FTSE 250 | Compute hardware / edge compute |
| CNC | Concurrent Technologies | ~£226m SETSqx | Embedded compute boards/systems |
| IQE | IQE | AIM | Compound semiconductor wafers |
| XPP | XP Power | Mid | Power conversion for electronics/semiconductor equipment |
| VLX | Volex | >£1bn | Power and high-speed connectivity/cabling |
| TTG | TT Electronics | Small | Electronic components/power/sensors |
| DSCV | discoverIE | Small | Specialist electronic components |
| SOLI | Solid State | ~£109m AIM | Rugged computing/electronics |

## Critical Materials

| Ticker | Company | Market Cap | Why |
|--------|---------|-----------|-----|
| PRE | Pensana | ~£235m Main | Rare earths |
| TUN | Tungsten West | ~£687m AIM | Tungsten — £71m UK National Wealth Fund investment, Hemerdon restart |
| ALL | Atlantic Lithium | Small | Lithium |
| SML | Strategic Minerals | AIM/SETSqx | Strategic/mineral resource exposure |
| HE1 | Helium One | ~£38m AIM | Helium — semiconductor/scientific/cooling |
| RHL | Rift Helium | AIM (May 2026) | Helium — Tanzania Rukwa Basin |

## Crypto / Hard-Asset Instrumentation (Control Group)

| Ticker | Company | Type | Why |
|--------|---------|------|-----|
| CBTC | 21Shares Bitcoin ETP | ETP | UK-listed BTC price/liquidity |
| ABTC | 21Shares Bitcoin ETP | ETP | UK-listed BTC price/liquidity |
| IB1T | iShares Bitcoin ETP | ETP | Physically backed BTC (Oct 2025) |
| BOLD | 21Shares Bitcoin Gold | ETP | BTC/gold hard-asset hybrid |
| ETHC | 21Shares Ethereum ETP | ETP | Crypto capital-flow comparator |
| AETH | 21Shares Ethereum ETP | ETP | Crypto capital-flow comparator |

## Schema Tagging

Every security gets tagged:

```json
{
  "ticker": "XPP",
  "company": "XP Power",
  "exchange": "LSE",
  "pow_layers": [
    "power_electronics",
    "semiconductor_capex",
    "compute_infrastructure"
  ],
  "constraints": [
    "power_conversion",
    "component_supply"
  ],
  "inputs": [],
  "outputs": ["power_supplies"],
  "upstream": [],
  "downstream": [
    "semiconductor_equipment",
    "datacentres",
    "industrial_compute"
  ]
}
```
