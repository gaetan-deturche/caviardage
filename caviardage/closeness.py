"""How related two words are.

Three signals, from most to least specific:
- WordNet says what a word is: a monkey is a primate.
- Numberbatch says which words are related, using a knowledge graph.
- A multilingual text model refines the score, but can't create a match by itself.

The result is a tier: "family" (a direct link), "scene" (the same broad
category or setting) or None.
"""
import functools
import json
from pathlib import Path

import nltk
import numpy as np
from fastembed import TextEmbedding

from . import text

ROOT = Path(__file__).resolve().parent.parent
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Tuned on labelled word pairs and on unrelated guesses against real pages.
# At 0.20 an unrelated guess lights about 2 words in 116. At 0.18 it lights 3.5
# and catches weak links like mer/pont, but gets bad on some pages.
FAMILY_SCORE = 0.40
SCENE_SCORE = 0.20
NUMBERBATCH_WEIGHT = 0.8
NUMBERBATCH_MIN = 0.15  # Below this the text model can't create a match by itself.
WORDNET_MIN_SCORE = 0.10  # A WordNet link needs some support, to skip wrong senses.
WORDNET_SCENE_MIN_SCORE = 0.15  # Broad links are easier to hit by accident, so they need more.
FAMILY_GROUP_SIZE = 400  # Sharing a parent only counts if that parent is specific.
SCENE_GROUP_SIZE = 5000
WORDNET_LANG = {"fr": "fra", "en": "eng"}


class Closeness:
    def __init__(self):
        nltk.data.path.insert(0, str(ROOT / ".cache" / "nltk"))
        for package in ("wordnet", "omw-2.0"):
            nltk.download(package, download_dir=str(ROOT / ".cache" / "nltk"), quiet=True)
        from nltk.corpus import wordnet

        self.wordnet = wordnet
        self.wordnet.synsets("pont", lang="fra")  # Loads the French data now, not mid-game.
        self.matrix = np.load(ROOT / "data" / "numberbatch.npy", mmap_mode="r")
        self.vocab = json.loads((ROOT / "data" / "numberbatch_vocab.json").read_text(encoding="utf-8"))
        self.model = TextEmbedding(MODEL, cache_dir=str(ROOT / ".cache" / "models"))
        self._group_sizes = {}
        self._embeddings = {}
        self._ancestors = {}
        # Load everything now, so the first page and first guess aren't slow.
        self.tier("pont", "rivière", "fr")
        self.tier("bridge", "river", "en")

    def in_vocabulary(self, word, lang):
        return word.lower() in self.vocab[lang]

    def _numberbatch(self, word, lang):
        for candidate in (word.lower(), *text.lemmas(word, lang)):
            index = self.vocab[lang].get(candidate)
            if index is not None:
                vector = np.asarray(self.matrix[index], dtype=np.float32)
                return vector / (np.linalg.norm(vector) or 1)
        return None

    def prepare(self, words):
        """Embed many words at once, so guesses stay instant."""
        missing = sorted({w.lower() for w in words} - self._embeddings.keys())
        if missing:
            for word, vector in zip(missing, self.model.embed(missing)):
                self._embeddings[word] = vector / (np.linalg.norm(vector) or 1)

    def score(self, a, b, lang):
        self.prepare([a, b])
        by_text = float(self._embeddings[a.lower()] @ self._embeddings[b.lower()])
        va, vb = self._numberbatch(a, lang), self._numberbatch(b, lang)
        if va is None or vb is None:
            return 0.0  # The text model alone can't be trusted on rare words: musique/acœlomate = 0.76.
        related = float(va @ vb)
        if related < NUMBERBATCH_MIN:
            return related
        return NUMBERBATCH_WEIGHT * related + (1 - NUMBERBATCH_WEIGHT) * by_text

    def _group_size(self, synset):
        name = synset.name()
        if name not in self._group_sizes:
            self._group_sizes[name] = sum(1 for _ in synset.closure(lambda s: s.hyponyms()))
        return self._group_sizes[name]

    def _synset_ancestors(self, word, lang):
        """{ancestor: steps away} for the noun senses of a word (verbs and others if none)."""
        key = (word.lower(), lang)
        if key not in self._ancestors:
            found = {}
            for lemma in text.lemmas(word, lang):
                synsets = self.wordnet.synsets(lemma, lang=WORDNET_LANG[lang])
                nouns = [s for s in synsets if s.pos() == "n"]
                for synset in (nouns or synsets)[:6]:
                    for ancestor, steps in synset.hypernym_distances():
                        if steps < found.get(ancestor, 99):
                            found[ancestor] = steps
            self._ancestors[key] = found
        return self._ancestors[key]

    def _wordnet_tier(self, a, b, lang):
        ancestors_a, ancestors_b = self._synset_ancestors(a, lang), self._synset_ancestors(b, lang)
        best = None
        for shared in ancestors_a.keys() & ancestors_b.keys():
            steps = ancestors_a[shared] + ancestors_b[shared]
            if steps > 3:
                continue
            size = self._group_size(shared)
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
