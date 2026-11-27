"""Collect messages from an authorized Discord channel."""
import argparse
import getpass
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent.parent
API_BASE = 'https://discord.com/api/v10'


def load_env():
    path = BASE_DIR / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch_page(token, channel, before=None, limit=100):
    params = {'limit': limit}
    if before:
        params['before'] = before
    url = f'{API_BASE}/channels/{channel}/messages?' + urlencode(params)
    request = Request(url, headers={
        'Authorization': f'Bot {token}',
        'User-Agent': 'digitalboo (local dataset collector, 1.0)',
    })
    for attempt in range(6):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                try:
                    delay = float(json.loads(exc.read()).get('retry_after', 2))
                except (ValueError, TypeError):
                    delay = 2
                time.sleep(max(delay, 0) + 0.2)
                continue
            if 500 <= exc.code < 600 and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            hints = {
                401: 'Bot Token khong hop le',
                403: 'Bot thieu quyen doc kenh',
                404: 'Channel ID sai hoac kenh khong truy cap duoc',
                429: 'Qua gioi han API',
            }
            raise RuntimeError(f'HTTP {exc.code}: {hints.get(exc.code, exc.reason)}') from None
        except (URLError, TimeoutError):
            if attempt == 5:
                raise RuntimeError('Khong the ket noi Discord API') from None
            time.sleep(2 ** attempt)


def extract_text(message):
    parts = []
    if message.get('content'):
        parts.append(message['content'])
    for embed in message.get('embeds', []):
        for key in ('title', 'description'):
            if embed.get(key):
                parts.append(embed[key])
        for field in embed.get('fields', []):
            parts.append(f"{field.get('name', '')}: {field.get('value', '')}")
    return '\n'.join(parts)


def normalize(message):
    snapshots = [s.get('message', {}) for s in message.get('message_snapshots', [])]
    originals = [
        {'timestamp': s.get('timestamp'), 'content': extract_text(s)}
        for s in snapshots
    ]
    return {
        'id': message['id'],
        'source': 'discord',
        'channel_id': message.get('channel_id'),
        'posted_at': message.get('timestamp'),
        'content': extract_text(message),
        'forwarded_messages': originals,
        'original_posted_at': originals[0]['timestamp'] if originals else None,
        'message_type': message.get('type'),
        'webhook_id': message.get('webhook_id'),
        'edited_at': message.get('edited_timestamp'),
    }


def fetch_announcements(token=None, channel=None, limit=0):
    """Return normalized messages, oldest first. No interactive input or file writes.

    Credentials default to environment variables or the script's .env file.
    limit=0 retrieves all accessible messages; a positive limit retrieves the latest N.
    """
    load_env()
    token = (token or os.getenv('DISCORD_BOT_TOKEN') or '').strip()
    channel = str(channel or os.getenv('DISCORD_CHANNEL_ID') or '').strip()
    if not token or not channel.isdigit():
        raise ValueError('Bot Token and numeric Channel ID required')
    if not isinstance(limit, int) or limit < 0:
        raise ValueError('limit must be a non-negative integer')
    rows = []
    before = None
    while True:
        size = min(100, limit - len(rows)) if limit else 100
        if size <= 0:
            break
        page = fetch_page(token, channel, before, size)
        if not page:
            break
        rows.extend(normalize(m) for m in page)
        before = min((m['id'] for m in page), key=int)
        if len(page) < size or (limit and len(rows) >= limit):
            break
        time.sleep(0.3)
    return sorted(rows, key=lambda m: int(m['id']))


def main():
    parser = argparse.ArgumentParser(description='Fetch authorized Discord channel history.')
    parser.add_argument('--limit', type=int, default=0, help='0 = all accessible messages')
    parser.add_argument('--out', type=Path, default=BASE_DIR / 'data/announcements_raw.json')
    args = parser.parse_args()
    if args.limit < 0:
        parser.error('--limit must be >= 0')
    load_env()
    token = os.getenv('DISCORD_BOT_TOKEN') or getpass.getpass('Bot Token: ')
    channel = os.getenv('DISCORD_CHANNEL_ID') or input('Channel ID: ').strip()
    try:
        rows = fetch_announcements(token, channel, args.limit)
    except ValueError as exc:
        parser.error(str(exc))
    except RuntimeError as exc:
        parser.exit(1, f'{exc}\n')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Hoan thanh: {len(rows)} tin nhan -> {args.out}')
    print('Kiem tra noi dung va an danh truoc khi chia se hoac commit.')


if __name__ == '__main__':
    main()
