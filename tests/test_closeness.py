"""Closeness tiers on the cases that felt wrong in the games we played."""
import pytest

from caviardage.closeness import Closeness


@pytest.fixture(scope="module")
def closeness():
    return Closeness()


@pytest.mark.parametrize("a,b,lang", [
    ("monkey", "primate", "en"), ("lemur", "primate", "en"), ("monkey", "lemur", "en"),
    ("singe", "primate", "fr"), ("roi", "reine", "fr"), ("médecin", "hôpital", "fr"), ("king", "queen", "en"),
])
def test_family(closeness, a, b, lang):
    assert closeness.tier(a, b, lang)[0] == "family"


@pytest.mark.parametrize("a,b,lang", [
    ("pangolin", "primate", "en"), ("rivière", "pont", "fr"), ("construction", "pont", "fr"), ("roi", "château", "fr"), ("rain", "cloud", "en"),
])
def test_at_least_scene(closeness, a, b, lang):
    assert closeness.tier(a, b, lang)[0] in ("scene", "family")


def test_pangolin_is_not_family(closeness):
    assert closeness.tier("pangolin", "primate", "en")[0] == "scene"


@pytest.mark.parametrize("a,b,lang", [
    ("fork", "primate", "en"), ("table", "primate", "en"), ("cheese", "bridge", "en"), ("doctor", "volcano", "en"),
    ("chaise", "pont", "fr"), ("fromage", "pont", "fr"), ("fourchette", "primate", "fr"), ("pain", "galaxie", "fr"),
    ("guerre", "fromage", "fr"), ("arbre", "téléphone", "fr"),
])
def test_unrelated(closeness, a, b, lang):
    assert closeness.tier(a, b, lang)[0] is None
