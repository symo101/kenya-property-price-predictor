import requests
from bs4 import BeautifulSoup
import pandas as pd
import time, random, logging, re
from datetime import datetime

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

#  CONFIGURATION

LISTING_TYPES = {
    "sale": "https://www.buyrentkenya.com/houses-for-sale",
    "rent": "https://www.buyrentkenya.com/houses-for-rent",
}

MAX_PAGES   = 40
MIN_DELAY   = 2.0
MAX_DELAY   = 4.5
OUTPUT_FILE = "buyrentkenya_raw.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://www.google.com/",
}

#  FETCH


def get_soup(url: str) -> BeautifulSoup | None:
    try:
        session = requests.Session()
        session.get("https://www.buyrentkenya.com", headers=HEADERS, timeout=20)
        time.sleep(random.uniform(0.5, 1.0))
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        log.info(f"  HTTP {resp.status_code} | {len(resp.text):,} chars")
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP error: {e}")
    except requests.exceptions.ConnectionError:
        log.warning(f"Connection error: {url}")
    except requests.exceptions.Timeout:
        log.warning(f"Timeout: {url}")
    except Exception as e:
        log.warning(f"{type(e).__name__}: {e}")
    return None

#  FIND ALL CARD WRAPPERS
#  Each card has data-cy="listing-<numeric_id> from the inspection

def find_card_wrappers(soup: BeautifulSoup) -> list:
    """
    Finds all listing card wrapper divs.

    CONFIRMED from diagnostic:
      data-cy="listing-3826286"  (one per listing, id varies)
      data-cy="listing-3926584"
      ... etc

    We match the pattern data-cy="listing-<digits>" using regex.
    This gives us the full card container with ALL fields inside it.
    """
    cards = soup.find_all(
        attrs={"data-cy": re.compile(r"^listing-\d+$")}
    )
    return cards

#  PARSE ONE CARD

def parse_card(card, listing_type: str) -> dict:
    """
    Extracts all fields from one card wrapper div using confirmed data-cy selectors.

    CONFIRMED data-cy values (from diagnostic Test 5):
      card-price          → "KSh 17,500,000"
      card-bedroom_count  → "4 Bedrooms" or "4"
      card-bathroom_count → "5 Bathrooms" or "5"
      card-area_value     → "240 m²" or "240"
      listing-information-link → the <a> with href and id
      user-title          → agent/agency name
      status-badge        → e.g. "For Sale", "To Let"
    """

    def cy(value: str) -> str:
        """Find element by data-cy and return its text."""
        el = card.find(attrs={"data-cy": value})
        return el.get_text(strip=True) if el else ""

    # Listing ID  (from the card's own data-cy attribute)
    card_cy = card.get("data-cy", "") 
    listing_id = card_cy.replace("listing-", "") 

    # URL  (from the anchor with data-cy="listing-information-link")
    anchor = card.find("a", attrs={"data-cy": "listing-information-link"})
    if not anchor:
        # Fallback: any anchor linking to /listings/
        anchor = card.find("a", href=re.compile(r"^/listings/"))
    href   = anchor.get("href", "") if anchor else ""
    url    = ("https://www.buyrentkenya.com" + href
              if href.startswith("/") else href)

    #Title  (from the anchor id or href slug)
    # BuyRentKenya puts the property title in the link text or nearby heading
    title = ""
    if anchor:
        # Try anchor text first
        title = anchor.get_text(strip=True)

    if not title:
        # Try h2 or h3 inside the card
        heading = card.find("h2") or card.find("h3") or card.find("p")
        title = heading.get_text(strip=True) if heading else ""

    if not title and href:
        # Build title from URL slug as last resort
        # "/listings/4-bed-house-ruiru-3826286" → "4 Bed House Ruiru"
        slug = href.split("/listings/")[-1]
        slug = re.sub(r"-\d+$", "", slug)        # remove trailing id
        title = slug.replace("-", " ").title()

    #Price
    price_raw = cy("card-price")

    # Bedrooms
    bedrooms_raw = cy("card-bedroom_count")

    #Bathrooms
    bathrooms_raw = cy("card-bathroom_count")

    #Size / Area
    size_raw = cy("card-area_value")

    #Location
    location = (
        cy("card-location") or
        cy("listing-location") or
        cy("card-suburb") or
        ""
    )
    if not location:

        full_text = card.get_text(separator=" ", strip=True)
        # Look for "Word, Word" location pattern
        loc_match = re.search(
            r"\b([A-Z][a-zA-Z\s]+),\s*([A-Z][a-zA-Z\s]+)\b",
            full_text
        )
        location = loc_match.group(0).strip() if loc_match else ""

    #Property Type
    property_type = ""
    text_to_check = (title + " " + url).lower()
    for ptype in ["apartment", "bungalow", "maisonette", "townhouse",
                  "villa", "studio", "penthouse", "flat", "house", "cottage"]:
        if ptype in text_to_check:
            property_type = ptype.title()
            break

    # Agent / Agency
 
    agent_el = card.find(attrs={"data-cy": "user-title"})
    agent    = agent_el.get_text(strip=True) if agent_el else ""

    # Status Badge
    
    status = cy("status-badge")

    return {
        "listing_id":    listing_id,
        "title":         title,
        "price_raw":     price_raw,         # "KSh 17,500,000"  (clean in notebook)
        "bedrooms_raw":  bedrooms_raw,      # "4 Bedrooms"      (clean in notebook)
        "bathrooms_raw": bathrooms_raw,     # "5 Bathrooms"     (clean in notebook)
        "size_raw":      size_raw,          # "240 m²"          (clean in notebook)
        "location":      location,          # "Kamakis, Ruiru"
        "property_type": property_type,     # "House" / "Apartment" etc.
        "status":        status,            # "For Sale" / "To Let"
        "listing_type":  listing_type,      # "sale" / "rent"
        "agent":         agent,
        "url":           url,
        "scraped_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

#  SCRAPE ONE PAGE

def scrape_page(soup: BeautifulSoup, listing_type: str) -> list[dict]:
    cards = find_card_wrappers(soup)

    if not cards:
        log.warning("  ⚠  No card wrappers found (data-cy='listing-<id>')")
        log.warning("  → Run the diagnostic script to check current data-cy values")
        return []

    log.info(f"  {len(cards)} cards found")
    results = []

    for card in cards:
        row = parse_card(card, listing_type)
        # Keep row if it has at least a URL (even if other fields are empty)
        if row["url"] or row["listing_id"]:
            results.append(row)

    log.info(f"  {len(results)} rows extracted")
    return results

#  DETECT LAST PAGE

def is_last_page(soup: BeautifulSoup) -> bool:
    # Check result count — "0 properties" means no more pages
    count_el = soup.find(attrs={"data-cy": "search-result-count"})
    if count_el:
        count_text = count_el.get_text(strip=True).lower()
        if count_text.startswith("0"):
            return True

    page_text = soup.get_text(separator=" ", strip=True).lower()
    if any(p in page_text for p in ["no properties found", "0 properties", "no listings found"]):
        return True

    return False

#  PAGINATE


def scrape_listing_type(label: str, base_url: str) -> list[dict]:
    all_props = []

    for page_num in range(1, MAX_PAGES + 1):
        url = f"{base_url}?page={page_num}"
        log.info(f"\n[{label.upper()}] Page {page_num}/{MAX_PAGES}  →  {url}")

        soup = get_soup(url)
        if soup is None:
            log.warning("  Skipping — fetch failed")
            continue

        if is_last_page(soup):
            log.info("  → Last page. Stopping.")
            break

        page_props = scrape_page(soup, label)
        if not page_props:
            log.info("  → No cards on this page. Stopping.")
            break

        all_props.extend(page_props)
        log.info(f"  Cumulative [{label}]: {len(all_props)}")

        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        log.info(f"  Sleeping {delay:.1f}s ...")
        time.sleep(delay)

    return all_props

#  SAVE + REPORT


def save_and_report(df: pd.DataFrame) -> None:
    if df.empty:
        log.error("❌ No data collected.")
        log.error("→ Run buyrentkenya_diagnostic.py to re-check selectors.")
        return

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print("\n" + "═" * 64)
    print(f"    {len(df):,} listings saved  →  {OUTPUT_FILE}")
    print("═" * 64)
    print(f"\n  Shape : {df.shape[0]:,} rows × {df.shape[1]} columns")

    print(f"\n  Listing type breakdown:")
    print(df["listing_type"].value_counts().to_string())

    print(f"\n  Property type breakdown:")
    print(df["property_type"].value_counts().head(10).to_string())

    print(f"\n  Fill rate per column:")
    for col in df.columns:
        n   = df[col].replace("", pd.NA).notna().sum()
        pct = n / len(df) * 100
        bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
        print(f"    {col:<18} {bar}  {pct:5.1f}%  ({n:,} rows)")

    print(f"\n  Sample data (first 5 rows):")
    cols = ["title", "price_raw", "bedrooms_raw", "bathrooms_raw", "location", "listing_type"]
    print(df[cols].head(5).to_string(index=False))
    print()

#  MAIN

if __name__ == "__main__":
    print("═" * 64)
    print("  BuyRentKenya Scraper  v4  (Diagnostic-Confirmed Selectors)")
    print(f"  data-cy selectors : listing-<id>, card-price,")
    print(f"                      card-bedroom_count, card-bathroom_count,")
    print(f"                      card-area_value, user-title, status-badge")
    print(f"  Max pages : {MAX_PAGES} per listing type")
    print(f"  Delay     : {MIN_DELAY}–{MAX_DELAY}s")
    print(f"  Output    : {OUTPUT_FILE}")
    print("═" * 64)

    combined = []
    for label, base_url in LISTING_TYPES.items():
        props = scrape_listing_type(label, base_url)
        log.info(f"\n[{label.upper()}] Done — {len(props):,} listings")
        combined.extend(props)

    df = pd.DataFrame(combined)

    # Deduplicate by listing_id
    before = len(df)
    df.drop_duplicates(subset=["listing_id"], keep="first", inplace=True)
    removed = before - len(df)
    if removed:
        log.info(f"Removed {removed} duplicate listings")

    save_and_report(df)