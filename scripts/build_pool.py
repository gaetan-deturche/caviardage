"""Build data/pool.json: well-known article titles in English and French.

Source: English Wikipedia's "Vital articles" lists, mapped to French through
interlanguage links. "famous" is Level 3 (about 1,000 pages) and "wide" is
Level 4 (about 10,000 pages).
"""
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "Caviardage/0.1 (https://github.com/gaetan-deturche/caviardage) python-requests"}
SKIP_SUBPAGE = re.compile(r"Article alerts|Draft|Archive|/$|Removed|Talk")
SKIP_TITLE = re.compile(r"^\d+$|^List of |^Lists of |^Outline of |^Index of |^Timeline of ")


def call(params):
    """One polite request: at most one a second, and wait when Wikipedia asks."""
    params = {"action": "query", "format": "json", "formatversion": 2, "maxlag": 5, **params}
    for attempt in range(8):
        time.sleep(1)
        response = requests.get(API, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                data = None
            if data is not None and "error" not in data:
                return data
        time.sleep(max(int(response.headers.get("retry-after", 0) or 0), 10 * (attempt + 1)))
    raise RuntimeError(f"Wikipedia kept refusing: {response.status_code}")


def links(page):
    out, params = [], {"titles": page, "redirects": 1, "prop": "links", "plnamespace": 0, "pllimit": "max"}
    while True:
        data = call(params)
        out += [l["title"] for p in data["query"]["pages"] for l in p.get("links", [])]
        if "continue" not in data:
            return out
        params.update(data["continue"])


def level4_pages():
    # These list pages are redirects to their current location; links() follows them.
    out, params = [], {"list": "allpages", "apnamespace": 4, "apprefix": "Vital articles/Level/4/", "aplimit": "max"}
    while True:
        data = call(params)
        out += [p["title"] for p in data["query"]["allpages"]]
        if "continue" not in data:
            return [p for p in out if not SKIP_SUBPAGE.search(p)]
        params.update(data["continue"])


def french_titles(titles):
    """Return {English title: French title} using interlanguage links."""
    mapping = {}
    for start in range(0, len(titles), 50):
        params = {"titles": "|".join(titles[start:start + 50]), "prop": "langlinks", "lllang": "fr", "lllimit": "max", "redirects": 1}
        while True:
            data = call(params)
            query = data["query"]
            resolved = {r["to"]: r["from"] for r in query.get("redirects", [])}
            for page in query["pages"]:
                if page.get("langlinks"):
                    french = page["langlinks"][0]["title"]
                    mapping[page["title"]] = french
                    if page["title"] in resolved:
                        mapping[resolved[page["title"]]] = french
            if "continue" not in data:
                break
            params.update(data["continue"])
        if start % 1000 == 0:
            print(f"  mapped {start}/{len(titles)}", flush=True)
    return mapping


def main():
    famous = {t for t in links("Wikipedia:Vital articles/Level/3") if not SKIP_TITLE.search(t)}
    print("famous", len(famous), flush=True)
    wide = set(famous)
    for page in level4_pages():
        found = [t for t in links(page) if not SKIP_TITLE.search(t)]
        print(" ", page, len(found), flush=True)
        wide.update(found)
    print("wide", len(wide), flush=True)
    mapping = french_titles(sorted(wide))
    pool = {
        "en": {"famous": sorted(famous), "wide": sorted(wide)},
        "fr": {
            "famous": sorted({mapping[t] for t in famous if t in mapping}),
            "wide": sorted({mapping[t] for t in wide if t in mapping}),
        },
    }
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=0), encoding="utf-8")
    print({lang: {k: len(v) for k, v in levels.items()} for lang, levels in pool.items()})


if __name__ == "__main__":
    main()
