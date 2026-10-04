"""SQLite repository. Connections are scoped per call for worker-thread safety."""
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager


def default_home():
    return Path(os.environ.get('QUANTDESK_HOME') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'QuantDesk')


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, home=None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.path = self.home / 'library.sqlite3'
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, symbol TEXT NOT NULL,
                metadata TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS bars (
                dataset_id TEXT REFERENCES datasets(id) ON DELETE CASCADE,
                date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY(dataset_id,date));
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                body TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY, created_at TEXT, level TEXT, message TEXT, detail TEXT);
            PRAGMA user_version=1;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_dataset(self, name, symbol, rows, metadata):
        ident = uuid.uuid4().hex
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        meta = {**metadata, 'sha256': digest, 'rows': len(rows), 'start': rows[0]['date'], 'end': rows[-1]['date']}
        with self.connect() as db:
            db.execute('INSERT INTO datasets VALUES (?,?,?,?,?)', (ident, name, symbol.upper(), json.dumps(meta, ensure_ascii=False), now()))
            db.executemany('INSERT INTO bars VALUES (?,?,?,?,?,?,?)',
                           [(ident, r['date'], r['open'], r['high'], r['low'], r['close'], r['volume']) for r in rows])
        return ident

    def datasets(self, search=''):
        with self.connect() as db:
            records = db.execute('SELECT * FROM datasets WHERE name LIKE ? OR symbol LIKE ? ORDER BY created_at DESC',
                                 (f'%{search}%', f'%{search}%')).fetchall()
        return [{**dict(r), 'metadata': json.loads(r['metadata'])} for r in records]

    def dataset(self, ident):
        with self.connect() as db:
            r = db.execute('SELECT * FROM datasets WHERE id=?', (ident,)).fetchone()
        if not r:
            raise ValueError('数据集不存在或已删除')
        return {**dict(r), 'metadata': json.loads(r['metadata'])}

    def bars(self, ident, start='', end='9999-12-31'):
        self.dataset(ident)
        with self.connect() as db:
            records = db.execute('SELECT date,open,high,low,close,volume FROM bars WHERE dataset_id=? AND date>=? AND date<=? ORDER BY date',
                                 (ident, start, end)).fetchall()
        return [dict(r) for r in records]

    def delete_dataset(self, ident):
        with self.connect() as db:
            db.execute('DELETE FROM datasets WHERE id=?', (ident,))

    def save(self, kind, name, body, ident=None):
        if kind not in {'strategy', 'config', 'experiment'}:
            raise ValueError('无效的文档类型')
        ident = ident or uuid.uuid4().hex
        text = json.dumps(body, ensure_ascii=False, allow_nan=False)
        with self.connect() as db:
            existing = db.execute('SELECT kind FROM documents WHERE id=?', (ident,)).fetchone()
            if existing and existing['kind'] != kind:
                raise ValueError('不能覆盖不同类型的文档')
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,body=excluded.body,updated_at=excluded.updated_at',
                       (ident, kind, name, text, now()))
        return ident

    def documents(self, kind):
        with self.connect() as db:
            records = db.execute('SELECT * FROM documents WHERE kind=? ORDER BY updated_at DESC', (kind,)).fetchall()
        return [{**dict(r), 'body': json.loads(r['body'])} for r in records]

    def load(self, ident):
        with self.connect() as db:
            r = db.execute('SELECT * FROM documents WHERE id=?', (ident,)).fetchone()
        if not r:
            raise ValueError('保存记录不存在')
        return {**dict(r), 'body': json.loads(r['body'])}

    def delete(self, ident):
        with self.connect() as db:
            db.execute('DELETE FROM documents WHERE id=?', (ident,))

    def log(self, level, message, detail=''):
        with self.connect() as db:
            db.execute('INSERT INTO logs(created_at,level,message,detail) VALUES(?,?,?,?)', (now(), level, message, detail))

    def logs(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM logs ORDER BY id DESC LIMIT 500')]
