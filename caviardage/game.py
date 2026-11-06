"""One round: holds the hidden article and answers guesses. The browser never gets hidden text."""
import secrets

from . import text

MAX_WORD_LENGTH = 40
TIER_RANK = {"same": 3, "family": 2, "scene": 1}
FAMILY_FROM = 0.40  # Word scores where a family link usually starts, and where it stops mattering.
FAMILY_TO = 0.80


def _shade(tier, closeness):
    """How close to show a guess, from 0.12 to 1. A family link is always shown closer than a scene one."""
    closeness = min(1.0, max(0.0, closeness))
    return round(0.55 + 0.45 * closeness if tier == "family" else 0.12 + 0.43 * closeness, 2)


def _word_shade(tier, score):
    if tier == "family":
        return _shade(tier, (score - FAMILY_FROM) / (FAMILY_TO - FAMILY_FROM))
    return _shade(tier, score / FAMILY_FROM)


class Game:
    def __init__(self, article, lang, closeness, level="famous", game_id=None):
        self.id = game_id or secrets.token_hex(4)
        self.lang = lang
        self.level = level
        self.closeness = closeness
        self.article = article
        self.guesses = {}
        self.tokens = []
        self.finished = False
        self.gave_up = False

        self.title_slots = []
        for token in text.tokenize(article["title"]):
            self._add(token, "title")
        self.tokens.append({"word": False, "text": "\n\n", "part": "break"})
        for index, paragraph in enumerate(article["paragraphs"]):
            if index:
                self.tokens.append({"word": False, "text": "\n\n", "part": "break"})
            for token in text.tokenize(paragraph):
                self._add(token, "body")

        self.words = [t for t in self.tokens if t["word"]]
        self.other_name = text.other_name(article["title"], article["paragraphs"][0], lang) if article["paragraphs"] else []
        self.other_name_left = set(range(len(self.other_name)))
        self.targets = {t["text"].lower() for t in self.words if not text.is_stopword(t["text"], lang)}
        for index, token in enumerate(self.tokens):
            if token["word"]:
                following = self.tokens[index + 1]["text"] if index + 1 < len(self.tokens) else ""
                elided = following[:1] in ("'", "’")  # D' and L' are not Roman numerals.
                token["number"] = None if elided else text.number_value(token["text"], lang)

    @classmethod
    def restore(cls, game_id, saved, closeness):
        """Rebuild a saved round by replaying its guesses."""
        game = cls(saved["article"], saved["lang"], closeness, level=saved["level"], game_id=game_id)
        for word in saved["guesses"]:
            game.guess(word)
        if saved["gave_up"]:
            game.give_up()
        return game

    def _add(self, token, part):
        token = {**token, "part": part, "i": len(self.tokens)}
        if token["word"]:
            token.update(revealed=False, near=None, near_rank=0, near_score=-1.0, shade=None)
            if part == "title":
                self.title_slots.append(token)
        self.tokens.append(token)

    def public_tokens(self):
        out = []
        for token in self.tokens:
            if not token["word"]:
                out.append({"i": token["i"] if "i" in token else None, "text": token["text"], "part": token["part"]})
            elif token["revealed"] or self.finished:
                out.append({
                    "i": token["i"], "word": True, "text": token["text"], "part": token["part"],
                    "revealed": True, "missed": not token["revealed"],
                })
            else:
                out.append({
                    "i": token["i"], "word": True, "length": len(token["text"]), "part": token["part"],
                    "near": token["near"], "tier": _tier_name(token["near_rank"]), "shade": token["shade"],
                })
        return out

    def _finish_payload(self):
        return {"title": self.article["title"], "url": self.article["url"]}

    def state(self):
        payload = {
            "id": self.id, "lang": self.lang, "level": self.level, "tokens": self.public_tokens(),
            "count": len(self.guesses), "log": list(self.guesses.values()),
            "finished": self.finished, "gaveUp": self.gave_up,
        }
        if self.finished:
            payload["answer"] = self._finish_payload()
        return payload

    def give_up(self):
        self.finished = True
        self.gave_up = True
        return self.state()

    def guess(self, raw):
        word = raw.strip()
        if not word or len(word) > MAX_WORD_LENGTH or not text.WORD_RE.fullmatch(word):
            return {"error": "invalid"}
        if self.finished:
            return {"error": "finished"}
        guess_keys = text.keys(word, self.lang)
        if text.fold(word) in self.guesses:
            return {"error": "duplicate", "word": word}

        number = text.number_value(word, self.lang, guess=True)
        ending = text.ordinal_ending(word) if number is not None else None
        same = [
            t for t in self.words
            if t["text"].lower() == word.lower()
            or guess_keys & text.keys(t["text"], self.lang)
            or (number is not None and t["number"] == number)
            or (ending and t["text"].lower() == ending)  # Guessing 7th also finds the th.
        ]
        if not same and number is None and not self._known(word):
            return {"error": "unknown", "word": word}

        for token in same:
            token["revealed"] = True

        best = "same" if same else None
        near_hits = matches = 0
        best_shade = 0
        if number is not None:
            for token in self.words:
                if token["revealed"] or token["number"] is None or token["number"][0] != number[0]:
                    continue
                tier, score = text.number_tier(number[1], token["number"][1])
                rank = TIER_RANK[tier]
                best_shade = max(best_shade, _shade(tier, score))
                if best is None or rank > TIER_RANK[best]:
                    best = tier
                matches += 1
                if (rank, score) > (token["near_rank"], token["near_score"]):
                    token.update(near=word, near_rank=rank, near_score=score, shade=_shade(tier, score))
                    near_hits += 1
        elif not text.is_stopword(word, self.lang):
            for target in self.targets:
                tier, score = self.closeness.tier(word, target, self.lang)
                if not tier:
                    continue
                if best is None or TIER_RANK[tier] > TIER_RANK[best]:
                    best = tier
                rank = TIER_RANK[tier]
                best_shade = max(best_shade, _word_shade(tier, score))
                for token in self.words:
                    if token["revealed"] or token["text"].lower() != target:
                        continue
                    matches += 1
                    if (rank, score) > (token["near_rank"], token["near_score"]):
                        token.update(near=word, near_rank=rank, near_score=score, shade=_word_shade(tier, score))
                        near_hits += 1

        self.guesses[text.fold(word)] = {"word": word, "tier": best, "hits": len(same), "shade": best_shade}
        self.other_name_left = {
            i for i in self.other_name_left if not guess_keys & text.keys(self.other_name[i], self.lang)
        }
        title_found = self.title_slots and all(t["revealed"] for t in self.title_slots)
        if title_found or (self.other_name and not self.other_name_left):
            self.finished = True
        return {"word": word, "tier": best, "hits": len(same), "near": near_hits, "matches": matches, "state": self.state()}

    def _known(self, word):
        return text.is_real_word(word, self.lang) or self.closeness.in_vocabulary(word, self.lang)


def _tier_name(rank):
    return {2: "family", 1: "scene"}.get(rank)
