"""FCA PDMR insider dealing collector.

Fetches Director/PDMR announcements from Investegate RNS feed.
Parses the structured UK MAR notification format to extract:
- Director name and position
- Transaction type (purchase, sale, option exercise, etc.)
- Price, volume, total value
- Date and venue
- ISIN of instrument
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

INVESTEGATE_URL = "https://www.investegate.co.uk/Index.aspx"


@dataclass
class PDMRDeal:
    ticker: str
    company_name: str
    director_name: str
    position: str
    transaction_type: str
    price: float
    shares: int
    total_value: float
    currency: str
    isin: str
    trade_date: str
    venue: str
    notification_url: str
    lei: str
    source: str = "investegate_rns"
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    group_shares: int | None = None  # total for multi-director notifications
    group_value: float | None = None  # total for multi-director notifications
    parse_status: str = "complete"  # complete or partial


def _clean_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_field(text: str, patterns: list[str]) -> str:
    """Try multiple regex patterns to extract a field value."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def _parse_pdmr_notification(html: str, ticker: str, company_name: str, url: str) -> list[PDMRDeal]:
    """Parse a UK MAR PDMR notification from Investegate HTML.
    
    Returns list of deals (a single notification can have multiple directors).
    """
    deals = []
    
    try:
        # PRIMARY: Use AI summary (Investegate extracts key info)
        summary_match = re.search(r'Summary by AI.*?Close X(.*?)Disclaimer', html, re.DOTALL)
        if summary_match:
            summary_text = _clean_html(summary_match.group(1))
            
            # Extract from summary using natural language patterns
            # Pattern: "Director Name, the Position, purchased/sold X shares at £Y each"
            director_match = re.search(
                r'(\w[\w\s\'-]+?),\s+(?:the\s+)?(?:Chief|Director|Executive|Non-Executive|Chairman|CEO|CFO|COO|CTO|General Counsel|Company Secretary|Managing Director|Head of[\w\s]+?|PDMR|a person)[^,]*,\s+(purchased|sold|acquired|disposed|exercised|granted|vested|reinvested)',
                summary_text, re.IGNORECASE
            )
            # Extract all director-role pairs from summary
            # Pattern: "Role, Name" (e.g. "Chief Executive Officer, Gary Guidry")
            director_pairs = re.findall(
                r'((?:President|Chief|Executive|Vice President|Non-Executive|Managing|Head of|PDMR)[^,]+),\s+(\w[\w\s\'-]+?)(?:,|\s+(?:and|acquired|purchased|sold|exercised))',
                summary_text, re.IGNORECASE
            )
            
            # Extract transaction action
            action_match = re.search(r'(purchased|sold|acquired|disposed|exercised|granted|vested|reinvested)', summary_text, re.IGNORECASE)
            action = action_match.group(1).lower() if action_match else ""
            
            if "purchas" in action or "acquir" in action:
                transaction_type = "Purchase"
            elif "sold" in action or "dispos" in action:
                transaction_type = "Sale"
            elif "exercis" in action:
                transaction_type = "Option Exercise"
            elif "grant" in action:
                transaction_type = "Option Grant"
            elif "vest" in action:
                transaction_type = "Vesting"
            elif "reinvest" in action:
                transaction_type = "Dividend Reinvestment"
            else:
                transaction_type = "Unknown"
            
            # Extract shares (total if multiple directors)
            shares_match = re.search(r'(?:total of\s+)?([\d,]+)\s+(?:common|ordinary)\s+shares', summary_text, re.IGNORECASE)
            total_shares = int(shares_match.group(1).replace(',', '')) if shares_match else 0
            
            # Extract price - try multiple patterns
            price_match = re.search(r'(?:USD|GBP|£|€|\$)\s*([\d,]+\.?\d*)', summary_text)
            if not price_match:
                price_match = re.search(r'at\s+(?:a\s+price\s+of\s+)?[£$€]?\s*([\d,]+\.?\d*)\s*(?:per\s+share|each)?', summary_text, re.IGNORECASE)
            price = 0.0
            if price_match:
                price = float(price_match.group(1).replace(',', ''))
                if 'pence' in summary_text.lower() and price > 100:
                    price = price / 100
            
            # Extract date
            date_match = re.search(r'on\s+(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', summary_text, re.IGNORECASE)
            if not date_match:
                date_match = re.search(r'(\w+\s+\d{1,2},?\s+\d{4})', summary_text, re.IGNORECASE)
            trade_date = date_match.group(1) if date_match else ""
            
            # Create a deal for each director found
            if director_pairs:
                # Do NOT divide total shares equally — that invents precision.
                # If individual allocation cannot be extracted, store NULL shares
                # and the total as group_shares. Unknown is valuable; fabricated
                # precision is poisonous.
                for role, name in director_pairs:
                    name = name.strip()
                    if len(name) > 3 and not name.isdigit():
                        deals.append(PDMRDeal(
                            ticker=ticker,
                            company_name=company_name,
                            director_name=name,
                            position=role.strip(),
                            transaction_type=transaction_type,
                            price=price,
                            shares=0,  # unknown per-director
                            total_value=0.0,  # unknown per-director
                            currency="USD" if "USD" in summary_text or "$" in summary_text else "GBP",
                            isin="",
                            trade_date=trade_date,
                            venue="Toronto Stock Exchange" if "Toronto" in summary_text else "London Stock Exchange",
                            notification_url=url,
                            lei="",
                            group_shares=total_shares if total_shares else None,
                            group_value=(price * total_shares) if price and total_shares else None,
                            parse_status="partial" if not total_shares else "complete",
                        ))
            elif total_shares > 0:
                # Single director or couldn't parse names
                director_match = re.search(
                    r'(\w[\w\s\'-]+?),\s+(?:the\s+)?(?:Chief|Director|Executive|Non-Executive|Chairman|CEO|CFO|COO|CTO|General Counsel|Company Secretary|Managing Director|Head of|PDMR|a person)[^,]*,\s+(purchased|sold|acquired|disposed|exercised|granted|vested|reinvested)',
                    summary_text, re.IGNORECASE
                )
                if director_match:
                    director_name = director_match.group(1).strip()
                    if 'announced that' in director_name:
                        director_name = director_name.split('announced that')[-1].strip()
                    
                    pos_match = re.search(r'the\s+(Chief\w+|Director\w*|Executive\w*|Non-Executive\w*|Chairman\w*|CEO|CFO|COO|CTO|General Counsel|Company Secretary|Managing Director)', summary_text, re.IGNORECASE)
                    position = pos_match.group(1) if pos_match else ""
                    
                    deals.append(PDMRDeal(
                        ticker=ticker,
                        company_name=company_name,
                        director_name=director_name,
                        position=position,
                        transaction_type=transaction_type,
                        price=price,
                        shares=total_shares,
                        total_value=price * total_shares,
                        currency="USD" if "USD" in summary_text or "$" in summary_text else "GBP",
                        isin="",
                        trade_date=trade_date,
                        venue="London Stock Exchange",
                        notification_url=url,
                        lei="",
                    ))
            
            # Also check for multiple directors mentioned
            # Pattern: "Name1 (Role1), Name2 (Role2), and Name3 (Role3)"
            multi_match = re.findall(r'(\w[\w\s\'-]+?)\s*\(([^)]+)\)', summary_text)
            for name, role in multi_match:
                name = name.strip()
                if len(name) > 3 and not name.startswith(('The', 'This', 'All')):
                    # This is another person mentioned - skip for now
                    pass
        
        # FALLBACK: Parse the full notification if AI summary didn't work
        if not deals:
            notif_start = -1
            for marker in ['NOTIFICATION AND PUBLIC DISCLOSURE', 'Notification and public disclosure',
                           'NOTIFICATION OF TRANSACTIONS', 'Notification of transactions']:
                notif_start = html.find(marker)
                if notif_start > 0:
                    break
            
            if notif_start > 0:
                notif_html = html[notif_start:notif_start + 5000]
                notif_text = _clean_html(notif_html)
                
                # Extract director name
                director_name = _extract_field(notif_text, [
                    r'a\)\s*Name\s+([A-Z][A-Z\s,.\'-]+?)(?:\s+2\s|\s+Reason|\s+b\))',
                    r'Name\s+([A-Z]{2,}[A-Z\s,.\'-]+?)(?:\s+2\s|\s+Reason)',
                ])
                
                # Extract price and volume
                price_match = re.search(r'£([\d,]+\.?\d*)', notif_text)
                vol_match = re.search(r'Volume\(s\)\s+([\d,]+)', notif_text)
                date_match = re.search(r'Date of.*?transaction\s+(\d{1,2}\s+\w+\s+\d{4})', notif_text, re.IGNORECASE)
                
                if director_name and vol_match:
                    price = float(price_match.group(1).replace(',', '')) if price_match else 0.0
                    shares = int(vol_match.group(1).replace(',', ''))
                    
                    # Determine transaction type from nature
                    nature_match = re.search(r'Nature of.*?transaction\s+(.+?)(?:\s+c\)|\s+d\))', notif_text)
                    nature = nature_match.group(1).lower() if nature_match else ""
                    
                    if "purchase" in nature or "acquisition" in nature:
                        transaction_type = "Purchase"
                    elif "sale" in nature or "disposal" in nature:
                        transaction_type = "Sale"
                    elif "dividend" in nature or "reinvestment" in nature:
                        transaction_type = "Dividend Reinvestment"
                    else:
                        transaction_type = "Unknown"
                    
                    deals.append(PDMRDeal(
                        ticker=ticker,
                        company_name=company_name,
                        director_name=director_name.title(),
                        position="",
                        transaction_type=transaction_type,
                        price=price,
                        shares=shares,
                        total_value=price * shares,
                        currency="GBP",
                        isin="",
                        trade_date=date_match.group(1) if date_match else "",
                        venue="London Stock Exchange",
                        notification_url=url,
                        lei="",
                    ))

    except Exception as e:
        log.warning("PDMR parse error for %s: %s", url, e)
    
    return deals


def fetch_pdmr_announcements(
    ticker: str | None = None,
    max_pages: int = 5,
) -> list[dict[str, Any]]:
    """Fetch PDMR/Director dealing announcements from Investegate.

    Args:
        ticker: Filter by specific TIDM. None = all recent.
        max_pages: Maximum pages to fetch.

    Returns:
        List of parsed PDMR deal dicts.
    """
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    all_deals = []
    raw_artifacts = []

    try:
        for page in range(1, max_pages + 1):
            params: dict[str, Any] = {"searchtype": "3"}
            if ticker:
                params["search"] = ticker
            if page > 1:
                params["page"] = str(page)

            resp = client.get(INVESTEGATE_URL, params=params)
            resp.raise_for_status()
            html = resp.text

            # Find announcement links with company/ticker context
            # The HTML structure is:
            # <td>Company Link</td>
            # <td><a class="announcement-link" href="...">Headline</a></td>
            
            # First find all table rows
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
            
            announcements = []
            for row in rows:
                # Check if this row has an announcement link
                link_match = re.search(
                    r'href="(https://www\.investegate\.co\.uk/announcement/rns/[^"]+)"',
                    row,
                )
                if not link_match:
                    continue
                    
                link = link_match.group(1)
                
                # Find headline
                headline_match = re.search(
                    r'class="announcement-link"[^>]*>([^<]+)</a>',
                    row,
                )
                if not headline_match:
                    continue
                    
                headline = headline_match.group(1).strip()
                
                # Only Director/PDMR announcements
                if "Director" not in headline and "PDMR" not in headline:
                    continue
                
                # Find company name and ticker in the same row
                # Pattern: "Company Name (TICKER)" or "Company Name (CDI) (TICKER)"
                company_match = re.search(
                    r'>([^<]+)\([A-Z0-9.]+\)\s*\(([A-Z0-9.]+)\)</a>',
                    row,
                )
                if company_match:
                    company_name = company_match.group(1).strip()
                    ann_ticker = company_match.group(2).strip()
                else:
                    company_match = re.search(
                        r'>([^<]+)\(([A-Z0-9.]+)\)</a>',
                        row,
                    )
                    if company_match:
                        company_name = company_match.group(1).strip()
                        ann_ticker = company_match.group(2).strip()
                    else:
                        continue
                
                announcements.append({
                    "url": link,
                    "ticker": ann_ticker,
                    "company": company_name,
                    "headline": headline,
                })

            # Fetch and parse each announcement
            for ann in announcements:
                if ticker and ann["ticker"].upper() != ticker.upper():
                    continue

                try:
                    resp = client.get(ann["url"])
                    resp.raise_for_status()
                    ann_html = resp.text

                    # Store raw HTML as artifact
                    raw_artifacts.append({
                        "source_url": ann["url"],
                        "content": resp.content,
                        "content_type": "text/html",
                        "ticker": ann["ticker"],
                    })

                    deals = _parse_pdmr_notification(ann_html, ann["ticker"], ann["company"], ann["url"])
                    for deal in deals:
                        all_deals.append({
                            "ticker": deal.ticker,
                            "company": deal.company_name,
                            "director": deal.director_name,
                            "position": deal.position,
                            "transaction_type": deal.transaction_type,
                            "price": deal.price,
                            "shares": deal.shares,
                            "total_value": deal.total_value,
                            "currency": deal.currency,
                            "isin": deal.isin,
                            "trade_date": deal.trade_date,
                            "venue": deal.venue,
                            "url": deal.notification_url,
                            "lei": deal.lei,
                        })

                    time.sleep(0.3)

                except Exception as e:
                    log.warning("PDMR fetch error %s: %s", ann["url"], e)

            time.sleep(0.5)

    finally:
        client.close()

    return all_deals, raw_artifacts


def fetch_ticker_insiders(ticker: str, max_pages: int = 3) -> list[dict[str, Any]]:
    """Fetch recent insider dealings for a specific ticker."""
    return fetch_pdmr_announcements(ticker=ticker, max_pages=max_pages)


def summarise_insider_activity(deals: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise insider activity for signal construction."""
    if not deals:
        return {"ticker": None, "total_deals": 0, "buys": 0, "sells": 0,
                "total_buy_value": 0, "total_sell_value": 0, "net_value": 0,
                "unique_directors": 0, "buy_sell_ratio": 0}

    buys = [d for d in deals if d["transaction_type"] == "Purchase"]
    sells = [d for d in deals if d["transaction_type"] == "Sale"]

    return {
        "ticker": deals[0]["ticker"],
        "total_deals": len(deals),
        "buys": len(buys),
        "sells": len(sells),
        "total_buy_value": sum(d["total_value"] for d in buys),
        "total_sell_value": sum(d["total_value"] for d in sells),
        "net_value": sum(d["total_value"] for d in buys) - sum(d["total_value"] for d in sells),
        "unique_directors": len(set(d["director"] for d in deals)),
        "buy_sell_ratio": len(buys) / len(sells) if sells else float("inf"),
    }
