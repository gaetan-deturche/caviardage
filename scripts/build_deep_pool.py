"""Add the "deep" level to data/pool.json: the most-read pages in each language.

Source: Wikimedia's monthly clickstream datasets, streamed and not saved.
https://dumps.wikimedia.org/other/clickstream/

A page's score is its lower month, so it has to be read in both months and a
one-off news spike doesn't count.
"""
import collections
import gzip
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "Caviardage/0.1 (https://github.com/gaetan-deturche/caviardage) python-requests"}
MONTHS = ("2026-09", "2026-10")
SIZE = 100_000
SKIP = re.compile(
    r"^(Main_Page|Wikipédia:|Wikipedia:|Accueil_principal|-)$"
    r"|^(List|Lists|Outline|Index|Timeline|Deaths|Liste|Listes|Chronologie|Décès)_(of|in|de|des|du|d'|en)"
    r"|(^|_)(1[5-9]|20)\d\d(_|$|[-–])"  # Seasons and yearly editions all read the same.
    r"|\((homonymie|disambiguation)\)$"
    r"|^\d+$"
)
DAYS = re.compile(r"^\d+(er)?_(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)$|^(January|February|March|April|May|June|July|August|September|October|November|December)_\d+$")


def month_totals(lang, month):
    url = f"https://dumps.wikimedia.org/other/clickstream/{month}/clickstream-{lang}wiki-{month}.tsv.gz"
    totals = collections.Counter()
    with requests.get(url, headers=HEADERS, stream=True, timeout=120) as response:
        response.raise_for_status()
        response.raw.decode_content = False
        with gzip.GzipFile(fileobj=response.raw) as lines:
            for raw in lines:
                parts = raw.decode("utf-8", "replace").rstrip("\n").split("\t")
                if len(parts) == 4:
                    totals[parts[1]] += int(parts[3])
    print(f"{lang} {month}: {len(totals)} pages", flush=True)
    return totals


def top_pages(lang):
    first, second = (month_totals(lang, month) for month in MONTHS)
    scores = [(min(count, second[title]), title) for title, count in first.items() if title in second]
    scores = [(score, title) for score, title in scores if not SKIP.search(title) and not DAYS.match(title)]
    scores.sort(reverse=True)
    top = scores[:SIZE]
    print(f"{lang}: kept {len(top)} of {len(scores)}, lowest score {top[-1][0]} a month", flush=True)
    return sorted(title.replace("_", " ") for _, title in top)


def main():
    path = ROOT / "data" / "pool.json"
    pool = json.loads(path.read_text(encoding="utf-8"))
    for lang in ("fr", "en"):
        pool[lang]["deep"] = top_pages(lang)
    path.write_text(json.dumps(pool, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"written, {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
