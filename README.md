# ljkc-calendar

Data feed for the native calendar on
[livejazzkc.com/calendar](https://www.livejazzkc.com/calendar).

A GitHub Actions workflow rebuilds `events.json` every 30 minutes from the
public LiveJazzKC Google Calendar — same shows, cleaned up (performer/venue
split, full addresses, no promo listings) in the JSON shape the website
widget renders. The calendar itself is still maintained in Google Calendar
as always; this repo only republishes it in web-friendly form.

- Widget data URL: `https://raw.githubusercontent.com/<owner>/ljkc-calendar/main/events.json`
- Builder: `build_events_json.py` · Workflow: `.github/workflows/calendar.yml`
