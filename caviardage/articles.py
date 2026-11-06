"""Pick a well-known article and fetch its introduction.

A background worker keeps a few pages ready for each language and level, so
"New page" doesn't wait on Wikipedia.
"""
import collections
import random
import re
import threading
import time
from html.parser import HTMLParser

import requests

from . import store, text

HEADERS = {"User-Agent": "Caviardage/0.1 (https://github.com/gaetan-deturche/caviardage) python-requests"}
MIN_WORDS = 80
MAX_WORDS = 400
READY_PAGES = 2
LIVE_DEADLINE = 8  # Seconds a player can be kept waiting when no page is ready.
WORKER_PAUSE = 1  # Seconds between the worker's requests, to respect Wikipedia's limits.


class ArticleError(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, wait):
        super().__init__(f"Wikipedia asked to wait {wait}s")
        self.wait = wait


class _ArticleText(HTMLParser):
    """Plain text from Wikipedia's formatted extract, with superscripts and subscripts marked."""

    BLOCKS = {"p", "div", "li", "ul", "ol", "dl", "dd", "dt", "blockquote", "br", "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr"}
    SKIPPED = {"style", "script", "math"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self.skipping += 1
        elif tag in ("sup", "sub"):
            self.parts.append(text.WORD_BREAK)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIPPED:
            self.skipping = max(0, self.skipping - 1)
        elif tag in ("sup", "sub"):
            self.parts.append(text.WORD_BREAK)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data.replace("\n", " "))


def _plain_text(extract):
    parser = _ArticleText()
    parser.feed(extract)
    parser.close()
    return "".join(parser.parts)


def _clean(extract):
    paragraphs = []
    for line in extract.split("\n"):
        line = re.sub(r"\s*\[[^\]]{0,60}\]", "", line)  # Editors' notes such as [réf. nécessaire].
        line = re.sub(r"\s+", " ", line).strip()
        if not line or "\\displaystyle" in line or line.startswith("=="):
            continue
        paragraphs.append(line)
    return paragraphs


def _trim(paragraphs):
    kept, count = [], 0
    for paragraph in paragraphs:
        size = len(paragraph.split())
        if kept and count + size > MAX_WORDS:
            break
        kept.append(paragraph)
        count += size
    return kept, count


def _display_title(title):
    """Remove the disambiguation: Mercure (planète) -> Mercure."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def _fetch(title, lang):
    response = requests.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        headers=HEADERS,
        timeout=6,
        params={
            "action": "query", "format": "json", "formatversion": 2, "redirects": 1, "titles": title,
            "prop": "extracts|info|pageprops", "inprop": "url", "exintro": 1,
        },
    )
    if response.status_code == 429:
        raise RateLimited(int(response.headers.get("retry-after", 5) or 5))
    response.raise_for_status()
    return response.json()["query"]["pages"][0]


def _to_article(page):
    """The article for a fetched page, or None if it can't be played."""
    if page.get("missing") or "disambiguation" in page.get("pageprops", {}):
        return None
    paragraphs, words = _trim(_clean(_plain_text(page.get("extract", ""))))
    if words < MIN_WORDS:
        return None
    return {
        "title": _display_title(page["title"]),
        "paragraphs": paragraphs,
        "url": page.get("fullurl", f"https://en.wikipedia.org/wiki/{page['title'].replace(' ', '_')}"),
    }


class Articles:
    def __init__(self, start_worker=True):
        self.used = set()
        self.ready = collections.defaultdict(collections.deque)
        self.wanted = {("fr", "famous"), ("en", "famous")}
        self.lock = threading.Lock()
        self.wake = threading.Event()
        if start_worker:
            threading.Thread(target=self._keep_ready, daemon=True).start()

    def _pick_title(self, lang, level):
        size = store.pool_size(lang, level)
        with self.lock:
            for _ in range(200):
                title = store.pool_title(lang, level, random.randrange(size))
                if (lang, title) not in self.used:
                    break
            self.used.add((lang, title))
            return title

    def _keep_ready(self):
        while True:
            with self.lock:
                short = [key for key in self.wanted if len(self.ready[key]) < READY_PAGES]
            if not short:
                self.wake.wait()
                self.wake.clear()
                continue
            lang, level = random.choice(short)
            try:
                article = _to_article(_fetch(self._pick_title(lang, level), lang))
                if article:
                    with self.lock:
                        self.ready[(lang, level)].append(article)
                time.sleep(WORKER_PAUSE)
            except RateLimited as limited:
                time.sleep(limited.wait + 1)
            except (requests.RequestException, ValueError, KeyError, IndexError):
                time.sleep(5)

    def next(self, lang, level):
        """A ready page if there is one. Otherwise fetch live, for a few seconds at most."""
        key = (lang, level)
        with self.lock:
            self.wanted.add(key)
            article = self.ready[key].popleft() if self.ready[key] else None
        self.wake.set()
        if article:
            return article
        deadline = time.monotonic() + LIVE_DEADLINE
        while time.monotonic() < deadline:
            try:
                article = _to_article(_fetch(self._pick_title(lang, level), lang))
            except RateLimited:
                break
            except (requests.RequestException, ValueError, KeyError, IndexError):
                continue
            if article:
                return article
        raise ArticleError("Wikipedia did not return a usable article.")
