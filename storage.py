"""JSON-backed guestbook with an automatically synchronized SQLite database.

JSON is intentionally loaded at startup to match the coursework's second session.
The in-memory Python list is used to render routes, and SQLite is kept in sync
for the standalone database requirement.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Ho_Chi_Minh')


class GuestbookStore:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.json_path = self.folder / 'data.json'
        self.db_path = self.folder / 'guestbook.db'
        self.lock = threading.RLock()
        self.entries: list[dict[str, Any]] = []
        self.next_id = 1
        self._initialize_db()
        self._load()

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def _initialize_db(self):
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_entries_name ON entries(name)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at)')

    def _load(self):
        # JSON is the authoritative storage whenever it exists; SQLite recovers
        # files only if there is no JSON. Both formats work across restarts.
        if self.json_path.exists():
            raw = json.loads(self.json_path.read_text(encoding='utf-8'))
            rows = raw if isinstance(raw, list) else raw.get('entries', [])
            next_id = raw.get('next_id') if isinstance(raw, dict) else None
            if not isinstance(rows, list):
                raise ValueError('data.json must contain a list of entries')
            ids = set()
            entries = []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                try:
                    id_ = int(item['id'])
                    name = str(item['name'])
                    message = str(item['message'])
                    created = str(item.get('created_at', datetime.now(timezone.utc).isoformat()))
                    datetime.fromisoformat(created.replace('Z', '+00:00'))
                except (KeyError, ValueError, TypeError):
                    continue
                if id_ < 1 or id_ in ids:
                    continue
                ids.add(id_)
                entries.append({'id': id_, 'name': name, 'message': message, 'created_at': created})
            self.entries = entries
            self.next_id = max(max(ids, default=0) + 1, int(next_id or 1))
        else:
            with self._connect() as db:
                self.entries = [dict(x) for x in db.execute('SELECT id,name,message,created_at FROM entries ORDER BY id')]
            self.next_id = max((x['id'] for x in self.entries), default=0) + 1
            self._write_json()
        self._sync_db()

    def _sync_db(self):
        with self._connect() as db:
            db.execute('DELETE FROM entries')
            db.executemany(
                'INSERT INTO entries (id, name, message, created_at) VALUES (?, ?, ?, ?)',
                [(x['id'], x['name'], x['message'], x['created_at']) for x in self.entries]
            )

    def _write_json(self):
        payload = {'version': 1, 'next_id': self.next_id, 'entries': self.entries}
        tmp = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.folder,
                                             prefix='.guestbook-', suffix='.tmp', delete=False) as f:
                tmp = f.name
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.json_path)
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    def _save(self):
        self._write_json()
        self._sync_db()

    def all(self):
        with self.lock:
            return sorted((dict(item) for item in self.entries), key=lambda x: x['id'], reverse=True)

    def add(self, name: str, message: str):
        with self.lock:
            entry = {
                'id': self.next_id,
                'name': name,
                'message': message,
                'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
            self.entries.append(entry)
            self.next_id += 1
            try:
                self._save()
            except Exception:
                self.entries.pop()
                self.next_id -= 1
                raise
            return dict(entry)

    def delete(self, id_: int):
        with self.lock:
            original = self.entries
            self.entries = [x for x in original if x['id'] != id_]
            if len(original) == len(self.entries):
                return False
            try:
                self._save()
            except Exception:
                self.entries = original
                raise
            return True

    def stats(self):
        items = self.all()
        names = Counter(item['name'] for item in items)
        leaders = sorted(names.items(), key=lambda x: (-x[1], x[0].casefold()))
        now = datetime.now(TZ)
        today = now.date()
        today_count = 0
        this_week = 0
        recent_days = Counter()
        for item in items:
            date = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            day = date.astimezone(TZ).date()
            if day == today:
                today_count += 1
            if 0 <= (today - day).days < 7:
                this_week += 1
                recent_days[day.isoformat()] += 1
        days = [(today - timedelta(days=x)).isoformat() for x in range(6, -1, -1)]
        return {
            'total': len(items),
            'unique': len(names),
            'today': today_count,
            'week': this_week,
            'leaders': [{'name': name, 'count': count, 'rank': i + 1}
                        for i, (name, count) in enumerate(leaders[:5])],
            'all_authors': [{'name': name, 'count': count} for name, count in leaders],
            'daily': [{'date': d, 'count': recent_days[d]} for d in days],
            'average': round(sum(len(item['message']) for item in items) / len(items)) if items else 0,
            'latest': items[:5],
        }

    def export(self):
        with self.lock:
            return {'version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
                    'entries': self.all()}
