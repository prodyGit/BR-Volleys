#!/usr/bin/env python3
"""
BR Volleys → Google Calendar helper
Fetches the BR Volleys event page, finds all iCal feeds, merges them into one .ics.
"""
import os, re, sys, hashlib, datetime as dt
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

PAGE_URL = os.environ.get("BRV_PAGE_URL", "https://www.berlin-recycling-volleys.de/news/events")
OUTPUT_ICS = os.environ.get("OUTPUT_ICS", "br_volleys_merged.ics")
TIMEZONE = os.environ.get("TZ", "Europe/Berlin")

def fetch(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r

def extract_ical_links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        text = (a.get_text() or "").lower()
        if "ical" in text or "task=ical.download" in href.lower() or href.lower().endswith(".ics"):
            links.append(urljoin(base, href))
    # remove duplicates
    seen, unique = set(), []
    for l in links:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return unique

def split_events(ics_text):
    text = ics_text.replace("\r\n", "\n").replace("\r", "\n")
    events = []
    for m in re.finditer(r"BEGIN:VEVENT.*?END:VEVENT", text, flags=re.S|re.I):
        block = m.group(0)
        uid = re.search(r"^UID:(.+)$", block, flags=re.M|re.I)
        uid = uid.group(1).strip() if uid else hashlib.sha1(block.encode()).hexdigest()
        events.append((uid, block))
    return events

def build_calendar(events):
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BRV Scraper//Merged ICS//EN",
        f"X-WR-CALNAME:BR Volleys (merged)",
        f"X-WR-TIMEZONE:{TIMEZONE}",
    ]
    body = [e[1] for e in events]
    footer = ["END:VCALENDAR"]
    return "\r\n".join(header + body + footer) + "\r\n"

def main():
    print(f"Loading {PAGE_URL} ...")
    html = fetch(PAGE_URL).text
    links = extract_ical_links(html, PAGE_URL)
    if not links:
        print("No iCal links found.")
        sys.exit(1)
    print("Found iCal links:", *links, sep="\n - ")

    all_events = {}
    for u in links:
        try:
            print(f"Downloading {u} ...")
            r = fetch(u)
            for uid, block in split_events(r.text):
                all_events[uid] = block
        except Exception as e:
            print(f"Failed {u}: {e}")
    print(f"Collected {len(all_events)} unique events.")
    merged = build_calendar(sorted(all_events.items()))
    with open(OUTPUT_ICS, "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"Wrote {OUTPUT_ICS}")

if __name__ == "__main__":
    main()
