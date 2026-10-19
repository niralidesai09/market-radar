"""python -m radar.pipeline [run|weekly]   (add --dry to skip email/push)"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from . import core, cards as cardmod, market, notify

IST = timezone(timedelta(hours=5, minutes=30))
DATA = os.path.join(core.ROOT, "docs", "data")

def rd(name, default):
    try: return json.load(open(os.path.join(DATA, name)))
    except Exception: return default

def wr(name, obj):
    os.makedirs(DATA, exist_ok=True)
    json.dump(obj, open(os.path.join(DATA, name), "w"), ensure_ascii=False, indent=1)

def update_health(health, now):
    h = rd("health.json", {})
    for name, v in health.items():
        e = h.setdefault(name, {"fails": 0, "last_ok": None})
        if isinstance(v, int) and v > 0: e["fails"], e["last_ok"] = 0, now.isoformat()
        else: e["fails"] += 1; e["error"] = str(v)
    wr("health.json", h); return h

def gauge(cs):
    if not cs: return 0
    return round((sum(c["sentiment"] == "Bullish" for c in cs) - sum(c["sentiment"] == "Bearish" for c in cs)) / len(cs), 2)

def run(dry=False):
    now = datetime.now(IST)
    items, health = core.fetch_all()
    update_health(health, now)
    existing = rd("cards.json", [])
    cutoff = (now - timedelta(days=14)).isoformat()
    existing = [c for c in existing if (c.get("first_seen") or "") >= cutoff]
    known_urls = {c["id"] for c in existing}
    known_titles = [core.norm_title(c["headline"]) for c in existing]
    clusters = core.dedupe(items)
    fresh = [c for c in clusters
             if __import__("hashlib").md5(c["url"].split("?")[0].encode()).hexdigest()[:12] not in known_urls]
    print(f"fetched {len(items)} | stories {len(clusters)} | not seen before {len(fresh)}")
    scored = core.score(fresh)
    keep = sorted([c for c in scored if (c.get("score") or 0) >= core.load("topics.yaml")["min_score"]], key=lambda c: -c["score"])[:25]
    print(f"{len(keep)} score >= 7")
    new = cardmod.make_cards(keep)
    new = [c for c in new if all(SequenceMatcher(None, core.norm_title(c["headline"]), t).ratio() < 0.85 for t in known_titles)]
    for c in new:
        c["first_seen"] = now.isoformat()
        if c["source_badge"] == "Official": cardmod.archive_official(c, now)
    allc = sorted(existing + new, key=lambda c: -c["score"])
    wr("cards.json", allc)
    arch = [{"title": c["headline"], "url": c["archive_url"], "source": c["source"], "date": c["first_seen"], "original": c["url"]}
            for c in allc if c.get("archive_url")]
    wr("archive.json", arch)
    mk = market.pulse(); wr("market.json", {"updated": now.isoformat(), "tiles": mk})
    today = [c for c in allc if c["first_seen"][:10] == now.date().isoformat()]
    sent = rd("sentiment.json", [])
    sent.append({"t": now.isoformat(), "score": gauge(today), "n": len(today)}); wr("sentiment.json", sent[-300:])
    wr("meta.json", {"updated": now.isoformat(), "new": len(new)})
    print(f"{len(new)} new cards")
    if new and not dry: notify.send_run(new, mk, now)
    elif not new: print("nothing new >= 7 -> no email")

def weekly(dry=False):
    now = datetime.now(IST)
    week = [c for c in rd("cards.json", []) if c["first_seen"] >= (now - timedelta(days=7)).isoformat()]
    if not week: print("empty week"); return
    if not dry: notify.send_weekly(week, rd("market.json", {}).get("tiles", []), rd("sentiment.json", []), now)

if __name__ == "__main__":
    mode = next((a for a in sys.argv[1:] if not a.startswith("-")), "run")
    (weekly if mode == "weekly" else run)(dry="--dry" in sys.argv)
