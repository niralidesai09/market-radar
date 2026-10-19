"""score >= 7 stories -> strict-JSON cards (validated, retry once), verification, official archive."""
import hashlib, json, os, re, time, urllib.request
from datetime import datetime
from .core import gemini, load, UA, ROOT

CATS = ["Funding", "M&A", "IPO", "Policy", "Macro", "Big Tech/AI", "Layoffs", "Earnings"]
SECTORS = ["fintech", "quick commerce", "D2C", "SaaS", "AI", "EV", "edtech", "healthtech", "other"]
SENT = ["Bullish", "Bearish", "Neutral"]
IMPACT = ["Big Move", "Notable", "Watch"]
KEYS = ["headline", "the_number", "why_it_matters", "founder_takeaway", "sentiment", "category",
        "sector_tags", "companies", "geography"]

PROMPT = """Turn each news item into a scannable card for a business-school student. Use ONLY facts in the item. Never invent numbers or dates.
Return ONLY a JSON array, one object per item, with exactly these keys:
id (int, same as input), headline (<=10 words), the_number (the single key figure copied from the item, e.g. "$25M", "Rs 1,200 Cr", "6.5%", "-4%"; if there is no figure in the item use "-"),
why_it_matters (<=12 words), founder_takeaway (<=10 words), sentiment (Bullish|Bearish|Neutral, for Indian startups/markets),
category (one of {cats}), sector_tags (list from {sectors}), companies (list of names, may be empty),
geography (India|Global), amount_usd_m (number: funding/deal size in USD millions if category is Funding/M&A/IPO and stated, else null).
Items:
{items}"""

def wc(s): return len(str(s).split())

def validate(c):
    try:
        if not all(k in c for k in KEYS): return False
        if wc(c["headline"]) > 10 or wc(c["why_it_matters"]) > 12 or wc(c["founder_takeaway"]) > 10: return False
        if c["sentiment"] not in SENT or c["category"] not in CATS or c["geography"] not in ("India", "Global"): return False
        if not isinstance(c["sector_tags"], list) or not isinstance(c["companies"], list): return False
        c["sector_tags"] = [s for s in c["sector_tags"] if s in SECTORS] or ["other"]
        if len(str(c["the_number"])) > 16: return False
        a = c.get("amount_usd_m"); c["amount_usd_m"] = a if isinstance(a, (int, float)) else None
        return True
    except Exception:
        return False

def make_cards(stories, batch=12):
    t = load("topics.yaml"); out = []
    for b in range(0, len(stories), batch):
        todo = list(enumerate(stories[b:b + batch]))
        for attempt in (1, 2):                       # validate; retry failures once
            if not todo: break
            listing = "\n".join(f'{n}. [{s["source"]}; outlets={s["covered_by"]}] {s["title"]} :: {s["text"][:500]}' for n, s in todo)
            try:
                res = {r.get("id"): r for r in gemini(PROMPT.format(cats=CATS, sectors=SECTORS, items=listing))}
            except Exception as e:
                print("  card batch error:", str(e)[:100]); res = {}
            still = []
            for n, s in todo:
                c = res.get(n)
                if c and validate(c): out.append(finish(c, s))
                else: still.append((n, s))
            todo = still
            time.sleep(4)
    return out

def finish(c, s):
    """Attach facts we control (source, urls, verification) - the model never sets these."""
    text = (s["title"] + " " + s["text"]).replace(",", "")
    num = str(c["the_number"]); unconfirmed = False
    digits = re.findall(r"\d+(?:\.\d+)?", num.replace(",", ""))
    if digits and not all(d in text for d in digits):    # figure not literally in the source -> don't trust it
        c["the_number"] = "-"; c["amount_usd_m"] = None; unconfirmed = True
    official = s["tier"] == "official"
    sc = s["score"]
    impact = "Big Move" if sc >= 8.5 else "Notable" if sc >= 7.5 else "Watch"
    if impact == "Big Move" and not (official or s["covered_by"] >= 2):
        impact = "Notable"; unconfirmed = True           # Big Move needs official source OR 2+ outlets
    c.update({"impact": impact, "source_badge": "Official" if official else "Verified media",
              "covered_by_count": s["covered_by"], "url": s["url"], "source": s["source"],
              "score": sc, "date": s["date"], "unconfirmed": unconfirmed,
              "id": hashlib.md5(s["url"].split("?")[0].encode()).hexdigest()[:12], "archive_url": None})
    return c

def archive_official(card, now):
    """Official items only: save the original document, link it from the card."""
    try:
        req = urllib.request.Request(card["url"], headers=UA)
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read(3_000_000)
        ctype = resp.headers.get("Content-Type", "")
        ext = ".pdf" if "pdf" in ctype or card["url"].lower().endswith(".pdf") else ".html"
        rel = f'archive/{now:%Y/%m}/{card["id"]}{ext}'
        path = os.path.join(ROOT, "docs", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(body)
        card["archive_url"] = rel
    except Exception as e:
        print("  archive failed:", card["url"][:60], str(e)[:50])
    return card
