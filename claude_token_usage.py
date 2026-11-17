from __future__ import annotations

import copy
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Asia/Shanghai')
TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')


def count(value):
    return value if type(value) is int and 0 <= value <= 10**15 else 0


def estimate_cost(model, usage, pricing):
    rates = pricing.get(model)
    if rates is None:
        for name in sorted(pricing, key=len, reverse=True):
            suffix = model.removeprefix(name + '-')
            if model.startswith(name + '-') and len(suffix) == 8 and suffix.isdigit():
                rates = pricing[name]
                break
    if rates is None:
        return None
    context = sum(count(usage.get(k)) for k in TOKEN_FIELDS if k != 'output_tokens')
    suffix = ''
    for limit in (100000, 200000, 272000):
        candidate = f'_above_{limit//1000}k_tokens'
        if context > limit and 'input_cost_per_token' + candidate in rates:
            suffix = candidate
    def rate(key):
        return rates.get(key + suffix, rates.get(key))
    writes = count(usage.get('cache_creation_input_tokens'))
    cache = usage.get('cache_creation')
    hour = min(writes, count(cache.get('ephemeral_1h_input_tokens'))) if isinstance(cache, dict) else 0
    parts = [(count(usage.get('input_tokens')), rate('input_cost_per_token')),
             (count(usage.get('output_tokens')), rate('output_cost_per_token')),
             (count(usage.get('cache_read_input_tokens')), rate('cache_read_input_token_cost')),
             (writes-hour, rate('cache_creation_input_token_cost')),
             (hour, rate('cache_creation_input_token_cost_above_1hr'))]
    if any(n and (not isinstance(price, (int, float)) or not math.isfinite(price)) for n, price in parts):
        return None
    return sum(n * price for n, price in parts if n)


def usage_record(row, pricing):
    if not isinstance(row, dict) or row.get('type') != 'assistant':
        return None
    message = row.get('message')
    if not isinstance(message, dict) or not isinstance(message.get('usage'), dict):
        return None
    model = message.get('model')
    if not isinstance(model, str) or not model.startswith('claude-') or len(model) > 100:
        return None
    message_id = message.get('id')
    if not isinstance(message_id, str) or not message_id:
        return None
    try:
        dt = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return None
        stamp = dt.timestamp()
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
        return None
    usage = message['usage']
    tokens = sum(count(usage.get(k)) for k in TOKEN_FIELDS)
    if not tokens:
        return None
    key = hashlib.sha256((str(row.get('requestId') or '') + '\0' + message_id).encode()).hexdigest()
    cost = estimate_cost(model, usage, pricing)
    return key, stamp, tokens, cost


class ClaudeTokenUsage:
    def __init__(self, roots=None, cache_path=None, *, clock=time.time, pricing_path=None):
        config = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home()/'.claude'))).expanduser()
        self.roots = list(roots) if roots is not None else [config/'projects', Path.home()/'.claude-swap-backup/sessions']
        self.cache_path = Path(cache_path) if cache_path else Path.home()/'.cache/turzx/claude-token-usage.sqlite3'
        self.clock = clock
        self.pricing_path = Path(pricing_path) if pricing_path else Path(__file__).with_name('claude-token-pricing.json')
        self.lock = threading.RLock()
        self.last_refresh = None
        self.data = {'status': 'loading', 'source': 'local_claude_code', 'timezone': 'Asia/Shanghai',
                     'today': None, 'week': None, 'updated_at': None}

    def refresh_if_due(self):
        now = self.clock()
        if self.last_refresh is not None and 0 <= now-self.last_refresh < 30:
            return
        self.last_refresh = now
        try:
            result = self.collect(now)
        except (OSError, ValueError, sqlite3.Error):
            with self.lock:
                self.data['status'] = 'unavailable'
            return
        with self.lock:
            self.data = result

    def collect(self, now):
        local = datetime.fromtimestamp(now, TIMEZONE)
        today = local.replace(hour=0, minute=0, second=0, microsecond=0)
        week = today - timedelta(days=today.weekday())
        pricing_blob = self.pricing_path.read_bytes()
        pricing = json.loads(pricing_blob)['models']
        fingerprint = hashlib.sha256(pricing_blob).hexdigest()
        scope = json.dumps([1, week.isoformat(), sorted(str(Path(root).resolve()) for root in self.roots)])
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.cache_path, timeout=3)
        self.cache_path.chmod(0o600)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, inode INTEGER, size INTEGER, modified INTEGER, offset INTEGER);
CREATE TABLE IF NOT EXISTS messages(path TEXT, key TEXT, at REAL, tokens INTEGER, cost REAL, PRIMARY KEY(path,key));
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);''')
            db.execute('BEGIN IMMEDIATE')
            meta = dict(db.execute('SELECT key,value FROM meta'))
            if meta.get('pricing') != fingerprint or meta.get('scope') != scope:
                db.execute('DELETE FROM files')
                db.execute('DELETE FROM messages')
                db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('pricing', fingerprint))
                db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('scope', scope))
            known = {r[0]: r[1:] for r in db.execute('SELECT path,inode,size,modified,offset FROM files')}
            paths = set()
            available = any(Path(root).is_dir() for root in self.roots)
            for root in self.roots:
                for path in Path(root).rglob('*.jsonl'):
                    if path.is_symlink():
                        continue
                    stat = path.stat()
                    name = str(path.resolve())
                    paths.add(name)
                    previous = known.get(name)
                    if stat.st_mtime < week.timestamp():
                        continue
                    if previous and previous[:3] == (stat.st_ino, stat.st_size, stat.st_mtime_ns):
                        continue
                    offset = previous[3] if previous else 0
                    if previous and (previous[0] != stat.st_ino or stat.st_size < previous[1]
                                     or stat.st_size == previous[1] and stat.st_mtime_ns != previous[2]):
                        offset = 0
                        db.execute('DELETE FROM messages WHERE path=?', (name,))
                    with path.open('rb') as stream:
                        stream.seek(offset)
                        while True:
                            line = stream.readline()
                            if not line or not line.endswith(b'\n'):
                                break
                            offset = stream.tell()
                            if b'"usage"' not in line or b'"assistant"' not in line:
                                continue
                            try:
                                record = usage_record(json.loads(line), pricing)
                            except (ValueError, TypeError, RecursionError):
                                continue
                            if record is None or record[1] < week.timestamp():
                                continue
                            key, stamp, tokens, cost = record
                            db.execute('''INSERT INTO messages VALUES (?,?,?,?,?) ON CONFLICT(path,key) DO UPDATE SET
at=min(at,excluded.at),tokens=max(tokens,excluded.tokens),cost=CASE WHEN cost IS NULL OR excluded.cost IS NULL THEN NULL ELSE max(cost,excluded.cost) END''',
                                       (name,key,stamp,tokens,cost))
                    db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?)', (name,stat.st_ino,stat.st_size,stat.st_mtime_ns,offset))
            for missing in set(known)-paths:
                db.execute('DELETE FROM messages WHERE path=?', (missing,))
                db.execute('DELETE FROM files WHERE path=?', (missing,))
            db.execute('DELETE FROM messages WHERE at<?', (week.timestamp(),))
            def totals(start):
                token_sum,cost_sum,missing,messages = db.execute('''SELECT sum(tokens),sum(cost),sum(cost IS NULL),count(*) FROM
(SELECT key,min(at) AS stamp,max(tokens) AS tokens,CASE WHEN count(cost)<count(*) THEN NULL ELSE max(cost) END AS cost
FROM messages GROUP BY key) WHERE stamp>=? AND stamp<=?''', (start.timestamp(),now)).fetchone()
                return {'tokens': token_sum or 0, 'cost_usd': None if missing else round(cost_sum or 0,6),
                        'unpriced_messages': missing or 0, 'messages':messages,'starts_at':start.isoformat()}
            result = {'status':'ok' if available else 'unavailable','source':'local_claude_code', 'timezone':'Asia/Shanghai',
                      'today':totals(today) if available else None,'week':totals(week) if available else None,
                      'updated_at':now,'pricing_basis':'standard_api_tokens'}
            db.commit()
            return result
        finally:
            db.close()

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.data)
        if result['updated_at'] is not None and self.clock()-result['updated_at']>120:
            result['status'] = 'stale'
        return result
