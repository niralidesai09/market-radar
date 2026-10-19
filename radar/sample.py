"""Write realistic SAMPLE data so the dashboard/email can be previewed without API keys."""
import json, os, random
from datetime import datetime, timedelta, timezone
from . import market, notify
from .core import ROOT
IST = timezone(timedelta(hours=5, minutes=30)); now = datetime.now(IST)
def C(i, h, n, w, f, s, cat, sec, co, geo, imp, amt=None, off=False, cov=1, hrs=1, unc=False):
    return dict(id=f"s{i}", headline=h, the_number=n, why_it_matters=w, founder_takeaway=f, sentiment=s, impact=imp,
                category=cat, sector_tags=sec, companies=co, geography=geo, source_badge="Official" if off else "Verified media",
                covered_by_count=cov, url="https://example.com/"+str(i), source="RBI" if off else "Economic Times",
                score=9 if imp=="Big Move" else 8 if imp=="Notable" else 7, date=now.isoformat(), unconfirmed=unc,
                amount_usd_m=amt, archive_url="archive/sample.html" if off else None,
                first_seen=(now - timedelta(hours=hrs, days=i%5)).isoformat())
cards = [
 C(1,"Zepto files DRHP for IPO","$450M","Biggest quick-commerce listing so far","Public markets now reward fast growth","Bullish","IPO",["quick commerce"],["Zepto"],"India","Big Move",450,cov=4),
 C(2,"RBI keeps repo rate unchanged","6.5%","Loans stay costly; startups' debt unchanged","Plan runway for no rate relief","Neutral","Policy",["fintech"],[],"India","Big Move",off=True),
 C(3,"Razorpay raises Series F","$120M","Payments still attract big cheques","Fintech infra beats consumer apps","Bullish","Funding",["fintech"],["Razorpay"],"India","Notable",120,cov=2),
 C(4,"Ola Electric slashes 1,000 jobs","1,000","EV cash burn forces cost cuts","Watch burn before scaling","Bearish","Layoffs",["EV"],["Ola Electric"],"India","Notable"),
 C(5,"Brent crude jumps on supply fears","$107","Higher oil weakens rupee, hits margins","Hedge import-heavy costs","Bearish","Macro",[ "other"],[],"Global","Watch"),
 C(6,"Nifty edges up as FIIs return","+0.6%","Foreign money lifts IPO appetite","Good window to list","Bullish","Macro",["other"],[],"India","Watch",hrs=3),
 C(7,"Groww buys wealth-tech startup","$60M","Brokers consolidate to cross-sell","Acquihire exits are rising","Bullish","M&A",["fintech"],["Groww"],"India","Notable",60,cov=2,unc=True),
 C(8,"SEBI tightens F&O rules","3 rules","Retail trading volumes may fall","Broker revenue models at risk","Bearish","Policy",["fintech"],[],"India","Notable",off=True),
 C(9,"OpenAI cuts API prices 40%","-40%","Cheaper AI helps SaaS startups","Rebuild margins around AI","Bullish","Big Tech/AI",["AI","SaaS"],["OpenAI"],"Global","Notable"),
 C(10,"Swiggy Q2 loss narrows","₹625 Cr","Quick commerce nears breakeven","Unit economics are improving","Bullish","Earnings",["quick commerce"],["Swiggy"],"India","Watch",hrs=6),
]
d = os.path.join(ROOT, "docs", "data"); os.makedirs(d, exist_ok=True)
for c in cards:
    if c["category"]=="Funding": pass
json.dump(cards, open(f"{d}/cards.json","w"), ensure_ascii=False)
mk = market.pulse() if os.environ.get("LIVE") else [dict(name=n,value=v,change_pct=p,spark=[random.uniform(90,110) for _ in range(20)]) for n,v,p in [("Nifty 50","22,954",0.62),("Sensex","74,234",0.58),("USD/INR","94.76",-0.21),("Brent","$107.3",1.4)]]
json.dump({"updated": now.isoformat(), "tiles": mk}, open(f"{d}/market.json","w"))
json.dump([{"t": (now - timedelta(hours=8*i)).isoformat(), "score": round(random.uniform(-.4,.7),2), "n": 8} for i in range(20,0,-1)], open(f"{d}/sentiment.json","w"))
json.dump({"RBI Press Releases":{"fails":0},"Entrackr":{"fails":3,"error":"HTTP 403"}}, open(f"{d}/health.json","w"))
json.dump([{"title":"RBI keeps repo rate unchanged","url":"archive/sample.html","source":"RBI","date":now.isoformat(),"original":"https://rbi.org.in"}], open(f"{d}/archive.json","w"))
json.dump({"updated": now.isoformat(), "new": 10}, open(f"{d}/meta.json","w"))
os.makedirs(f"{ROOT}/docs/archive", exist_ok=True); open(f"{ROOT}/docs/archive/sample.html","w").write("<h1>Sample official doc</h1>")
top = sorted(cards, key=lambda c: -c["score"])
open(f"{ROOT}/preview_email.html","w").write(notify.run_html(top, mk, now)); print("subject:", notify.subject(top, now))
wk, _ = notify.weekly_html(cards, mk, json.load(open(f"{d}/sentiment.json")), now); open(f"{ROOT}/preview_weekly.html","w").write(wk)
