"""Caviardage local server. Run with: .venv\\Scripts\\python app.py"""
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from caviardage.articles import ArticleError, Articles
from caviardage.closeness import Closeness
from caviardage.game import Game

PORT = 5180
STATIC = Path(__file__).resolve().parent / "static"
MAX_GAMES = 50

app = Flask(__name__)
closeness = Closeness()
articles = Articles()
games = {}


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.post("/api/new")
def new_game():
    body = request.get_json(silent=True) or {}
    lang = body.get("lang") if body.get("lang") in ("fr", "en") else "fr"
    level = body.get("level") if body.get("level") in ("famous", "wide") else "famous"
    try:
        article = articles.next(lang, level)
    except ArticleError as error:
        return jsonify({"error": str(error)}), 503
    game = Game(article, lang, closeness)
    games[game.id] = game
    while len(games) > MAX_GAMES:
        games.pop(next(iter(games)))
    return jsonify(game.state())


def _game(game_id):
    return games.get(game_id)


@app.post("/api/guess")
def guess():
    body = request.get_json(silent=True) or {}
    game = _game(body.get("id"))
    if not game:
        return jsonify({"error": "expired"}), 404
    return jsonify(game.guess(str(body.get("word", ""))))


@app.post("/api/giveup")
def give_up():
    body = request.get_json(silent=True) or {}
    game = _game(body.get("id"))
    if not game:
        return jsonify({"error": "expired"}), 404
    return jsonify(game.give_up())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True)
