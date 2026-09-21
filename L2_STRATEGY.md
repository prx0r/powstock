# L2 Strategy

Split UK L2 collection into two datasets. Thinner markets are better sensors.

## POW_UK_LIQUID

Continuous, reasonably deep books. Baseline for what a healthy liquid market looks like.

| Ticker | Company | Market Cap | Why |
|--------|---------|-----------|-----|
| NG. | National Grid | Large | Grid capacity sensor |
| SSE | SSE | Large | Grid + generation sensor |
| DRX | Drax | Mid | Dispatchable power sensor |
| CNA | Centrica | Mid | Energy system sensor |
| CCC | Computacenter | FTSE 100 | Compute deployment sensor |
| RPI | Raspberry Pi | FTSE 250 | Edge compute sensor |
| XPP | XP Power | Mid | Power conversion sensor |
| VLX | Volex | >£1bn | Power + data interconnect sensor |
| IQE | IQE | AIM | Semiconductor material sensor |
| BBOX | Tritax Big Box | Mid | Powered land sensor |
| CORD | Cordiant Digital | Small | Digital infrastructure sensor |

**Purpose**: Establish baseline market microstructure — normal spreads, normal depth, normal quote behavior. Everything else is measured relative to this.

## POW_UK_CONSTRAINT

Thinner markets. Experimental goldmine. More visible information in:

- spread
- depth
- market maker quotes
- quote withdrawal
- replenishment speed
- auction activity
- imbalance
- trade-through
- size clustering
- liquidity gaps

| Ticker | Company | Market Cap | Why |
|--------|---------|-----------|-----|
| CNC | Concurrent Technologies | ~£226m SETSqx | Embedded compute |
| SOLI | Solid State | ~£109m AIM | Rugged computing |
| PRE | Pensana | ~£235m Main | Rare earths |
| TUN | Tungsten West | ~£687m AIM | Tungsten |
| ALL | Atlantic Lithium | Small | Lithium |
| SML | Strategic Minerals | AIM/SETSqx | Strategic minerals |
| HE1 | Helium One | ~£38m AIM | Helium |
| RHL | Rift Helium | AIM | Helium |

**Purpose**: These are where the physical scarcity → equity repricing signal lives. The order book on Helium One (£38m) contains more information about helium supply constraint repricing than anything on National Grid.

## What to Record per Snapshot

```python
@dataclass
class L2Snapshot:
    ticker: str
    timestamp: datetime
    bid_price: float
    ask_price: float
    spread_bps: float
    bid_depth: float        # total depth within X bps
    ask_depth: float
    bid_levels: int         # number of distinct price levels
    ask_levels: int
    top_bid_size: float
    top_ask_size: float
    quote_age_seconds: float  # time since last quote update
    last_trade_price: float
    last_trade_size: float
    last_trade_side: str      # BUY/SELL
    imbalance: float          # (bid_depth - ask_depth) / (bid_depth + ask_depth)
    venue: str                # LSE, AIM, SETSqx
```

## Metrics to Compute

### Per-Security (daily)
- Average spread (bps)
- Average depth (GBP notional within 50bps)
- Quote update frequency
- Imbalance mean + volatility
- Trade size distribution
- Quote-to-trade ratio

### Cross-Sectional (daily)
- Z-scored spread vs universe median
- Z-scored depth vs universe median
- Z-scored imbalance vs universe median
- Constraint/liquid spread ratio

### Signal Construction
- `l2_information_v1` = cross-sectional z of (spread × |imbalance|) — where is information concentrated?
- `l2_liquidity_v1` = cross-sectional z of depth — where is capital deployed?
- `l2_withdrawal_v1` = count of quote withdrawals > threshold — where are market makers stepping back?

## Why This Matters

The £7/month IBKR feed on a £38m AIM stock gives you:
- Real-time order book state
- Quote更新频率
- Market maker behavior
- Liquidity gaps

This is physical scarcity being repriced in real-time through market microstructure. No other data source gives you this at this resolution for UK small-caps.

The liquid dataset tells you what "normal" looks like. The constraint dataset tells you where the interesting things are happening.
