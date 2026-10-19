"""Market pulse from Yahoo Finance's free public chart endpoint (no key)."""
import json, urllib.request

SYMS = [("Nifty 50", "^NSEI", "{:,.0f}"), ("Sensex", "^BSESN", "{:,.0f}"),
        ("USD/INR", "INR=X", "{:.2f}"), ("Brent", "BZ=F", "${:.1f}")]

def pulse():
    out = []
    for name, sym, fmt in SYMS:
        try:
            u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}?range=1mo&interval=1d"
            r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20))["chart"]["result"][0]
            closes = [round(c, 4) for c in r["indicators"]["quote"][0]["close"] if c]
            last, prev = closes[-1], closes[-2]
            out.append({"name": name, "value": fmt.format(last), "change_pct": round((last - prev) / prev * 100, 2),
                        "spark": closes[-20:]})
        except Exception as e:
            out.append({"name": name, "value": "n/a", "change_pct": 0, "spark": [], "error": str(e)[:60]})
    return out
