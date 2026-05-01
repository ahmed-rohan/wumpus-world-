from __future__ import annotations

from dataclasses import asdict
from flask import Flask, jsonify, render_template, request

from wumpus_game import GameConfig, WumpusGame

app = Flask(__name__)

_game: WumpusGame | None = None

# Episode statistics
_stats = {"wins": 0, "losses": 0, "total_episodes": 0}


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/state")
def api_state():
    global _game
    if _game is None:
        _game = WumpusGame(GameConfig(rows=4, cols=4, pits=3))
        _game.start_new_episode()
    return jsonify(_game.to_public_state())


@app.post("/api/new")
def api_new():
    global _game
    data = request.get_json(silent=True) or {}

    rows = int(data.get("rows", 4))
    cols = int(data.get("cols", 4))
    pits = int(data.get("pits", 3))

    rows = max(3, min(12, rows))
    cols = max(3, min(12, cols))
    pits = max(1, min(30, pits))

    _game = WumpusGame(GameConfig(rows=rows, cols=cols, pits=pits))
    _game.start_new_episode()
    return jsonify(_game.to_public_state())


@app.post("/api/step")
def api_step():
    global _game, _stats
    if _game is None:
        _game = WumpusGame(GameConfig(rows=4, cols=4, pits=3))
        _game.start_new_episode()

    was_over = _game.game_over
    _game.step()

    # Track episode results
    if _game.game_over and not was_over:
        _stats["total_episodes"] += 1
        if _game.status in ("Fell into pit", "Eaten by wumpus"):
            _stats["losses"] += 1
        else:
            _stats["wins"] += 1

    return jsonify(_game.to_public_state())


@app.post("/api/reset")
def api_reset():
    """Reset the current game without changing config."""
    global _game
    if _game is None:
        _game = WumpusGame(GameConfig(rows=4, cols=4, pits=3))
    _game.start_new_episode()
    return jsonify(_game.to_public_state())


@app.get("/api/stats")
def api_stats():
    return jsonify(_stats)


@app.get("/api/kb_clauses")
def api_kb_clauses():
    """Return all KB clauses for the clause viewer."""
    if _game is None:
        return jsonify({"clauses": []})
    clauses = _game.get_kb_clauses()
    return jsonify({"clauses": clauses})


@app.get("/api/resolution_trace")
def api_resolution_trace():
    """Return the last resolution trace."""
    if _game is None:
        return jsonify({"trace": [], "query": ""})
    trace = _game.get_resolution_trace()
    return jsonify(trace)


if __name__ == "__main__":
    # Low-fidelity local dev server
    app.run(host="127.0.0.1", port=5000, debug=True)
