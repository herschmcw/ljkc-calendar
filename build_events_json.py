#!/usr/bin/env python3
"""Build events.json for the LiveJazzKC native calendar (free-route builder).

Used by the GitHub Actions workflow in this folder as the zero-cost
alternative to the Cloudflare Worker. Emits the SAME JSON shape the Worker
serves, so the Squarespace widget doesn't care which one it points at.

Usage:
  python build_events_json.py [days] [out_path]
Env:
  LJKC_ICS_FILE — read the calendar from this local .ics instead of fetching
                  (used for offline testing).
"""
import hashlib
import html as ihtml
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

CAL_ID = "qmhle7gdhlsgoj1o71dlth2u58@group.calendar.google.com"
ICS_URL = f"https://calendar.google.com/calendar/ical/{CAL_ID.replace('@', '%40')}/public/basic.ics"
TZ = ZoneInfo("America/Chicago")
PROMO_MARKERS = ["kansas city's #1 source", "livejazzkc.com -"]


def load_cal():
    import icalendar
    local = os.environ.get("LJKC_ICS_FILE")
    if local:
        with open(local, "rb") as f:
            return icalendar.Calendar.from_ical(f.read())
    req = urllib.request.Request(ICS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return icalendar.Calendar.from_ical(r.read())


def events_for_day(cal, day: date):
    """Same expansion semantics as the daily-agenda pipeline."""
    import recurring_ical_events
    start = datetime.combine(day, dtime.min).replace(tzinfo=TZ)
    end = start + timedelta(days=1)
    out = []
    for e in recurring_ical_events.of(cal).between(start, end):
        s = e.get("dtstart").dt
        en = e.get("dtend").dt if e.get("dtend") else None

        def norm(v):
            if isinstance(v, datetime):
                return v if v.tzinfo else v.replace(tzinfo=TZ)
            return datetime.combine(v, dtime.min).replace(tzinfo=TZ)

        s, en = norm(s), (norm(en) if en else None)
        if s.astimezone(TZ).date() != day and not (s < start):
            continue
        out.append({
            "summary": str(e.get("summary", "")).strip(),
            "location": str(e.get("location", "") or "").strip(),
            "description": str(e.get("description", "") or "").strip(),
            "start": s.astimezone(TZ),
            "end": en.astimezone(TZ) if en else None,
            "all_day": not isinstance(e.get("dtstart").dt, datetime),
        })
    return out


def _is_address(s):
    if not s:
        return False
    return bool(re.search(
        r"^\d+\s+\S+.*\b(St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Pl|Place|Ter|Terrace|Pkwy|Parkway|Hwy|Highway)\b",
        s, re.IGNORECASE))


def clean_venue(summary, location):
    performer, venue = summary, ""
    parts = re.split(r"\s+[–—-]\s+|(?<=[A-Za-z])-\s+(?=[A-Z])", summary, maxsplit=1)
    if len(parts) == 2:
        performer, rest = parts
        venue = rest.split("@")[-1].strip() if "@" in rest else rest.strip()
    if _is_address(venue):
        first = (location or "").split(",")[0].strip()
        venue = "" if _is_address(first) else first
    if not venue and location:
        first = location.split(",")[0].strip()
        if not _is_address(first):
            venue = first
    return performer.strip(), venue.strip()


def short_address(location):
    if not location:
        return ""
    clean = re.sub(r",?\s*USA\s*$", "", location).strip()
    m = re.search(r"(\d+\s+[^,]+,\s*[^,]+,\s*[A-Z]{2}\s*\d{5})", clean)
    return (m.group(1) if m else clean).strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</p>\s*<p[^>]*>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = ihtml.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main():
    days_out = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    out_path = sys.argv[2] if len(sys.argv) > 2 else "events.json"
    cal = load_cal()
    today = datetime.now(TZ).date()
    seen = {}
    for i in range(days_out + 1):
        day = today + timedelta(days=i)
        for e in events_for_day(cal, day):
            if any(m in e["summary"].lower() for m in PROMO_MARKERS):
                continue
            # unique by start+summary (a late-night show spans two day lists)
            key = (e["start"].isoformat(), e["summary"])
            if key in seen:
                continue
            performer, venue = clean_venue(e["summary"], e["location"])
            desc = strip_html(e["description"])
            if len(desc) > 1200:
                desc = desc[:1200].rstrip() + "…"
            seen[key] = {
                "id": hashlib.sha1(f"{key[0]}|{key[1]}".encode()).hexdigest()[:16],
                "summary": e["summary"],
                "performer": performer,
                "venue": venue,
                "location": e["location"],
                "address": short_address(e["location"]),
                "description": desc,
                "start": e["start"].date().isoformat() if e["all_day"] else e["start"].isoformat(),
                "end": None if (e["all_day"] or not e["end"]) else e["end"].isoformat(),
                "allDay": bool(e["all_day"]),
            }
    events = sorted(seen.values(), key=lambda x: x["start"])
    payload = {
        "generatedAt": datetime.now(TZ).isoformat(),
        "timezone": "America/Chicago",
        "range": {"from": today.isoformat(), "to": (today + timedelta(days=days_out)).isoformat()},
        "count": len(events),
        "events": events,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"wrote {out_path}: {len(events)} events, {os.path.getsize(out_path)//1024} KB")


if __name__ == "__main__":
    main()
