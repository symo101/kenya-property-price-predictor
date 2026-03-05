# =============================================================================
#  BuyRentKenya — Diagnostic Script
#  Run this BEFORE the main scraper to see the raw HTML of listing cards
#  and figure out the exact selectors we need
# =============================================================================

import requests
from bs4 import BeautifulSoup
import re
import json

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection":      "keep-alive",
    "Referer":         "https://www.google.com/",
}

URL = "https://www.buyrentkenya.com/houses-for-sale"

print("=" * 70)
print("  BuyRentKenya HTML Diagnostic")
print("=" * 70)

session = requests.Session()
session.get("https://www.buyrentkenya.com", headers=HEADERS, timeout=20)

resp = session.get(URL, headers=HEADERS, timeout=20)
print(f"\nHTTP Status : {resp.status_code}")
print(f"Page size   : {len(resp.text):,} chars")

soup = BeautifulSoup(resp.text, "html.parser")

# ── TEST 1: Find listing anchors by data-cy ────────────────────────────────
print("\n" + "─" * 70)
print("TEST 1: Find anchors with data-cy='listing-information-link'")
anchors = soup.find_all("a", attrs={"data-cy": "listing-information-link"})
print(f"  Found: {len(anchors)} anchors")

if not anchors:
    print("\n  ⚠  Not found! Trying fallbacks...")
    
    # Try all data-cy values present on the page
    all_cy = soup.find_all(attrs={"data-cy": True})
    cy_values = list(set(el.get("data-cy") for el in all_cy))
    print(f"\n  ALL data-cy values on this page ({len(cy_values)} unique):")
    for v in sorted(cy_values):
        count = len(soup.find_all(attrs={"data-cy": v}))
        print(f"    data-cy='{v}'  ({count} elements)")

# ── TEST 2: Find all <a> tags linking to /listings/ ───────────────────────
print("\n" + "─" * 70)
print("TEST 2: Find <a> tags with href containing '/listings/'")
listing_links = soup.find_all("a", href=re.compile(r"/listings/"))
print(f"  Found: {len(listing_links)} links")
if listing_links:
    print(f"\n  First 3 hrefs:")
    for a in listing_links[:3]:
        print(f"    {a.get('href')}")
        print(f"    data-cy = {a.get('data-cy', 'NONE')}")
        print(f"    id      = {a.get('id', 'NONE')}")
        print()

# ── TEST 3: Print raw HTML of the FIRST listing anchor and its parent ─────
print("\n" + "─" * 70)
print("TEST 3: Raw HTML of first listing card (anchor + 3 parent levels)")

target_anchors = (
    soup.find_all("a", attrs={"data-cy": "listing-information-link"}) or
    soup.find_all("a", href=re.compile(r"/listings/"))
)

if target_anchors:
    anchor = target_anchors[0]
    
    # Walk up 3 parent levels and print each
    el = anchor
    for level in range(4):
        print(f"\n  Level {level} — <{el.name}> "
              f"| id='{el.get('id','')}' "
              f"| data-cy='{el.get('data-cy','')}' "
              f"| class='{' '.join(el.get('class',[]))[:80]}'")
        
        # Print direct children tags
        children = [c for c in el.children if hasattr(c, 'name') and c.name]
        print(f"    Children tags: {[c.name for c in children[:10]]}")
        
        if el.parent:
            el = el.parent
        else:
            break

    # Print the card container's full text
    card_container = target_anchors[0]
    for _ in range(3):
        if card_container.parent:
            card_container = card_container.parent

    print(f"\n  Card container full text (first 400 chars):")
    print(f"  {card_container.get_text(separator=' | ', strip=True)[:400]}")

# ── TEST 4: Look for gtmData JSON in the page ─────────────────────────────
print("\n" + "─" * 70)
print("TEST 4: Search for gtmData JSON blobs in <script> tags")

scripts = soup.find_all("script")
gtm_scripts = [s for s in scripts if s.string and "gtmData" in (s.string or "")]
print(f"  Found {len(gtm_scripts)} script tags containing 'gtmData'")

if gtm_scripts:
    raw = gtm_scripts[0].string
    print(f"\n  First gtmData script (first 500 chars):")
    print(f"  {raw[:500]}")
    
    # Try to extract the JSON
    match = re.search(r"JSON\.parse\('(.+?)'\)", raw, re.DOTALL)
    if match:
        print(f"\n  ✅ JSON.parse() pattern found!")
        raw_json = match.group(1)
        raw_json = raw_json.replace("\\/", "/")
        try:
            # Handle unicode escapes like \u0022
            import codecs
            raw_json2 = raw_json.encode('raw_unicode_escape').decode('unicode_escape')
            data = json.loads(raw_json2)
            print(f"  Parsed keys: {list(data.keys())}")
            print(f"  ga4Value    : {data.get('ga4Value', 'NOT FOUND')}")
            print(f"  listingId   : {data.get('listingId', 'NOT FOUND')}")
            print(f"  productSlug : {data.get('productSlug', 'NOT FOUND')}")
        except Exception as e:
            print(f"  ⚠ JSON parse error: {e}")
            print(f"  Raw JSON sample: {raw_json[:300]}")
    else:
        print(f"\n  ⚠ JSON.parse() pattern NOT found")
        print(f"  Script content sample: {raw[:300]}")
else:
    print("  ⚠ No gtmData scripts found — checking for Alpine.store pattern")
    alpine = [s for s in scripts if s.string and "Alpine.store" in (s.string or "")]
    print(f"  Alpine.store scripts: {len(alpine)}")
    if alpine:
        print(f"  Sample: {alpine[0].string[:400]}")

# ── TEST 5: All unique data-cy values ─────────────────────────────────────
print("\n" + "─" * 70)
print("TEST 5: Summary of ALL data-cy values on the page")
all_cy_els = soup.find_all(attrs={"data-cy": True})
cy_counts = {}
for el in all_cy_els:
    v = el.get("data-cy")
    cy_counts[v] = cy_counts.get(v, 0) + 1

print(f"  Total elements with data-cy: {len(all_cy_els)}")
print(f"  Unique data-cy values ({len(cy_counts)}):")
for v, count in sorted(cy_counts.items(), key=lambda x: -x[1]):
    print(f"    '{v}'  ×{count}")

print("\n" + "=" * 70)
print("  Diagnostic complete — share this output to fix the scraper")
print("=" * 70)
