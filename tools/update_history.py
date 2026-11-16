"""Download the official PDF, validate all rows, and atomically extend the feed."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import urllib.request

SOURCE = 'https://files.floridalottery.com/exptkt/l6.pdf'
FIRST = dt.date(1999, 10, 27)
PATTERN = re.compile(r'(\d{2}/\d{2}/\d{2})\s+(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)(?:[ \t]+(LOTTO(?:[ \t]+DP)?))?')


def validate(rows, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if not rows:
        raise ValueError('Empty history')
    previous = None
    for row in rows:
        date = dt.date.fromisoformat(row['date'])
        numbers = row['numbers']
        if date < FIRST or date > today or date.weekday() not in (2, 5):
            raise ValueError('Invalid draw date')
        if previous and date <= previous:
            raise ValueError('Duplicate or unordered date')
        if len(numbers) != 6 or any(type(n) is not int or not 1 <= n <= 53 for n in numbers) or len(set(numbers)) != 6:
            raise ValueError('Invalid numbers')
        previous = date
    expected = set()
    date = FIRST
    while date <= previous:
        if date.weekday() in (2, 5):
            expected.add(date.isoformat())
        date += dt.timedelta(days=1)
    if {r['date'] for r in rows} != expected:
        raise ValueError('Incomplete drawing calendar; requires review')


def parse(text):
    rows = []
    for line in text.splitlines():
        matches = list(PATTERN.finditer(line))
        if len(re.findall(r'\b\d{2}/\d{2}/\d{2}\b', line)) != len(matches):
            raise ValueError('Unrecognized PDF row')
        for match in matches:
            month, day, year = map(int, match[1].split('/'))
            date = dt.date(1900 + year if year >= 88 else 2000 + year, month, day)
            if match[8] and 'DP' in match[8]:
                continue
            if date >= FIRST:
                rows.append({'date': date.isoformat(), 'numbers': sorted(map(int, match.group(2, 3, 4, 5, 6, 7)))})
    rows.sort(key=lambda r: r['date'])
    validate(rows)
    return rows


def extend(previous, rows):
    validate(previous['draws'])
    validate(rows)
    old = {r['date']: sorted(r['numbers']) for r in previous['draws']}
    new = {r['date']: sorted(r['numbers']) for r in rows}
    if any(new.get(date) != numbers for date, numbers in old.items()):
        raise ValueError('Previously published draws changed or disappeared; requires review')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=pathlib.Path)
    ap.add_argument('--feed', type=pathlib.Path, default=pathlib.Path('data/florida-lotto.json'))
    args = ap.parse_args()
    previous = json.loads(args.feed.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        pdf = pathlib.Path(tmp) / 'history.pdf'
        if args.pdf:
            body = args.pdf.read_bytes()
        else:
            request = urllib.request.Request(SOURCE, headers={'User-Agent': 'LottoInsightsHistoryUpdater/1.0'})
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read(10_000_001)
        if not body.startswith(b'%PDF-') or len(body) > 10_000_000:
            raise ValueError('Response is not a supported PDF')
        pdf.write_bytes(body)
        text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True, timeout=45)
        rows = parse(text)
    extend(previous, rows)
    if rows == previous['draws']:
        print('No new draws; keeping existing feed')
        return
    feed = {'schema_version': 1, 'game': 'florida_lotto', 'number_pool': 53,
            'source_url': SOURCE, 'pdf_sha256': hashlib.sha256(body).hexdigest(),
            'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'latest_draw': rows[-1]['date'], 'draw_count': len(rows), 'draws': rows}
    pending = args.feed.with_suffix('.pending')
    pending.write_text(json.dumps(feed, separators=(',', ':')) + '\n')
    pending.replace(args.feed)
    print(f"Validated {len(rows)} draws through {rows[-1]['date']}")


if __name__ == '__main__':
    main()
