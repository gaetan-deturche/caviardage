"""Saved rounds and who played them, so a reload, a restart or another computer can resume them."""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

KEEP_DAYS = 180
HISTORY_LIMIT = 200
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "games.sqlite"


class Saves:
    def __init__(self, path=None):
        path = path or os.environ.get("CAVIARDAGE_SAVES") or DEFAULT_PATH
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock, self.db:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS games("
                "id TEXT PRIMARY KEY, lang TEXT, level TEXT, article TEXT, guesses TEXT, gave_up INTEGER, updated REAL)"
            )
            columns = [row[1] for row in self.db.execute("PRAGMA table_info(games)")]
            if "finished" not in columns:
                self.db.execute("ALTER TABLE games ADD COLUMN finished INTEGER")
            if "hints" not in columns:
                self.db.execute("ALTER TABLE games ADD COLUMN hints TEXT")
            if "snapshot" not in columns:
                self.db.execute("ALTER TABLE games ADD COLUMN snapshot TEXT")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS plays(player TEXT, game TEXT, PRIMARY KEY(player, game)) WITHOUT ROWID"
            )
            self.db.execute("DELETE FROM games WHERE updated < ?", (time.time() - KEEP_DAYS * 86400,))
            self.db.execute("DELETE FROM plays WHERE game NOT IN (SELECT id FROM games)")

    def save(self, game):
        row = (
            game.id, game.lang, game.level, json.dumps(game.article, ensure_ascii=False),
            json.dumps([g["word"] for g in game.guesses.values()], ensure_ascii=False),
            int(game.gave_up), time.time(), int(game.finished), json.dumps(game.hint_log, ensure_ascii=False),
            json.dumps(game.snapshot(), ensure_ascii=False),
        )
        with self.lock, self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO games(id, lang, level, article, guesses, gave_up, updated, finished, hints, snapshot) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)", row,
            )

    def load(self, game_id):
        """The saved round as a dict, or None."""
        with self.lock:
            row = self.db.execute(
                "SELECT lang, level, article, guesses, gave_up, hints, snapshot FROM games WHERE id=?", (game_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "lang": row[0], "level": row[1], "article": json.loads(row[2]),
            "guesses": json.loads(row[3]), "gave_up": bool(row[4]), "hints": json.loads(row[5] or "[]"),
            "snapshot": json.loads(row[6]) if row[6] else None,
        }

    def set_snapshot(self, game):
        """Store a replayed round's state, so it reopens fast, without changing its date."""
        with self.lock, self.db:
            self.db.execute(
                "UPDATE games SET snapshot=? WHERE id=?", (json.dumps(game.snapshot(), ensure_ascii=False), game.id)
            )

    def add_play(self, player, game_id):
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO plays VALUES (?, ?)", (player, game_id))

    def unknown_status(self, player):
        """Rounds of this player saved before finished was recorded."""
        with self.lock:
            rows = self.db.execute(
                "SELECT g.id FROM plays p JOIN games g ON g.id = p.game WHERE p.player=? AND g.finished IS NULL", (player,)
            ).fetchall()
        return [row[0] for row in rows]

    def set_finished(self, game_id, finished):
        """Record a round's status without counting as playing it."""
        with self.lock, self.db:
            self.db.execute("UPDATE games SET finished=? WHERE id=?", (int(finished), game_id))

    def history(self, player):
        """A player's rounds, newest first. The title stays hidden until a round is over."""
        with self.lock:
            rows = self.db.execute(
                "SELECT g.id, g.lang, g.level, g.article, g.guesses, g.gave_up, g.finished, g.updated "
                "FROM plays p JOIN games g ON g.id = p.game WHERE p.player=? ORDER BY g.updated DESC LIMIT ?",
                (player, HISTORY_LIMIT),
            ).fetchall()
        out = []
        for game_id, lang, level, article, guesses, gave_up, finished, updated in rows:
            out.append({
                "id": game_id, "lang": lang, "level": level, "count": len(json.loads(guesses)),
                "finished": bool(finished), "gaveUp": bool(gave_up), "updated": updated,
                "title": json.loads(article)["title"] if finished else None,
            })
        return out
