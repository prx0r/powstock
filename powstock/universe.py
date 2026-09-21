"""POW UK Universe — 25 securities sensing physical constraints.

company_number, isin, and lei are hard-coded (not guessed via fuzzy search).
These are verified mappings. Never resolve these via API search.
"""

from dataclasses import dataclass, field


@dataclass
class Security:
    ticker: str
    company: str
    exchange: str  # LSE, AIM, SETSqx
    market_cap: str  # description, not number
    company_number: str = ""  # Companies House number (hard-coded)
    isin: str = ""  # ISIN (hard-coded)
    lei: str = ""  # LEI (hard-coded)
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
             company_number="04031152",
             isin="GB00BDR96V06",
             lei="EVRYXRUZ5G1S3AJSQO86",
             pow_layers=["grid_transmission", "power_generation"],
             constraints=["grid_capacity", "connection_queue"]),
    Security("SSE", "SSE", "LSE", "Large",
             company_number="SC090326",
             isin="GB0B09SN5P82",
             lei="LR662YX57F2K6HVXKB82",
             pow_layers=["grid_networks", "power_generation"],
             constraints=["grid_capacity", "renewable_integration"]),
    Security("DRX", "Drax", "LSE", "Mid",
             company_number="02951435",
             isin="GB00B1VQCD93",
             lei="213800WSAIZLTXW86764",
             pow_layers=["dispatchable_power", "storage"],
             constraints=["electricity_dispatch", "biomass_supply"]),
    Security("CNA", "Centrica", "LSE", "Mid",
             company_number="03033654",
             isin="GB00B033F229",
             lei="E26EDGU13G5RVVH29E85",
             pow_layers=["energy_system", "gas_storage"],
             constraints=["energy_balance", "gas_supply"]),

    # Compute Infrastructure
    Security("CCC", "Computacenter", "LSE", "FTSE 100",
             company_number="02149434",
             isin="GB00BW4GP286",
             lei="2138007P43MDC7V6K782",
             pow_layers=["compute_deployment", "datacentre_infrastructure"],
             constraints=["enterprise_compute"], dataset="liquid"),
    Security("CORD", "Cordiant Digital Infrastructure", "LSE", "Small",
             company_number="SC641412",
             isin="GB00BYYMV480",
             lei="21380067G88AH3E5K435",
             pow_layers=["digital_infrastructure"],
             constraints=["datacentre_capacity"], dataset="liquid"),
    Security("BBOX", "Tritax Big Box", "LSE", "Mid",
             company_number="09521476",
             isin="GB00BG394740",
             lei="213800LO697MN9T1O654",
             pow_layers=["powered_land", "datacentre_development"],
             constraints=["land_power_connection"], dataset="liquid"),
    Security("SGRO", "SEGRO", "LSE", "Large",
             company_number="00825524",
             isin="GB00B18KWC48",
             lei="213800D328WH1D6SDP55",
             pow_layers=["industrial_real_estate"],
             constraints=["logistics_capacity"]),

    # Compute Hardware
    Security("RPI", "Raspberry Pi", "LSE", "FTSE 250",
             company_number="09564201",
             isin="GB001334C690",
             lei="213800N1I6DYB3XEGY09",
             pow_layers=["edge_compute", "compute_hardware"],
             constraints=["compute_demand"], dataset="liquid"),
    Security("CNC", "Concurrent Technologies", "LSE", "~226m SETSqx",
             company_number="01320913",
             isin="GB0003541267",
             lei="2138004VQAU8S6T7B258",
             pow_layers=["embedded_compute"],
             constraints=["embedded_systems"], dataset="constraint"),
    Security("IQE", "IQE", "AIM", "AIM",
             company_number="03355332",
             isin="GB00B49G3K07",
             lei="213800QBP9RH81BWDK82",
             pow_layers=["semiconductor_materials"],
             constraints=["compound_semiconductor_supply"], dataset="liquid"),
    Security("XPP", "XP Power", "LSE", "Mid",
             company_number="03155213",
             isin="GB0030204202",
             lei="2138004FY22UK3C3A571",
             pow_layers=["power_electronics"],
             constraints=["power_conversion"], dataset="liquid"),
    Security("VLX", "Volex", "LSE", ">1bn",
             company_number="02835475",
             isin="GB0009291894",
             lei="2138003T1FY2CT10X305",
             pow_layers=["power_connectivity"],
             constraints=["power_data_interconnect"], dataset="liquid"),
    Security("TTG", "TT Electronics", "LSE", "Small",
             company_number="01635264",
             isin="GB0007601437",
             lei="2138008V4JN0TYYXH387",
             pow_layers=["electronic_components"],
             constraints=["component_supply"]),
    Security("DSCV", "discoverIE", "LSE", "Small",
             company_number="00798603",
             isin="GB0001663347",
             lei="2138007KGOXIY2WCXP69",
             pow_layers=["specialist_electronics"],
             constraints=["specialist_component_supply"]),
    Security("SOLI", "Solid State", "AIM", "~109m AIM",
             company_number="02227104",
             isin="GB0008353460",
             lei="213800MHX05206X8FH60",
             pow_layers=["rugged_computing"],
             constraints=["rugged_systems"], dataset="constraint"),

    # Critical Materials
    Security("PRE", "Pensana", "Main", "~235m Main",
             company_number="04143993",
             isin="GB00BLM49Y29",
             lei="213800VFBO125JTVP495",
             pow_layers=["rare_earths"],
             constraints=["rare_earth_supply", "ndpr_pricing"], dataset="constraint"),
    Security("TUN", "Tungsten West", "AIM", "~687m AIM",
             company_number="09990529",
             isin="GB00BTRJXV10",
             lei="2138003VQAU8S6T7B258",
             pow_layers=["tungsten"],
             constraints=["tungsten_supply", "hemerdon_restart"], dataset="constraint"),
    Security("ALL", "Atlantic Lithium", "LSE", "Small",
             company_number="07587700",
             isin="GH000000004",
             lei="",
             pow_layers=["lithium"],
             constraints=["lithium_supply"], dataset="constraint"),
    Security("SML", "Strategic Minerals", "AIM", "AIM/SETSqx",
             company_number="05102478",
             isin="GB00B4Y6V341",
             lei="2138007KGOXIY2WCXP69",
             pow_layers=["strategic_minerals"],
             constraints=["mineral_supply"], dataset="constraint"),
    Security("HE1", "Helium One", "AIM", "~38m AIM",
             company_number="10817320",
             isin="GB00BF3K4N84",
             lei="",
             pow_layers=["helium"],
             constraints=["helium_supply", "semiconductor_cooling"], dataset="constraint"),
    Security("RHL", "Rift Helium", "AIM", "AIM",
             company_number="13727534",
             isin="GB00BMQX7J67",
             lei="",
             pow_layers=["helium"],
             constraints=["helium_supply"], dataset="constraint"),

    # Crypto / Hard-Asset Instrumentation (Control Group)
    Security("CBTC", "21Shares Bitcoin ETP", "LSE", "ETP",
             company_number="",
             isin="CH1198828594",
             lei="",
             pow_layers=["crypto_exposure"],
             constraints=["btc_price"], dataset="liquid"),
    Security("IB1T", "iShares Bitcoin ETP", "LSE", "ETP",
             company_number="",
             isin="IE00BLD4ZL17",
             lei="",
             pow_layers=["crypto_exposure"],
             constraints=["btc_price"], dataset="liquid"),
    Security("BOLD", "21Shares Bitcoin Gold", "LSE", "ETP",
             company_number="",
             isin="CH1198828586",
             lei="",
             pow_layers=["hard_asset_hybrid"],
             constraints=["btc_gold_price"], dataset="liquid"),
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

# Stooq symbol mapping (.uk suffix for LSE)
STOOQ_SYMBOLS: dict[str, str] = {
    "NG.": "ng.uk",
    "SSE": "sse.uk",
    "DRX": "drx.uk",
    "CNA": "cna.uk",
    "CCC": "ccc.uk",
    "CORD": "cord.uk",
    "BBOX": "bbox.uk",
    "SGRO": "sgro.uk",
    "RPI": "rpi.uk",
    "CNC": "cnc.uk",
    "IQE": "iqe.uk",
    "XPP": "xpp.uk",
    "VLX": "vlx.uk",
    "TTG": "ttg.uk",
    "DSCV": "dscv.uk",
    "SOLI": "soli.uk",
    "PRE": "pre.uk",
    "TUN": "tun.uk",
    "ALL": "all.uk",
    "SML": "sml.uk",
    "HE1": "he1.uk",
    "RHL": "rhl.uk",
    "CBTC": "cbtc.uk",
    "IB1T": "ib1t.uk",
    "BOLD": "bold.uk",
}
