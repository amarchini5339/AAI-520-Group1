import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, List, Dict

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"   # preferred
AUTOC_URL  = "https://autoc.finance.yahoo.com/autoc"                # fallback

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        # Some Yahoo endpoints 404/403 without a UA
        "User-Agent": "Mozilla/5.0 (compatible; ticker-lookup/1.0)",
        "Accept": "application/json,text/javascript,*/*;q=0.1",
    })
    retry = Retry(
        total=3, backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def yahoo_find_ticker(
    company_name: str,
    exchanges: Optional[List[str]] = None,   # e.g. ["NYSE", "NasdaqGS"]
    types: Optional[List[str]] = None,       # e.g. ["EQUITY", "ETF"]
    return_all: bool = False
) -> Optional[Dict]:
    """
    Find a ticker by company name using Yahoo Finance.
    Returns best dict match (default) or a list of matches if return_all=True.
    """
    s = _session()

    # --- Preferred endpoint ---
    try:
        r = s.get(SEARCH_URL, params={"q": company_name, "lang": "en-US", "region": "US"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        quotes = data.get("quotes", []) or []

        # Normalize + filter
        def norm(q):
            return {
                "symbol": q.get("symbol"),
                "name": q.get("shortname") or q.get("longname") or q.get("quoteType"),
                "exch": q.get("exchange"),
                "exchDisp": q.get("exchDisp") or q.get("fullExchangeName"),
                "type": q.get("quoteType"),
                "typeDisp": q.get("quoteType"),
            }

        candidates = [norm(q) for q in quotes if q.get("symbol")]
        if types:
            tset = {t.upper() for t in types}
            candidates = [c for c in candidates if (c["type"] or "").upper() in tset]
        if exchanges:
            eset = set(exchanges)
            candidates = [c for c in candidates if c["exchDisp"] in eset or c["exch"] in eset]

        if candidates:
            return candidates if return_all else candidates[0]
    except requests.HTTPError:
        pass  # fall through to fallback

    # --- Fallback endpoint (older autocomplete) ---
    try:
        r = s.get(AUTOC_URL, params={"query": company_name, "region": 1, "lang": "en"}, timeout=10)
        r.raise_for_status()
        rs = (r.json() or {}).get("ResultSet", {}).get("Result", []) or []
        candidates = [{
            "symbol": x.get("symbol"),
            "name": x.get("name"),
            "exch": x.get("exch"),
            "exchDisp": x.get("exchDisp"),
            "type": x.get("type"),
            "typeDisp": x.get("typeDisp"),
        } for x in rs if x.get("symbol")]

        if types:
            tset = {t.upper() for t in types}
            candidates = [c for c in candidates if (c["typeDisp"] or "").upper() in tset or (c["type"] or "").upper() in tset]
        if exchanges:
            eset = set(exchanges)
            candidates = [c for c in candidates if c["exchDisp"] in eset or c["exch"] in eset]

        if not candidates:
            return [] if return_all else None
        return candidates if return_all else candidates[0]
    except requests.HTTPError as e:
        # Surface the original 404/403 with a friendly hint
        raise RuntimeError(
            f"Yahoo lookup failed ({e.response.status_code}). "
            "Try the newer search API, ensure a real User-Agent, or check your network/proxy."
        ) from e

# --- Example ---
if __name__ == "__main__":
    print(yahoo_find_ticker("Apple"))            # -> {'symbol': 'AAPL', ...}
    print(yahoo_find_ticker("Delta", return_all=True)[:3])
