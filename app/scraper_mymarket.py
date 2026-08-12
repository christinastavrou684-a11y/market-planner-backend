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
            continue
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
    for r in search_mymarket(query):
        print(r)
