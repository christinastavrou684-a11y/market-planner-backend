"""
Scraper για το Σκλαβενίτη (sklavenitis.gr).

Η σελίδα αποτελεσμάτων αναζήτησης είναι server-rendered HTML (όχι καθαρό
JSON API), αλλά κάθε προϊόν κουβαλάει μέσα στο attribute
`data-plugin-analyticsimpressions` ένα κομμάτι δομημένου JSON με
όνομα/μάρκα/τιμή — πολύ πιο αξιόπιστο από το να διαβάζουμε ακατέργαστο
κείμενο.

ΣΗΜΑΝΤΙΚΟ: Αυτό το αρχείο δεν έχει τεσταριστεί by Claude (το sandbox δεν
έχει πρόσβαση στο sklavenitis.gr). Χρειάζεται να τρέξει ΤΟΠΙΚΑ στο δικό σου
μηχάνημα για να επιβεβαιωθεί ότι δουλεύει.
"""

import json
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.sklavenitis.gr/apotelesmata-anazitisis/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def search_sklavenitis(query: str, max_results: int = 5):
    """Ψάχνει το query στο Σκλαβενίτη και επιστρέφει λίστα από dicts:
    {name, brand, price (τεμαχίου, σε ευρώ), unit_price_text (π.χ. '1,00 €/λίτρο')}
    """
    params = {"Query": query}
    resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=8)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    products = soup.select("div[data-plugin-product]")

    results = []
    for product in products:
        impressions_raw = product.get("data-plugin-analyticsimpressions")
        if not impressions_raw:
            continue
        try:
            data = json.loads(impressions_raw)
            item = data["Call"]["ecommerce"]["items"][0]
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            continue

        unit_price_el = product.select_one(".priceKil")
        unit_price_text = unit_price_el.get_text(strip=True) if unit_price_el else None

        results.append({
            "name": item.get("item_name"),
            "brand": item.get("item_brand"),
            "price": item.get("price"),
            "unit_price_text": unit_price_text,
        })

        if len(results) >= max_results:
            break

    return results


if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "γάλα"
    print(f"Αναζήτηση: {query}\n")
    for r in search_sklavenitis(query):
        print(r)
