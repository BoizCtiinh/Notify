import re
import time
import threading
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("api")

MAX_AGE          = 200
CLEANUP_INTERVAL = 5
MAX_PER_BOSS     = 50

BOSS_SLUGS: dict[str, str] = {
    "ripindra":      "rip_indra True Form",
    "doughking":     "Dough King",
    "cursedcaptain": "Cursed Captain",
    "soulreaper":    "Soul Reaper",
    "tyrant":        "Tyrant of the Skies",
    "darkbeard":     "Darkbeard",
}

NAME_TO_SLUG: dict[str, str] = {
    "ripindratruefrom": "ripindra",
    "ripindra":         "ripindra",
    "doughking":        "doughking",
    "cursedcaptain":    "cursedcaptain",
    "soulreaper":       "soulreaper",
    "tyrantoftheskies": "tyrant",
    "tyrant":           "tyrant",
    "darkbeard":        "darkbeard",
}

_store: dict[str, list] = {s: [] for s in BOSS_SLUGS}
_last_update: dict[str, float] = {s: 0.0 for s in BOSS_SLUGS}
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
                    log.info("Removed {} expired entries ({})".format(removed, BOSS_SLUGS[slug]))


threading.Thread(target=_cleanup, daemon=True).start()


class BossEntry(BaseModel):
    boss_name:    str
    player_count: str
    job_id:       str

    @field_validator("player_count")
    @classmethod
    def check_players(cls, v):
        if not re.match(r"^\d{1,3}/\d{1,3}$", v):
            raise ValueError("Format: x/y (e.g. 11/12)")
        return v

    @field_validator("job_id")
    @classmethod
    def check_job_id(cls, v):
        if not re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", v):
            raise ValueError("job_id must be a valid UUID")
        return v.lower()


def build_response(slug: str) -> dict[str, Any]:
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

    return {
        "count":       len(data),
        "data":        data,
        "last_update": last_upd or now,
    }


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
def post_boss(entry: BossEntry):
    key  = entry.boss_name.lower().replace(" ", "").replace("_", "")
    slug = NAME_TO_SLUG.get(key)
    if not slug:
        raise HTTPException(422, detail="Unknown boss: {}".format(entry.boss_name))

    now = time.time()
    record = {
        "Name":      BOSS_SLUGS[slug],
        "JobId":     entry.job_id,
        "Players":   entry.player_count,
        "posted_at": now,
    }

    with _lock:
        _store[slug].insert(0, record)
        if len(_store[slug]) > MAX_PER_BOSS:
            _store[slug] = _store[slug][:MAX_PER_BOSS]
        _last_update[slug] = now

    log.info("POST {} | {} | {}".format(record["Name"], record["Players"], record["JobId"]))
    return {"success": True, "data": {"Age": 0, "JobId": record["JobId"], "Name": record["Name"], "Players": record["Players"]}, "last_update": now}


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
    