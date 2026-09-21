"""Entity registry — persistent, verified mappings for the 25 universe names.

For checkpoint 1, these are hard-coded. Never resolve via fuzzy API search.
The registry becomes the source of truth for entity identity.

Fields:
- ticker: TIDM
- company_number: Companies House number
- isin: ISIN
- lei: LEI (empty if not assigned)

Status: DEAD
- Never imported by any module.
- Duplicates identical data already in powstock/universe.py (UNIVERSE list with
  company_number, isin, lei fields). universe.py is the single source of truth.
- To revive: only if entity data needs to diverge from universe.py (e.g. historical
  mappings that change over time).
"""
- company_name: canonical name
- verified: True if manually verified
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class EntityMapping:
    ticker: str
    company_number: str
    isin: str
    lei: str
    company_name: str
    verified: bool = True


ENTITY_REGISTRY: dict[str, EntityMapping] = {
    "NG.": EntityMapping("NG.", "04031152", "GB00BDR96V06", "EVRYXRUZ5G1S3AJSQO86", "National Grid PLC"),
    "SSE": EntityMapping("SSE", "SC090326", "GB0B09SN5P82", "LR662YX57F2K6HVXKB82", "SSE PLC"),
    "DRX": EntityMapping("DRX", "02951435", "GB00B1VQCD93", "213800WSAIZLTXW86764", "Drax Group PLC"),
    "CNA": EntityMapping("CNA", "03033654", "GB00B033F229", "E26EDGU13G5RVVH29E85", "Centrica PLC"),
    "CCC": EntityMapping("CCC", "02149434", "GB00BW4GP286", "2138007P43MDC7V6K782", "Computacenter PLC"),
    "CORD": EntityMapping("CORD", "SC641412", "GB00BYYMV480", "21380067G88AH3E5K435", "Cordiant Digital Infrastructure LTD"),
    "BBOX": EntityMapping("BBOX", "09521476", "GB00BG394740", "213800LO697MN9T1O654", "Tritax Big Box REIT PLC"),
    "SGRO": EntityMapping("SGRO", "00825524", "GB00B18KWC48", "213800D328WH1D6SDP55", "SEGRO PLC"),
    "RPI": EntityMapping("RPI", "09564201", "GB001334C690", "213800N1I6DYB3XEGY09", "Raspberry Pi Holdings PLC"),
    "CNC": EntityMapping("CNC", "01320913", "GB0003541267", "2138004VQAU8S6T7B258", "Concurrent Technologies PLC"),
    "IQE": EntityMapping("IQE", "03355332", "GB00B49G3K07", "213800QBP9RH81BWDK82", "IQE PLC"),
    "XPP": EntityMapping("XPP", "03155213", "GB0030204202", "2138004FY22UK3C3A571", "XP Power LTD"),
    "VLX": EntityMapping("VLX", "02835475", "GB0009291894", "2138003T1FY2CT10X305", "Volex PLC"),
    "TTG": EntityMapping("TTG", "01635264", "GB0007601437", "2138008V4JN0TYYXH387", "TT Electronics PLC"),
    "DSCV": EntityMapping("DSCV", "00798603", "GB0001663347", "2138007KGOXIY2WCXP69", "discoverIE Group PLC"),
    "SOLI": EntityMapping("SOLI", "02227104", "GB0008353460", "213800MHX05206X8FH60", "Solid State PLC"),
    "PRE": EntityMapping("PRE", "04143993", "GB00BLM49Y29", "213800VFBO125JTVP495", "Pensana PLC"),
    "TUN": EntityMapping("TUN", "09990529", "GB00BTRJXV10", "2138003VQAU8S6T7B258", "Tungsten West PLC"),
    "ALL": EntityMapping("ALL", "07587700", "GH000000004", "", "Atlantic Lithium LTD"),
    "SML": EntityMapping("SML", "05102478", "GB00B4Y6V341", "2138007KGOXIY2WCXP69", "Strategic Minerals PLC"),
    "HE1": EntityMapping("HE1", "10817320", "GB00BF3K4N84", "", "Helium One Global LTD"),
    "RHL": EntityMapping("RHL", "13727534", "GB00BMQX7J67", "", "Rift Helium PLC"),
    "CBTC": EntityMapping("CBTC", "", "CH1198828594", "", "21Shares Bitcoin ETP", verified=False),
    "IB1T": EntityMapping("IB1T", "", "IE00BLD4ZL17", "", "iShares Bitcoin ETP", verified=False),
    "BOLD": EntityMapping("BOLD", "", "CH1198828586", "", "21Shares Bitcoin Gold ETP", verified=False),
}


def get_entity(ticker: str) -> EntityMapping | None:
    """Get verified entity mapping for a ticker."""
    return ENTITY_REGISTRY.get(ticker)


def get_company_number(ticker: str) -> str:
    """Get Companies House number for a ticker."""
    entity = ENTITY_REGISTRY.get(ticker)
    return entity.company_number if entity else ""


def get_isin(ticker: str) -> str:
    """Get ISIN for a ticker."""
    entity = ENTITY_REGISTRY.get(ticker)
    return entity.isin if entity else ""


def verify_entity(ticker: str, company_number: str = "", isin: str = "", lei: str = "") -> bool:
    """Manually verify/override an entity mapping. Returns True if updated."""
    entity = ENTITY_REGISTRY.get(ticker)
    if not entity:
        return False
    if company_number:
        entity.company_number = company_number
    if isin:
        entity.isin = isin
    if lei:
        entity.lei = lei
    entity.verified = True
    return True
