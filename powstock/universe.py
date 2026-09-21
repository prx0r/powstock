"""POW UK Universe — 25 securities sensing physical constraints."""

from dataclasses import dataclass, field


@dataclass
class Security:
    ticker: str
    company: str
    exchange: str  # LSE, AIM, SETSqx
    market_cap: str  # description, not number
    pow_layers: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)
    dataset: str = "liquid"  # liquid or constraint


UNIVERSE: list[Security] = [
    # Grid / Power
    Security("NG.", "National Grid", "LSE", "Large",
             ["grid_transmission", "power_generation"],
             ["grid_capacity", "connection_queue"]),
    Security("SSE", "SSE", "LSE", "Large",
             ["grid_networks", "power_generation"],
             ["grid_capacity", "renewable_integration"]),
    Security("DRX", "Drax", "LSE", "Mid",
             ["dispatchable_power", "storage"],
             ["electricity_dispatch", "biomass_supply"]),
    Security("CNA", "Centrica", "LSE", "Mid",
             ["energy_system", "gas_storage"],
             ["energy_balance", "gas_supply"]),

    # Compute Infrastructure
    Security("CCC", "Computacenter", "LSE", "FTSE 100",
             ["compute_deployment", "datacentre_infrastructure"],
             ["enterprise_compute"], dataset="liquid"),
    Security("CORD", "Cordiant Digital Infrastructure", "LSE", "Small",
             ["digital_infrastructure"],
             ["datacentre_capacity"], dataset="liquid"),
    Security("BBOX", "Tritax Big Box", "LSE", "Mid",
             ["powered_land", "datacentre_development"],
             ["land_power_connection"], dataset="liquid"),
    Security("SGRO", "SEGRO", "LSE", "Large",
             ["industrial_real_estate"],
             ["logistics_capacity"]),

    # Compute Hardware
    Security("RPI", "Raspberry Pi", "LSE", "FTSE 250",
             ["edge_compute", "compute_hardware"],
             ["compute_demand"], dataset="liquid"),
    Security("CNC", "Concurrent Technologies", "LSE", "~226m SETSqx",
             ["embedded_compute"],
             ["embedded_systems"], dataset="constraint"),
    Security("IQE", "IQE", "AIM", "AIM",
             ["semiconductor_materials"],
             ["compound_semiconductor_supply"], dataset="liquid"),
    Security("XPP", "XP Power", "LSE", "Mid",
             ["power_electronics"],
             ["power_conversion"], dataset="liquid"),
    Security("VLX", "Volex", "LSE", ">1bn",
             ["power_connectivity"],
             ["power_data_interconnect"], dataset="liquid"),
    Security("TTG", "TT Electronics", "LSE", "Small",
             ["electronic_components"],
             ["component_supply"]),
    Security("DSCV", "discoverIE", "LSE", "Small",
             ["specialist_electronics"],
             ["specialist_component_supply"]),
    Security("SOLI", "Solid State", "AIM", "~109m AIM",
             ["rugged_computing"],
             ["rugged_systems"], dataset="constraint"),

    # Critical Materials
    Security("PRE", "Pensana", "Main", "~235m Main",
             ["rare_earths"],
             ["rare_earth_supply", "ndpr_pricing"], dataset="constraint"),
    Security("TUN", "Tungsten West", "AIM", "~687m AIM",
             ["tungsten"],
             ["tungsten_supply", "hemerdon_restart"], dataset="constraint"),
    Security("ALL", "Atlantic Lithium", "LSE", "Small",
             ["lithium"],
             ["lithium_supply"], dataset="constraint"),
    Security("SML", "Strategic Minerals", "AIM", "AIM/SETSqx",
             ["strategic_minerals"],
             ["mineral_supply"], dataset="constraint"),
    Security("HE1", "Helium One", "AIM", "~38m AIM",
             ["helium"],
             ["helium_supply", "semiconductor_cooling"], dataset="constraint"),
    Security("RHL", "Rift Helium", "AIM", "AIM",
             ["helium"],
             ["helium_supply"], dataset="constraint"),

    # Crypto / Hard-Asset Instrumentation (Control Group)
    Security("CBTC", "21Shares Bitcoin ETP", "LSE", "ETP",
             ["crypto_exposure"],
             ["btc_price"], dataset="liquid"),
    Security("IB1T", "iShares Bitcoin ETP", "LSE", "ETP",
             ["crypto_exposure"],
             ["btc_price"], dataset="liquid"),
    Security("BOLD", "21Shares Bitcoin Gold", "LSE", "ETP",
             ["hard_asset_hybrid"],
             ["btc_gold_price"], dataset="liquid"),
]

# Ticker lookup
BY_TICKER: dict[str, Security] = {s.ticker: s for s in UNIVERSE}

# Dataset splits
LIQUID = [s for s in UNIVERSE if s.dataset == "liquid"]
CONSTRAINT = [s for s in UNIVERSE if s.dataset == "constraint"]

# Yahoo Finance symbol mapping (.L suffix for LSE)
YAHOO_SYMBOLS: dict[str, str] = {
    "NG.": "NG.L",
    "SSE": "SSE.L",
    "DRX": "DRX.L",
    "CNA": "CNA.L",
    "CCC": "CCC.L",
    "CORD": "CORD.L",
    "BBOX": "BBOX.L",
    "SGRO": "SGRO.L",
    "RPI": "RPI.L",
    "CNC": "CNC.L",
    "IQE": "IQE.L",
    "XPP": "XPP.L",
    "VLX": "VLX.L",
    "TTG": "TTG.L",
    "DSCV": "DSCV.L",
    "SOLI": "SOLI.L",
    "PRE": "PRE.L",
    "TUN": "TUN.L",
    "ALL": "ALL.L",
    "SML": "SML.L",
    "HE1": "HE1.L",
    "RHL": "RHL.L",
    "CBTC": "CBTC.L",
    "IB1T": "IB1T.L",
    "BOLD": "BOLD.L",
}

# Backward compat alias
STOOQ_SYMBOLS = YAHOO_SYMBOLS
