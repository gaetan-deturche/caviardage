"""How related two words are.

Two signals, both read from disk so memory use stays low:
- WordNet says what a word is: a monkey is a primate.
- ConceptNet Numberbatch says which words are related, using a knowledge graph.

The result is a tier: "family" (a direct link), "scene" (the same broad
category or setting) or None. Words Numberbatch doesn't know only match exactly.
"""
import functools
from pathlib import Path

import numpy as np

from . import store, text

ROOT = Path(__file__).resolve().parent.parent

# Tuned on labelled word pairs and on unrelated guesses against real pages.
FAMILY_SCORE = 0.40
SCENE_SCORE = 0.20
WORDNET_MIN_SCORE = 0.10  # A WordNet link needs some support, to skip wrong senses.
WORDNET_SCENE_MIN_SCORE = 0.15  # Broad links are easier to hit by accident, so they need more.
FAMILY_GROUP_SIZE = 400  # Sharing a parent only counts if that parent is specific.
SCENE_GROUP_SIZE = 5000


class Closeness:
    def __init__(self):
        self.matrix = np.load(ROOT / "data" / "numberbatch.npy", mmap_mode="r")

    def in_vocabulary(self, word, lang):
        return store.vector_index(lang, word.lower()) is not None

    @functools.lru_cache(maxsize=3000)
    def _numberbatch(self, word, lang):
        for candidate in (word.lower(), *text.lemmas(word, lang)):
            index = store.vector_index(lang, candidate)
            if index is not None:
                vector = np.asarray(self.matrix[index], dtype=np.float32)
                return vector / (np.linalg.norm(vector) or 1)
        return None

    def score(self, a, b, lang):
        va, vb = self._numberbatch(a, lang), self._numberbatch(b, lang)
        if va is None or vb is None:
            return 0.0
        return float(va @ vb)

    @functools.lru_cache(maxsize=2000)
    def _ancestors(self, word, lang):
        """{ancestor: steps away} for the senses of a word."""
        found = {}
        for lemma in text.lemmas(word, lang):
            for synset in store.word_synsets(lang, lemma):
                for ancestor, steps in store.synset_ancestors(synset):
                    if steps < found.get(ancestor, 99):
                        found[ancestor] = steps
        return found

    def _wordnet_tier(self, a, b, lang):
        ancestors_a, ancestors_b = self._ancestors(a, lang), self._ancestors(b, lang)
        best = None
        for shared in ancestors_a.keys() & ancestors_b.keys():
            steps = ancestors_a[shared] + ancestors_b[shared]
            if steps > 3:
                continue
            size = store.group_size(shared)
            if steps <= 2 and size <= FAMILY_GROUP_SIZE:
                return "family"
            if size <= SCENE_GROUP_SIZE:
                best = "scene"
        return best

    def tier(self, a, b, lang):
        """Tier and score of guess a against article word b."""
        score = self.score(a, b, lang)
        tier = "family" if score >= FAMILY_SCORE else "scene" if score >= SCENE_SCORE else None
        if tier != "family" and score >= WORDNET_MIN_SCORE:
            linked = self._wordnet_tier(a, b, lang)
            if linked == "family" or (linked == "scene" and tier is None and score >= WORDNET_SCENE_MIN_SCORE):
                tier = linked
        return tier, score
