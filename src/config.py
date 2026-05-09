"""Project configuration for Toronto condo rental scraping."""

BASE_URL = "https://condos.ca"
SEARCH_URL_TEMPLATE = "https://condos.ca/toronto?mode=Rent&page={page}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15
REQUEST_DELAY_SECONDS = 1.0
MAX_PAGES = 76

# These selectors reflect the original notebook and may need updates if Condos.ca changes.
SELECTORS = {
    "listing_link": "a.styles___Link-sc-54qk44-1.fDWBFh",
    "address": "h1.styles___Title-sc-ka5njm-7.iMYmnJ",
    "price": "div.styles___Price-sc-ka5njm-25.jcbcec",
    "neighbourhood": "a.styles___AddressInlineLink-sc-ka5njm-31.bARpRt",
    "area": "a.styles___AddressInlineLink-sc-ka5njm-31.hVlEZL",
    "summary_values": "span.styles___BlurCont-sc-qq1hs5-0",
    "detail_values": "div.styles___BlurCont-sc-qq1hs5-0.styles___InfoRowValue-sc-1cv9cf1-4.hvTiCH",
}
