import re
import time
import threading
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("api")

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
    "ripindratruefrom": "ripindra",
    "ripindra":         "ripindra",
    "doughking":        "doughking",
    "cursedcaptain":    "cursedcaptain",
    "soulreaper":       "soulreaper",
    "tyrantoftheskies": "tyrant",
    "tyrant":           "tyrant",
    "darkbeard":        "darkbeard",
}

_store = {s: [] for s in BOSS_SLUGS}
_last_update = {s: 0.0 for s in BOSS_SLUGS}
_lock = threading.Lock()


def _cleanup():
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = time.time()
        with _lock:
            for slug in _store:
                before = len(_store[slug])
                _store[slug] = [r for r in _store[slug] if now - r["posted_at"] <= MAX_AGE]
                removed = before - len(_store[slug])
                if removed:
                    log.info("Removed {} expired ({})".format(removed, BOSS_SLUGS[slug]))


threading.Thread(target=_cleanup, daemon=True).start()


UUID_RE    = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PLAYERS_RE = re.compile(r"^\d{1,3}/\d{1,3}$")


def validate(body: dict) -> tuple[str, str, str, str]:
    boss_name    = str(body.get("boss_name", "")).strip()
    player_count = str(body.get("player_count", "")).strip()
    job_id       = str(body.get("job_id", "")).strip().lower()

    if not boss_name:
        raise HTTPException(422, "boss_name is required")
    if not PLAYERS_RE.match(player_count):
        raise HTTPException(422, "player_count must be x/y (e.g. 11/12)")
    if not UUID_RE.match(job_id):
        raise HTTPException(422, "job_id must be a valid UUID")

    key  = boss_name.lower().replace(" ", "").replace("_", "")
    slug = NAME_TO_SLUG.get(key)
    if not slug:
        raise HTTPException(422, "Unknown boss: {}".format(boss_name))

    return slug, BOSS_SLUGS[slug], player_count, job_id


def build_response(slug: str) -> dict:
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


app = FastAPI(title="Boss Tracker API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "max_age": MAX_AGE}


@app.post("/api/boss", status_code=201)
async def post_boss(request: Request):
    body = await request.json()
    slug, name, players, job_id = validate(body)

    now = time.time()
    record = {"Name": name, "JobId": job_id, "Players": players, "posted_at": now}

    with _lock:
        _store[slug].insert(0, record)
        if len(_store[slug]) > MAX_PER_BOSS:
            _store[slug] = _store[slug][:MAX_PER_BOSS]
        _last_update[slug] = now

    log.info("POST {} | {} | {}".format(name, players, job_id))
    return {"success": True, "data": {"Age": 0, "JobId": job_id, "Name": name, "Players": players}, "last_update": now}


@app.get("/api/boss/RipIndra")
def get_rip_indra():
    return build_response("ripindra")

@app.get("/api/boss/DoughKing")
def get_dough_king():
    return build_response("doughking")

@app.get("/api/boss/CursedCaptain")
def get_cursed_captain():
    return build_response("cursedcaptain")

@app.get("/api/boss/Soul reaper")
def get_soul_reaper():
    return build_response("soulreaper")

@app.get("/api/boss/SoulReaper", include_in_schema=False)
def get_soul_reaper_alias():
    return build_response("soulreaper")

@app.get("/api/boss/Tyrant")
def get_tyrant():
    return build_response("tyrant")

@app.get("/api/boss/DarkBeard")
def get_darkbeard():
    return build_response("darkbeard")

@app.get("/api/boss/all")
def get_all():
    return {name: build_response(slug) for slug, name in BOSS_SLUGS.items()}
    
