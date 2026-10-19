"""Email (Gmail SMTP, table-based inline-CSS HTML) + ntfy phone push."""
import html, json, os, smtplib, ssl, urllib.request
from collections import defaultdict
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from .core import ROOT

ARROW = {"Bullish": ("▲", "#16a34a"), "Bearish": ("▼", "#dc2626"), "Neutral": ("●", "#6b7280")}
IMPACT_BG = {"Big Move": "#dc2626", "Notable": "#d97706", "Watch": "#6b7280"}

def dash_url():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        o, r = repo.split("/"); return f"https://{o.lower()}.github.io/{r}/"
    return os.environ.get("DASHBOARD_URL", "http://localhost:8000/docs/")

def overall(cards):
    b = sum(c["sentiment"] == "Bullish" for c in cards); r = sum(c["sentiment"] == "Bearish" for c in cards)
    return "Bullish" if b > r else "Bearish" if r > b else "Neutral"

def short_names(cards):
    return ", ".join(" ".join(c["headline"].split()[:3]) for c in cards[:2])

def subject(cards, now):
    big = [c for c in cards if c["impact"] == "Big Move"]
    ar = ARROW[overall(cards)][0] + " " + overall(cards)
    date = f"{now.day} {now:%b}"
    lead = f"🔴 {len(big)} Big Move{'s' if len(big) != 1 else ''} · {ar}" if big else f"{ar} · {len(cards)} stories"
    return f"{lead} | {short_names(cards)} | {date}"

def chip(text, bg):
    return f'<span style="display:inline-block;background:{bg};color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:4px">{html.escape(text)}</span>'

def pulse_row(tiles):
    cells = ""
    for t in tiles:
        up = t["change_pct"] >= 0; col = "#16a34a" if up else "#dc2626"
        cells += (f'<td align="center" style="padding:8px 2px;font-family:Arial,sans-serif">'
                  f'<div style="font-size:11px;color:#6b7280">{html.escape(t["name"])}</div>'
                  f'<div style="font-size:15px;font-weight:700;color:#111">{html.escape(t["value"])}</div>'
                  f'<div style="font-size:12px;font-weight:700;color:{col}">{"▲" if up else "▼"} {abs(t["change_pct"]):.2f}%</div></td>')
    return f'<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;border-radius:8px"><tr>{cells}</tr></table>'

def card_html(c):
    a, col = ARROW[c["sentiment"]]
    chips = chip(c["impact"], IMPACT_BG[c["impact"]]) + chip(c["category"], "#374151")
    if c.get("unconfirmed"): chips += chip("Unconfirmed", "#92400e")
    if c["covered_by_count"] > 1: chips += chip(f'covered by {c["covered_by_count"]}', "#2563eb")
    return f'''<tr><td style="padding:6px 0"><table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-left:5px solid {col};border-radius:8px;background:#ffffff"><tr><td style="padding:14px;font-family:Arial,sans-serif">
<div>{chips}</div>
<div style="font-size:34px;line-height:40px;font-weight:800;color:{col};margin-top:6px">{a} {html.escape(str(c["the_number"]))}</div>
<div style="font-size:16px;font-weight:700;color:#111;margin-top:2px"><a href="{html.escape(c["url"])}" style="color:#111;text-decoration:none">{html.escape(c["headline"])}</a></div>
<div style="font-size:13px;color:#4b5563;margin-top:6px">💡 {html.escape(c["why_it_matters"])}</div>
<div style="font-size:13px;color:#4b5563;margin-top:2px">🚀 {html.escape(c["founder_takeaway"])}</div>
<div style="font-size:11px;color:#9ca3af;margin-top:6px">{html.escape(c["source_badge"])} · {html.escape(c["source"])}</div>
</td></tr></table></td></tr>'''

def page(title, sub, tiles, body, button_label="See all on dashboard"):
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0;padding:0;background:#f9fafb">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb"><tr><td align="center" style="padding:12px">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td style="font-family:Arial,sans-serif;padding:4px 0 10px"><div style="font-size:22px;font-weight:800;color:#111">{title}</div><div style="font-size:12px;color:#6b7280">{sub}</div></td></tr>
<tr><td style="padding-bottom:8px">{pulse_row(tiles)}</td></tr>
{body}
<tr><td align="center" style="padding:16px 0"><a href="{dash_url()}" style="display:inline-block;background:#111827;color:#fff;font-family:Arial,sans-serif;font-weight:700;font-size:15px;padding:14px 28px;border-radius:8px;text-decoration:none">{button_label} →</a></td></tr>
</table></td></tr></table></body></html>'''

def run_html(cards, tiles, now):
    top = cards[:5]
    return page("Market Radar", f"{now:%a %d %b · %H:%M} IST", tiles, "".join(card_html(c) for c in top))

# ---------- weekly charts (PNG hosted on the dashboard so Gmail can load them) ----------
def charts(week, sent, now):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    os.makedirs(os.path.join(ROOT, "docs", "charts"), exist_ok=True)
    days = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
    tot = defaultdict(float)
    for c in week:
        if c["category"] == "Funding" and c.get("amount_usd_m"): tot[c["first_seen"][:10]] += c["amount_usd_m"]
    fig, ax = plt.subplots(figsize=(6, 3), dpi=140)
    ax.bar([d.strftime("%a") for d in days], [tot[d.isoformat()] for d in days], color="#2563eb")
    ax.set_title("Funding announced ($M)", fontsize=11, loc="left"); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); f1 = f"funding-{now:%G-W%V}.png"; fig.savefig(os.path.join(ROOT, "docs/charts", f1)); plt.close(fig)
    pts = [s for s in sent if s["t"] >= (now - timedelta(days=7)).isoformat()]
    fig, ax = plt.subplots(figsize=(6, 2.4), dpi=140)
    if pts: ax.plot(range(len(pts)), [s["score"] for s in pts], color="#16a34a", lw=2.5)
    ax.axhline(0, color="#9ca3af", lw=1); ax.set_ylim(-1, 1); ax.set_xticks([])
    ax.set_title("Sentiment trend (▲ bullish / ▼ bearish)", fontsize=11, loc="left"); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); f2 = f"sentiment-{now:%G-W%V}.png"; fig.savefig(os.path.join(ROOT, "docs/charts", f2)); plt.close(fig)
    return f1, f2

def weekly_html(week, tiles, sent, now):
    f1, f2 = charts(week, sent, now); base = dash_url() + "charts/"
    top = sorted(week, key=lambda c: -c["score"])[:5]
    img = lambda f: f'<tr><td style="padding:6px 0"><img src="{base}{f}" width="100%" style="display:block;border-radius:8px;border:1px solid #e5e7eb"></td></tr>'
    body = img(f1) + "".join(card_html(c) for c in top) + img(f2)
    return page("Week in 60 seconds", f"Week ending {now:%d %b %Y}", tiles, body, "Open full dashboard"), f1

# ---------- sending ----------
def send_mail(subj, htm):
    user, pw, to = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD"), os.environ.get("MAIL_TO")
    if not (user and pw and to): print("email skipped (GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO not set)"); return
    m = MIMEMultipart("alternative"); m["Subject"], m["From"], m["To"] = subj, f"Market Radar <{user}>", to
    m.attach(MIMEText("Open this email in an HTML-capable app.", "plain")); m.attach(MIMEText(htm, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw); s.sendmail(user, [t.strip() for t in to.split(",")], m.as_string())
    print("email sent:", subj)

def push(title, msg, priority=3):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic: print("push skipped (NTFY_TOPIC not set)"); return
    body = json.dumps({"topic": topic, "title": title, "message": msg, "priority": priority, "click": dash_url()}).encode()
    urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", body, {"Content-Type": "application/json"}), timeout=20)
    print("push sent")

def send_run(cards, tiles, now):
    cards = sorted(cards, key=lambda c: -c["score"])
    s = subject(cards, now)
    send_mail(s, run_html(cards, tiles, now))
    big = [c for c in cards if c["impact"] == "Big Move"]
    lines = "\n".join(f'{ARROW[c["sentiment"]][0]} {c["the_number"]}  {c["headline"]}' for c in cards[:4])
    push(s.split(" | ")[0], lines, 5 if big else 3)

def send_weekly(week, tiles, sent, now):
    htm, _ = weekly_html(week, tiles, sent, now)
    s = f"📊 Week in 60 seconds | {ARROW[overall(week)][0]} {overall(week)} week | {now.day} {now:%b}"
    send_mail(s, htm); push("Week in 60 seconds", f"{len(week)} stories · {overall(week)} week", 3)
