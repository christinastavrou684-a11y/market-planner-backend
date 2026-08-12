"""
Scraper για το My Market (mymarket.gr).

Σαν το Σκλαβενίτη, η σελίδα αποτελεσμάτων είναι server-rendered HTML, αλλά
κάθε προϊόν κουβαλάει μέσα του ένα attribute `data-google-analytics-item-param`
με καθαρό JSON (id, name, price, brand, category) — άρα δεν χρειάζεται να
διαβάσουμε ακατέργαστο κείμενο.

ΣΗΜΑΝΤΙΚΟ: Αυτό το αρχείο δεν έχει τεσταριστεί by Claude (το sandbox δεν
έχει πρόσβαση στο mymarket.gr). Χρειάζεται να τρέξει ΤΟΠΙΚΑ στο δικό σου
μηχάνημα για να επιβεβαιωθεί ότι δουλεύει.
"""

import json
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.mymarket.gr/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def search_mymarket(query: str, max_results: int = 5):
    """Ψάχνει το query στο My Market και επιστρέφει λίστα από dicts:
    {name, brand, price (τεμαχίου, σε ευρώ), category}
    """
    params = {"query": query}
    resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=8)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("a[data-google-analytics-item-param]")

    results = []
    seen_ids = set()
    for link in links:
        raw = link.get("data-google-analytics-item-param")
        try:
            item = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        item_id = item.get("id")
        if item_id in seen_ids:
            continue  # ίδιο προϊόν εμφανίζεται συχνά 2 φορές (mobile/desktop εικόνα)
        seen_ids.add(item_id)

        price_raw = item.get("price")
        try:
            price = round(float(price_raw), 2) if price_raw is not None else None
        except ValueError:
            price = None

        results.append({
            "name": item.get("name"),
            "brand": item.get("brand"),
            "price": price,
            "category": item.get("category"),
        })

        if len(results) >= max_results:
            break

    return results


if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "γάλα"
    print(f"Αναζήτηση: {query}\n")
    for r in search_mymarket(query):
        print(r)
