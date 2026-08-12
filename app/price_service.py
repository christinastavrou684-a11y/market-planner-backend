"""
Price service: παίρνει LIVE τιμές από τους scrapers (Σκλαβενίτης/My Market)
με βάση το όνομα ενός υλικού, με απλή cache in-memory ώστε να μην ξαναχτυπάμε
τα sites σε κάθε request.

Αν το scraping αποτύχει για κάποιο υλικό (π.χ. δεν βρέθηκε αποτέλεσμα, ή
το site άλλαξε δομή), επιστρέφουμε None και ο caller πέφτει πίσω στην
εκτιμώμενη τιμή (package_cost) από το recipes.json -- η εφαρμογή δεν
"σπάει" ποτέ εξαιτίας του scraping.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .scraper_sklavenitis import search_sklavenitis
from .scraper_mymarket import search_mymarket

_CACHE = {}  # (supermarket, ingredient_name) -> (timestamp, price ή None)
CACHE_TTL_SECONDS = 60 * 60  # 1 ώρα
MAX_WORKERS = 10  # πόσες ταυτόχρονες αναζητήσεις κάνουμε


def get_live_price(ingredient_name: str, supermarket: str):
    key = (supermarket, ingredient_name)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    price = _fetch_price(ingredient_name, supermarket)
    _CACHE[key] = (now, price)
    return price


def _fetch_price(ingredient_name: str, supermarket: str):
    try:
        if supermarket == "mymarket":
            results = search_mymarket(ingredient_name, max_results=3)
        else:
            results = search_sklavenitis(ingredient_name, max_results=3)
    except Exception:
        return None

    prices = [r["price"] for r in results if r.get("price")]
    if not prices:
        return None

    prices.sort()
    return prices[len(prices) // 2]


def get_live_prices_bulk(ingredient_names: list, supermarket: str) -> dict:
    """Επιστρέφει {ingredient_name: price_or_None}, ψάχνοντας ΠΑΡΑΛΛΗΛΑ
    (μέχρι MAX_WORKERS ταυτόχρονα) ώστε να μη σερνόμαστε σε ~45 διαδοχικά
    requests."""
    results = {}
    now = time.time()

    # πρώτα τσεκάρουμε τι είναι ήδη στην cache -- αυτά δεν χρειάζονται δίκτυο
    to_fetch = []
    for name in ingredient_names:
        key = (supermarket, name)
        cached = _CACHE.get(key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            results[name] = cached[1]
        else:
            to_fetch.append(name)

    if not to_fetch:
        return results

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_name = {
            executor.submit(_fetch_price, name, supermarket): name
            for name in to_fetch
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                price = future.result()
            except Exception:
                price = None
            results[name] = price
            _CACHE[(supermarket, name)] = (now, price)

    return results


def clear_cache():
    _CACHE.clear()
