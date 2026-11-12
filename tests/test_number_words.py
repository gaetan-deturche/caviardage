"""Numbers written as words compare with each other: two lights up four. Digits stay apart: 4 is not four."""
from caviardage.game import Game
from caviardage.text import number_value


class Scores:
    def in_vocabulary(self, word, lang):
        return True

    def tier(self, a, b, lang):
        return None, 0.0


def game(sentence, lang="en"):
    return Game({"title": "Car", "paragraphs": [sentence], "url": "x"}, lang, Scores())


def test_two_lights_up_four():
    g = game("A four-wheel drive.")
    state = g.guess("two")["state"]
    four = [t for t in state["tokens"] if t.get("near") == "two"]
    assert len(four) == 1 and not four[0].get("revealed")


def test_digits_and_number_words_stay_apart():
    state = game("A four-wheel drive in 4 days.").guess("4")["state"]
    assert not any(t.get("text") == "four" or t.get("near") == "4" for t in state["tokens"])
    state = game("A four-wheel drive in 4 days.").guess("four")["state"]
    assert not any(t.get("text") == "4" or t.get("near") == "four" for t in state["tokens"])


def test_french_number_words():
    assert number_value("quatre", "fr") == ("words", 4)
    assert number_value("vingts", "fr") == ("words", 20)
    assert number_value("dix", "fr", guess=True) == ("words", 10)


def test_words_that_are_mostly_not_numbers_stay_words():
    assert number_value("one", "en") is None
    assert number_value("une", "fr") is None
    assert number_value("neuf", "fr") is None
