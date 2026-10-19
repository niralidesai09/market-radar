"""Stage 1: fetch -> dedupe -> score (Gemini). Prints a table. No cards/email yet."""
import hashlib, json, os, re, sys, time, urllib.error, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (compatible; MarketRadar/1.0; personal use)"}
MAX_AGE_H = 30
MODELS = [os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), "gemini-flash-latest"]

def load(name):
    return yaml.safe_load(open(os.path.join(ROOT, "config", name)))

def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def parse_date(s):
    if not s: return None
    for fn in (parsedate_to_datetime, lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
               lambda x: datetime.strptime(x, "%d-%b-%Y %H:%M:%S")):
        try:
            d = fn(s.strip())
            return d if d.tzinfo else d.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        except Exception: pass
    return None

def fetch_source(src):
    raw = urllib.request.urlopen(urllib.request.Request(src["url"], headers=UA), timeout=25).read()
    root = ET.fromstring(raw)
    items = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        g = lambda n: next((strip(c.text) for c in it if c.tag.split("}")[-1] == n and c.text), "")
        link = g("link") or next((c.get("href") for c in it if c.tag.split("}")[-1] == "link" and c.get("href")), "")
        d = parse_date(g("pubDate") or g("published") or g("updated"))
        items.append({"title": g("title"), "url": link, "date": d.isoformat() if d else None,
                      "source": src["name"], "tier": src["tier"],
                      "text": (g("description") or g("summary") or g("content"))[:600]})
        if len(items) >= src.get("max_items", 40): break
    return items

def fetch_all():
    srcs, items, health = load("sources.yaml")["sources"], [], {}
    for s in srcs:
        try:
            got = fetch_source(s); items += got; health[s["name"]] = len(got)
        except Exception as e:
            health[s["name"]] = f"FAIL {str(e)[:50]}"
    return items, health

def norm_title(t):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s[-|]\s[^-|]+$", "", t.lower())).strip()

STOP = set("the a an of in on to for and as at by with from is are its it new after says say amid over this that will may".split())

NOISE = re.compile(r"recovery certificate|release order|notice of demand|appeal no|attachment (of|on)|\bRC No|adjudication order|settlement order", re.I)

def same_story(a, b, cross=False):
    """Title similarity > 0.85, OR heavy keyword overlap (same story, reworded headline)."""
    if SequenceMatcher(None, a, b).ratio() > 0.85: return True
    ta, tb = set(a.split()) - STOP, set(b.split()) - STOP
    return len(ta) >= 4 and len(tb) >= 4 and len(ta & tb) / len(ta | tb) >= (0.45 if cross else 0.8)

def dedupe(items):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_H)
    fresh = []
    for i in items:
        if NOISE.search(i["title"]): continue
        d = datetime.fromisoformat(i["date"]) if i["date"] else None
        if d is None or d >= cutoff: fresh.append(i)
    clusters, seen = [], {}
    for i in fresh:
        h = hashlib.md5(i["url"].split("?")[0].encode()).hexdigest()
        if h in seen: continue
        nt = norm_title(i["title"]); i["_nt"] = nt
        match = next((c for c in clusters if same_story(c["_nt"], nt, i["source"] not in c["outlets"])), None)
        if match:
            match["outlets"].add(i["source"])
            if i["tier"] == "official": match["tier"] = "official"
            match["alts"].append(i["url"])
        else:
            i["outlets"] = {i["source"]}; i["alts"] = []; clusters.append(i)
        seen[h] = 1
    for c in clusters: c["covered_by"] = len(c["outlets"])
    return clusters

PROMPT = """You are a news editor for an Indian business-school student tracking startups and markets.
Rate each item's BIGNESS from 0-10 using: money size, people affected, market-moving potential, novelty.
Reference: 9-10 = RBI rate move, $500M+ deal, major IPO/unicorn event; 7-8 = $10M+ round, big policy/M&A, notable listing; <=6 = routine, opinion, small, stock-tip or exchange routine filings.
Topics that matter: {topics}. Watchlist companies get a bonus: {watch}.
Return ONLY JSON: [{{"id":<int>,"score":<0-10>}}] for every id.
Items:
{items}"""

def gemini(prompt):
    key = os.environ["GEMINI_API_KEY"]
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}}).encode()
    last = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for wait in (0, 15, 40):
            time.sleep(wait)
            try:
                req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": key})
                out = json.load(urllib.request.urlopen(req, timeout=120))
                return json.loads(out["candidates"][0]["content"]["parts"][0]["text"])
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 404: break          # model gone -> try next
                if e.code not in (429, 500, 503): raise
            except (json.JSONDecodeError, KeyError) as e:
                last = e
    raise RuntimeError(f"gemini failed: {last}")

def score(clusters, batch=40):
    t = load("topics.yaml")
    for b in range(0, len(clusters), batch):
        chunk = clusters[b:b + batch]
        listing = "\n".join(f'{n}. [{c["source"]}] {c["title"]} :: {c["text"][:200]}' for n, c in enumerate(chunk))
        prompt = PROMPT.format(topics="; ".join(t["big_means"]), watch=", ".join(t["watchlist_companies"]), items=listing)
        try:
            res = {r["id"]: r for r in gemini(prompt)}
        except Exception as e:
            print("  scoring batch failed:", str(e)[:100], file=sys.stderr); res = {}
        for n, c in enumerate(chunk):
            c["score"] = (res.get(n) or {}).get("score")
        time.sleep(4)
    return clusters
