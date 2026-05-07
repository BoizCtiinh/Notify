from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import time
import threading
import os

app = Flask(__name__)
CORS(app)

MAX_AGE          = 200
CLEANUP_INTERVAL = 5
MAX_PER_BOSS     = 50

BOSS_SLUGS = {
    "ripindra":      "rip_indra True Form",
    "doughking":     "Dough King",
    "cursedcaptain": "Cursed Captain",
    "soulreaper":    "Soul Reaper",
    "tyrant":        "Tyrant of the Skies",
    "darkbeard":     "Darkbeard",
}

NAME_TO_SLUG = {
    "ripindratrueform": "ripindra",
    "ripindra":         "ripindra",
    "doughking":        "doughking",
    "cursedcaptain":    "cursedcaptain",
    "soulreaper":       "soulreaper",
    "tyrantoftheskies": "tyrant",
    "tyrant":           "tyrant",
    "darkbeard":        "darkbeard",
}

_store       = {s: [] for s in BOSS_SLUGS}
_last_update = {s: 0.0 for s in BOSS_SLUGS}
_lock        = threading.Lock()

UUID_RE    = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PLAYERS_RE = re.compile(r"^\d{1,3}/\d{1,3}$")


def cleanup():
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = time.time()
        with _lock:
            for slug in _store:
                _store[slug] = [r for r in _store[slug] if now - r["posted_at"] <= MAX_AGE]


threading.Thread(target=cleanup, daemon=True).start()


def build_response(slug):
    now = time.time()
    with _lock:
        records  = list(_store[slug])
        last_upd = _last_update[slug]

    data = [
        {
            "Age":     max(0, int(now - r["posted_at"])),
            "JobId":   r["JobId"],
            "Name":    r["Name"],
            "Players": r["Players"],
        }
        for r in records
        if now - r["posted_at"] <= MAX_AGE
    ]
    data.sort(key=lambda x: x["Age"])

    return {"count": len(data), "data": data, "last_update": last_upd or now}


@app.route("/")
def home():
    return jsonify({"status": "ok", "max_age": MAX_AGE})


@app.route("/api/boss", methods=["POST"])
def post_boss():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": False, "message": "Invalid JSON"}), 400

    boss_name    = str(body.get("boss_name", "")).strip()
    player_count = str(body.get("player_count", "")).strip()
    job_id       = str(body.get("job_id", "")).strip().lower()

    if not boss_name:
        return jsonify({"status": False, "message": "boss_name is required"}), 422
    if not PLAYERS_RE.match(player_count):
        return jsonify({"status": False, "message": "player_count must be x/y (e.g. 11/12)"}), 422
    if not UUID_RE.match(job_id):
        return jsonify({"status": False, "message": "job_id must be a valid UUID"}), 422

    key  = boss_name.lower().replace(" ", "").replace("_", "")
    slug = NAME_TO_SLUG.get(key)
    if not slug:
        return jsonify({"status": False, "message": "Unknown boss: {}".format(boss_name)}), 422

    now    = time.time()
    record = {"Name": BOSS_SLUGS[slug], "JobId": job_id, "Players": player_count, "posted_at": now}

    with _lock:
        _store[slug].insert(0, record)
        if len(_store[slug]) > MAX_PER_BOSS:
            _store[slug] = _store[slug][:MAX_PER_BOSS]
        _last_update[slug] = now

    return jsonify({
        "status": True,
        "data": {"Age": 0, "JobId": job_id, "Name": BOSS_SLUGS[slug], "Players": player_count},
        "last_update": now,
    }), 201


@app.route("/api/boss/RipIndra")
def get_rip_indra():
    return jsonify(build_response("ripindra"))

@app.route("/api/boss/DoughKing")
def get_dough_king():
    return jsonify(build_response("doughking"))

@app.route("/api/boss/CursedCaptain")
def get_cursed_captain():
    return jsonify(build_response("cursedcaptain"))

@app.route("/api/boss/Soul reaper")
def get_soul_reaper():
    return jsonify(build_response("soulreaper"))

@app.route("/api/boss/SoulReaper")
def get_soul_reaper_alias():
    return jsonify(build_response("soulreaper"))

@app.route("/api/boss/Tyrant")
def get_tyrant():
    return jsonify(build_response("tyrant"))

@app.route("/api/boss/DarkBeard")
def get_darkbeard():
    return jsonify(build_response("darkbeard"))

@app.route("/api/boss/all")
def get_all():
    return jsonify({name: build_response(slug) for slug, name in BOSS_SLUGS.items()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
    
